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
  cloudBaseUrl?: string
  cloudApiKey?: string
  model?: string
}): Promise<KBChatResponse> {
  const res = await fetch(`${KB_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: params.query,
      k: params.k ?? 6,
      rerank: params.rerank ?? true,
      provider: params.provider ?? "local",
      ...(params.cloudBaseUrl ? { cloud_base_url: params.cloudBaseUrl } : {}),
      ...(params.cloudApiKey ? { cloud_api_key: params.cloudApiKey } : {}),
      ...(params.model ? { model: params.model } : {}),
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

// --- Meetily integration: audio transcription, SQLite import, analysis ---

export interface KBAudioResponse {
  doc_id: string
  chunks: number
  segments: number
  transcript: string
}

export async function ingestAudio(params: {
  file: File
  language?: string
  classify?: boolean
  contextualize?: boolean
}): Promise<KBAudioResponse> {
  const form = new FormData()
  form.append("file", params.file)
  if (params.language) form.append("language", params.language)
  form.append("classify", String(params.classify ?? true))
  form.append("contextualize", String(params.contextualize ?? false))
  const res = await fetch(`${KB_BASE_URL}/ingest/audio`, {
    method: "POST",
    body: form,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`KB audio ingest failed (${res.status}): ${detail}`)
  }
  return (await res.json()) as KBAudioResponse
}

export interface MeetilyImportedMeeting {
  meeting_id: string
  chunks: number
}

export interface MeetilyImportResponse {
  meetings: MeetilyImportedMeeting[]
}

export async function meetilyImport(params: {
  dbPath: string
  classify?: boolean
  contextualize?: boolean
}): Promise<MeetilyImportResponse> {
  const res = await fetch(`${KB_BASE_URL}/meetily/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      db_path: params.dbPath,
      classify: params.classify ?? true,
      contextualize: params.contextualize ?? false,
    }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`Meetily import failed (${res.status}): ${detail}`)
  }
  return (await res.json()) as MeetilyImportResponse
}

export interface AnalysisTemplate {
  id: string
  name: string | null
  description: string | null
}

export async function analysisTemplates(): Promise<AnalysisTemplate[]> {
  try {
    const res = await withTimeout(fetch(`${KB_BASE_URL}/analysis/templates`), 2500)
    if (!res.ok) return []
    const data = (await res.json()) as { templates: AnalysisTemplate[] }
    return data.templates ?? []
  } catch {
    return []
  }
}

export interface AnalysisRunResponse {
  template_id: string
  markdown: string
}

export async function analysisRun(params: {
  content: string
  templateId: string
  model?: string
}): Promise<AnalysisRunResponse> {
  const res = await fetch(`${KB_BASE_URL}/analysis/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: params.content,
      template_id: params.templateId,
      ...(params.model ? { model: params.model } : {}),
    }),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`Analysis run failed (${res.status}): ${detail}`)
  }
  return (await res.json()) as AnalysisRunResponse
}

