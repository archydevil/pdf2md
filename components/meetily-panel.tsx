"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { MarkdownPreview } from "@/components/markdown-preview"
import {
  Mic,
  Database,
  FileAudio,
  Import,
  Sparkles,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
  kbHealth,
  kbStats,
  ingestAudio,
  meetilyImport,
  analysisTemplates,
  analysisRun,
  type AnalysisTemplate,
} from "@/lib/kb-client"

type Tab = "audio" | "import" | "analysis"

export function MeetilyPanel() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [tab, setTab] = useState<Tab>("audio")

  // Audio transcription
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [audioLang, setAudioLang] = useState("it")
  const [transcribing, setTranscribing] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(null)
  const audioInputRef = useRef<HTMLInputElement>(null)

  // Meetily SQLite import
  const [dbPath, setDbPath] = useState("")
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState<string | null>(null)

  // Analysis
  const [templates, setTemplates] = useState<AnalysisTemplate[]>([])
  const [templateId, setTemplateId] = useState("")
  const [analysisContent, setAnalysisContent] = useState("")
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<string | null>(null)

  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      const health = await kbHealth()
      if (cancelled) return
      setOnline(Boolean(health))
      if (health) {
        const t = await analysisTemplates()
        if (cancelled) return
        setTemplates(t)
        if (t.length && !templateId) setTemplateId(t[0].id)
      }
    }
    check()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleTranscribe = async () => {
    if (!audioFile || transcribing) return
    setError(null)
    setTranscript(null)
    setTranscribing(true)
    try {
      const res = await ingestAudio({
        file: audioFile,
        language: audioLang.trim() || undefined,
      })
      setTranscript(res.transcript)
      // Offer the transcript as analysis input.
      setAnalysisContent(res.transcript)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setTranscribing(false)
    }
  }

  const handleImport = async () => {
    if (!dbPath.trim() || importing) return
    setError(null)
    setImportMsg(null)
    setImporting(true)
    try {
      const res = await meetilyImport({ dbPath: dbPath.trim() })
      const total = res.meetings.reduce((acc, m) => acc + m.chunks, 0)
      setImportMsg(
        `Importate ${res.meetings.length} riunioni (${total} chunk indicizzati).`,
      )
      await kbStats()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setImporting(false)
    }
  }

  const handleAnalyze = async () => {
    if (!analysisContent.trim() || !templateId || analyzing) return
    setError(null)
    setAnalysisResult(null)
    setAnalyzing(true)
    try {
      const res = await analysisRun({
        content: analysisContent,
        templateId,
      })
      setAnalysisResult(res.markdown)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setAnalyzing(false)
    }
  }

  if (online === false) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center">
        <Mic className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">Meetily non disponibile</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Avvia il sidecar locale per trascrivere riunioni, importare Meetily e
          generare analisi:
        </p>
        <code className="mt-2 inline-block rounded bg-muted px-2 py-1 text-xs">
          cd kb &amp;&amp; source .venv/bin/activate &amp;&amp; uvicorn app.main:app --port 8077
        </code>
      </div>
    )
  }

  const tabs: { id: Tab; label: string; icon: typeof Mic }[] = [
    { id: "audio", label: "Trascrivi audio", icon: FileAudio },
    { id: "import", label: "Importa Meetily", icon: Import },
    { id: "analysis", label: "Analisi", icon: Sparkles },
  ]

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Mic className="h-4 w-4 text-foreground" />
          <span className="text-sm font-medium text-foreground">Riunioni &amp; Meetily</span>
        </div>
        <span className="text-xs text-muted-foreground">
          {online ? "sidecar online" : "…"}
        </span>
      </div>

      <div className="flex gap-1 border-b border-border bg-muted/10 px-3 py-2">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              tab === id
                ? "bg-background text-foreground"
                : "text-muted-foreground hover:bg-muted/50",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      <div className="p-4">
        {error && (
          <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </p>
        )}

        {tab === "audio" && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Carica un file audio/video di una riunione: viene trascritto in
              locale (whisper.cpp / faster-whisper) e indicizzato nella KB.
            </p>
            <input
              ref={audioInputRef}
              type="file"
              accept="audio/*,video/*"
              className="hidden"
              onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                onClick={() => audioInputRef.current?.click()}
              >
                <FileAudio className="mr-1.5 h-3.5 w-3.5" />
                {audioFile ? "Cambia file" : "Scegli file"}
              </Button>
              {audioFile && (
                <span className="max-w-[220px] truncate text-xs text-muted-foreground">
                  {audioFile.name}
                </span>
              )}
              <div className="flex items-center gap-1">
                <label className="text-xs text-muted-foreground">Lingua</label>
                <Input
                  value={audioLang}
                  onChange={(e) => setAudioLang(e.target.value)}
                  placeholder="it"
                  className="h-8 w-16 text-xs"
                />
              </div>
              <Button
                size="sm"
                className="h-8 text-xs"
                onClick={handleTranscribe}
                disabled={!audioFile || transcribing}
              >
                {transcribing ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    Trascrivo…
                  </>
                ) : (
                  <>
                    <Mic className="mr-1.5 h-3.5 w-3.5" />
                    Trascrivi
                  </>
                )}
              </Button>
            </div>
            {transcript && (
              <div className="rounded-md border border-border bg-muted/20">
                <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
                  <span className="text-xs font-medium text-foreground">
                    Trascrizione (indicizzata nella KB)
                  </span>
                  <button
                    type="button"
                    className="text-xs text-sky-600 hover:underline dark:text-sky-400"
                    onClick={() => {
                      setAnalysisContent(transcript)
                      setTab("analysis")
                    }}
                  >
                    Usa per analisi →
                  </button>
                </div>
                <ScrollArea className="h-[200px]">
                  <pre className="whitespace-pre-wrap p-3 text-xs text-foreground/80">
                    {transcript}
                  </pre>
                </ScrollArea>
              </div>
            )}
          </div>
        )}

        {tab === "import" && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Importa un database Meetily esistente (<code>meeting_minutes.sqlite</code>).
              Indica il percorso assoluto del file sul computer dove gira il
              sidecar.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                value={dbPath}
                onChange={(e) => setDbPath(e.target.value)}
                placeholder="/percorso/a/meeting_minutes.sqlite"
                className="h-8 flex-1 text-xs"
              />
              <Button
                size="sm"
                className="h-8 text-xs"
                onClick={handleImport}
                disabled={!dbPath.trim() || importing}
              >
                {importing ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    Importo…
                  </>
                ) : (
                  <>
                    <Database className="mr-1.5 h-3.5 w-3.5" />
                    Importa
                  </>
                )}
              </Button>
            </div>
            {importMsg && (
              <p className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-600 dark:text-emerald-400">
                {importMsg}
              </p>
            )}
          </div>
        )}

        {tab === "analysis" && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Genera un&apos;analisi strutturata (verbale, action item, ecc.) da una
              trascrizione o documento, usando i template stile Meetily.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs text-muted-foreground">Template</label>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className="h-8 rounded-md border border-border bg-background px-2 text-xs"
              >
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name || t.id}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                className="h-8 text-xs"
                onClick={handleAnalyze}
                disabled={!analysisContent.trim() || !templateId || analyzing}
              >
                {analyzing ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    Analizzo…
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                    Genera
                  </>
                )}
              </Button>
            </div>
            <textarea
              value={analysisContent}
              onChange={(e) => setAnalysisContent(e.target.value)}
              placeholder="Incolla qui la trascrizione o il testo da analizzare…"
              className="h-32 w-full rounded-md border border-border bg-background p-2 text-xs"
            />
            {analysisResult && (
              <div className="rounded-md border border-border bg-muted/20 p-3">
                <MarkdownPreview markdown={analysisResult} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
