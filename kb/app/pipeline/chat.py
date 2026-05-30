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
from app.privacy.egress import EgressDenied, prepare_egress
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
            text = await self._answer_cloud(prompt, model=model)
        else:
            text = await self.ollama.generate(
                prompt, system=_SYSTEM, temperature=0.1, model=model
            )
        return ChatAnswer(answer=text, citations=citations)

    async def _answer_cloud(self, prompt: str, model: str | None = None) -> str:
        """Send to the cloud provider, gated by the egress policy.

        With ``cloud_anonymize`` on (default), the prompt is anonymized via the
        egress gateway before leaving the machine and the answer is restored
        with the reversible mapping. The gateway raises ``EgressDenied`` when the
        air-gap switch (``KB_ALLOW_CLOUD_EGRESS``) is off.
        """
        settings = get_settings()
        if settings.cloud_anonymize:
            envelope = prepare_egress(prompt, require_approval=False)
            raw = await self.cloud.generate(
                envelope.safe_text, system=_SYSTEM, temperature=0.1, model=model
            )
            return envelope.restore(raw)
        if not settings.allow_cloud_egress:
            raise EgressDenied(
                "Egress verso il cloud disabilitato (air-gap). "
                "Imposta KB_ALLOW_CLOUD_EGRESS=true per consentirlo."
            )
        return await self.cloud.generate(
            prompt, system=_SYSTEM, temperature=0.1, model=model
        )
