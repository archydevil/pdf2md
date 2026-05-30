/**
 * Client for the local KB Forge sidecar (Python FastAPI).
 *
 * The sidecar is optional and runs fully offline (default http://localhost:8077).
 * All calls degrade gracefully: if the sidecar is unreachable the UI just shows
 * a hint that the KB is not running.
 */

const KB_BASE_URL =
  process.env.NEXT_PUBLIC_KB_URL ?? "http://localhost:8077"

export interface KBIngestResponse {
  doc_id: string
  chunks: number
}

export interface KBHealth {
  ok: boolean
  ollama: boolean
  model: string
}

async function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  try {
    return await p
  } finally {
    clearTimeout(timer)
  }
}

export async function kbHealth(): Promise<KBHealth | null> {
  try {
    const res = await withTimeout(
      fetch(`${KB_BASE_URL}/health`, { method: "GET" }),
      2500,
    )
    if (!res.ok) return null
    return (await res.json()) as KBHealth
  } catch {
    return null
  }
}

export async function ingestMarkdown(params: {
  markdown: string
  fileName: string
  title?: string
  classify?: boolean
  contextualize?: boolean
}): Promise<KBIngestResponse> {
  const res = await fetch(`${KB_BASE_URL}/ingest/markdown`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      markdown: params.markdown,
      file_name: params.fileName,
      title: params.title,
      classify: params.classify ?? true,
      contextualize: params.contextualize ?? false,
    }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`KB ingest failed (${res.status}): ${detail}`)
  }
  return (await res.json()) as KBIngestResponse
}

export interface KBCitation {
  n: number
  chunk_id: string
  file_name: string
  section_path: string[]
  page: number | null
  text: string
}

export interface KBChatResponse {
  query: string
  answer: string
  citations: KBCitation[]
}

export async function kbChat(params: {
  query: string
  k?: number
  rerank?: boolean
  provider?: "local" | "cloud"
}): Promise<KBChatResponse> {
  const res = await fetch(`${KB_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: params.query,
      k: params.k ?? 6,
      rerank: params.rerank ?? true,
      provider: params.provider ?? "local",
    }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`KB chat failed (${res.status}): ${detail}`)
  }
  return (await res.json()) as KBChatResponse
}

export interface KBStats {
  chunks: number
  lancedb_dir: string
}

export async function kbStats(): Promise<KBStats | null> {
  try {
    const res = await withTimeout(fetch(`${KB_BASE_URL}/stats`), 2500)
    if (!res.ok) return null
    return (await res.json()) as KBStats
  } catch {
    return null
  }
}

