"""RAG chat: retrieve -> build a citation-grounded context -> answer.

Designed for weak local models: the retriever (hybrid + rerank) does the heavy
lifting, and the prompt forces the model to answer ONLY from the provided
context and to cite sources as ``[n]``. Each ``[n]`` maps to a returned chunk so
the UI can show provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.cloud_client import CloudClient
from app.config import get_settings
from app.ollama_client import OllamaClient
from app.pipeline.retrieve import Retriever
from app.privacy.anonymize import anonymize
from app.privacy.egress import EgressDenied
from app.schema import RetrievedChunk

_SYSTEM = (
    "Sei un assistente che risponde SOLO usando il CONTESTO fornito. "
    "Cita ogni affermazione con il riferimento [n] del passaggio usato. "
    "Se il contesto non contiene la risposta, dillo chiaramente: "
    "'Non trovo questa informazione nella knowledge base.' Non inventare."
)


@dataclass
class Citation:
    n: int
    chunk_id: str
    file_name: str
    section_path: list[str]
    page: int | None
    text: str


@dataclass
class ChatAnswer:
    answer: str
    citations: list[Citation] = field(default_factory=list)


def _build_context(chunks: list[RetrievedChunk]) -> tuple[str, list[Citation]]:
    blocks: list[str] = []
    citations: list[Citation] = []
    for i, item in enumerate(chunks, start=1):
        prov = item.chunk.provenance
        loc = " > ".join(prov.section_path) if prov.section_path else prov.file_name
        blocks.append(f"[{i}] (fonte: {prov.file_name} — {loc})\n{item.chunk.text}")
        citations.append(
            Citation(
                n=i,
                chunk_id=item.chunk.id,
                file_name=prov.file_name,
                section_path=prov.section_path,
                page=prov.page,
                text=item.chunk.text,
            )
        )
    return "\n\n".join(blocks), citations


class ChatEngine:
    def __init__(
        self,
        retriever: Retriever | None = None,
        ollama: OllamaClient | None = None,
        cloud: CloudClient | None = None,
    ) -> None:
        self.retriever = retriever or Retriever()
        self.ollama = ollama or OllamaClient()
        self.cloud = cloud or CloudClient()

    async def answer(
        self,
        query: str,
        k: int = 6,
        where: str | None = None,
        rerank: bool | None = None,
        model: str | None = None,
        provider: str = "local",
        cloud_base_url: str | None = None,
        cloud_api_key: str | None = None,
    ) -> ChatAnswer:
        chunks = await self.retriever.search(query, k=k, where=where, rerank=rerank)
        if not chunks:
            return ChatAnswer(answer="Non trovo questa informazione nella knowledge base.")
        context, citations = _build_context(chunks)
        prompt = (
            f"CONTESTO:\n{context}\n\n"
            f"DOMANDA: {query}\n\n"
            "Rispondi in italiano, citando i passaggi con [n]."
        )
        if provider == "cloud":
            text = await self._answer_cloud(
                prompt,
                model=model,
                base_url=cloud_base_url,
                api_key=cloud_api_key,
            )
        else:
            text = await self.ollama.generate(
                prompt, system=_SYSTEM, temperature=0.1, model=model
            )
        return ChatAnswer(answer=text, citations=citations)

    async def _answer_cloud(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> str:
        """Send to the cloud provider, gated by the egress policy.

        Credentials may come from the environment (``KB_CLOUD_*``) or be supplied
        per-request from the UI. Providing an API key for the request counts as
        explicit consent to leave the machine for that call; otherwise the
        master switch ``KB_ALLOW_CLOUD_EGRESS`` must be on. Either way, with
        ``cloud_anonymize`` on (default) the prompt is anonymized before sending
        and the answer is restored with the reversible mapping.
        """
        settings = get_settings()
        # Per-request credentials override the env-configured client.
        client = (
            CloudClient(base_url=base_url, api_key=api_key)
            if (base_url or api_key)
            else self.cloud
        )
        explicit_consent = bool(api_key)

        if settings.cloud_anonymize:
            if not (settings.allow_cloud_egress or explicit_consent):
                raise EgressDenied(
                    "Egress verso il cloud disabilitato (air-gap). "
                    "Inserisci una API key nelle impostazioni cloud o imposta "
                    "KB_ALLOW_CLOUD_EGRESS=true."
                )
            anon = anonymize(prompt, language="it")
            raw = await client.generate(
                anon.text, system=_SYSTEM, temperature=0.1, model=model
            )
            return anon.deanonymize(raw)
        if not (settings.allow_cloud_egress or explicit_consent):
            raise EgressDenied(
                "Egress verso il cloud disabilitato (air-gap). "
                "Inserisci una API key nelle impostazioni cloud o imposta "
                "KB_ALLOW_CLOUD_EGRESS=true."
            )
        return await client.generate(
            prompt, system=_SYSTEM, temperature=0.1, model=model
        )
