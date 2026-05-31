# KB Forge — Local-first Knowledge Base sidecar

Pipeline **air-gapped** che trasforma file eterogenei in una Knowledge Base
ottimizzata per modelli locali (anche piccoli), con classificazione dettagliata,
anonimizzazione PII opzionale e integrazione con Meetily (STT + analisi).

## Principi

- **Local-first / air-gapped**: per default nessun byte lascia la macchina.
  Tutto gira su Ollama + librerie locali.
- **Cloud opzionale con cancello**: qualunque uscita verso cloud passa da un
  Egress Gateway che (1) rileva PII, (2) ti mostra un diff per revisione
  manuale, (3) invia solo testo redatto, (4) de-anonimizza la risposta in locale.
- **Retrieval fa il lavoro pesante**: chunk contestualizzati + hybrid search +
  reranking → anche un modello da 7B risponde con precisione e citazioni.

## Stack

| Funzione                | Strumento                          |
|-------------------------|------------------------------------|
| Runtime modelli         | Ollama                             |
| Embeddings              | `bge-m3` (dense + sparse, IT)      |
| Reranking               | `bge-reranker-v2-m3` (opzionale)   |
| LLM enrich/classify     | `qwen2.5:32b` / `llama3.1:8b`      |
| Parsing layout-aware    | Docling (fallback: unstructured)   |
| OCR offline             | RapidOCR / llama3.2-vision         |
| STT                     | whisper.cpp `large-v3` + ffmpeg    |
| Anonimizzazione PII     | Microsoft Presidio + spaCy IT      |
| Vector store            | LanceDB (embedded, hybrid)         |
| Esposizione             | FastAPI ora, MCP server poi        |

## Stato (fasi)

- [x] Fase 0 — scheletro: config, schema chunk, store LanceDB, embeddings Ollama, FastAPI
- [ ] Fase 1 — ingest PDF/DOCX/MD (Docling) + chunking + enrichment
- [ ] Fase 2 — hybrid retrieval + rerank + chat con citazioni
- [ ] Fase 3 — OCR scansioni + email/HTML
- [ ] Fase 4 — Presidio + Egress Gateway
- [ ] Fase 5 — Meetily: STT + import SQLite + template analisi
- [ ] Fase 6 — MCP server + GraphRAG opzionale

## Avvio (dev)

```bash
cd kb
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

I modelli locali richiesti (già presenti se hai eseguito `ollama list`):

```bash
ollama pull bge-m3
ollama pull llama3.1:8b
```

## Cloud opzionale (a comando)

Per default tutto gira **locale/air-gapped**. Puoi usare un modello cloud
quando vuoi, per singola richiesta (`provider: "cloud"` su `/chat`, tool MCP
`kb_chat`, o il toggle **Locale/Cloud** nel pannello chat). L'uscita passa
sempre dall'Egress Gateway: con `KB_CLOUD_ANONYMIZE=true` (default) le PII
vengono sostituite con placeholder reversibili **prima** dell'invio e
ripristinate nella risposta.

Variabili d'ambiente (prefisso `KB_`):

```bash
KB_ALLOW_CLOUD_EGRESS=true                 # master switch: senza questo, egress negato (403)
KB_CLOUD_BASE_URL=https://api.openai.com/v1  # qualsiasi endpoint OpenAI-compatible
KB_CLOUD_API_KEY=sk-...                     # la tua chiave
KB_CLOUD_MODEL=gpt-4o-mini
KB_CLOUD_ANONYMIZE=true                     # anonimizza le PII prima dell'invio
KB_CORS_ORIGINS=http://localhost:3000,https://tuo-dominio  # se esponi UI/sidecar in cloud
```

Nota: gli **embeddings restano locali** (bge-m3) perché l'indice è costruito con
quel modello; il cloud è usato solo per la generazione della risposta.

Il sidecar è un'app FastAPI portabile: puoi eseguirlo dove vuoi (anche su un
server/cloud) — non è vincolato alla macchina locale.

## Layout

```
kb/
  app/
    main.py            FastAPI app + endpoint
    config.py          impostazioni (env-driven)
    schema.py          schema Pydantic (Document, Chunk, ...)
    pipeline/          ingest → parse → chunk → enrich → classify → embed
    store/             LanceDB (vettori + BM25)
    analysis/          motore analisi template-driven (template Meetily)
    bridges/           STT (whisper.cpp), import Meetily SQLite
    privacy/           anonimizzazione PII + egress gateway
  requirements.txt
```
