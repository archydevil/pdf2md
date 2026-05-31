"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Database, Send, Loader2, MessageSquare, Cloud, HardDrive, Settings } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  kbChat,
  kbHealth,
  kbStats,
  type KBCitation,
} from "@/lib/kb-client"

interface ChatTurn {
  role: "user" | "assistant"
  content: string
  citations?: KBCitation[]
}

function mapKbChatError(
  err: unknown,
  provider: "local" | "cloud",
  cloudBaseUrl: string,
  cloudApiKey: string,
): string {
  const message = err instanceof Error ? err.message : String(err)

  if (provider === "cloud") {
    const is401 = message.includes("(401)") || message.toLowerCase().includes("unauthorized")
    const is403 = message.includes("(403)")
    const isGoogleEndpoint = cloudBaseUrl.includes("generativelanguage.googleapis.com")
    const isAQToken = cloudApiKey.trim().startsWith("AQ.Ab")

    if (is401 && isGoogleEndpoint && isAQToken) {
      return "Errore cloud 401: token Google AQ.Ab non valido o scaduto. Rigenera il token e incollalo di nuovo nelle impostazioni Cloud."
    }

    if (is401) {
      return "Errore cloud 401: API key/token non valido o scaduto. Controlla endpoint, credenziali e modello selezionato."
    }

    if (is403) {
      return "Errore cloud 403: egress bloccato dal sidecar (privacy). Abilita l'egress cloud o usa la modalità Locale."
    }
  }

  return err instanceof Error ? `Errore: ${err.message}` : "Errore durante la richiesta alla KB."
}

export function KbChat() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [chunks, setChunks] = useState<number | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [provider, setProvider] = useState<"local" | "cloud">("local")
  const [showSettings, setShowSettings] = useState(false)
  const [cloudBaseUrl, setCloudBaseUrl] = useState("https://api.openai.com/v1")
  const [cloudApiKey, setCloudApiKey] = useState("")
  const [cloudModel, setCloudModel] = useState("gpt-4o-mini")
  const scrollRef = useRef<HTMLDivElement>(null)
  const hydrated = useRef(false)

  // Load persisted cloud settings (local only; not sent anywhere but the local sidecar).
  useEffect(() => {
    try {
      const raw = localStorage.getItem("kb-cloud-settings")
      if (raw) {
        const s = JSON.parse(raw)
        if (s.baseUrl) setCloudBaseUrl(s.baseUrl)
        if (s.model) setCloudModel(s.model)
        if (s.apiKey) setCloudApiKey(s.apiKey)
        if (s.provider === "cloud") setProvider("cloud")
      }
    } catch {
      // ignore malformed storage
    } finally {
      hydrated.current = true
    }
  }, [])

  useEffect(() => {
    // Skip the first run (before hydration) so we never overwrite a stored key
    // with the default empty value, e.g. when a second tab is open.
    if (!hydrated.current) return
    try {
      const prev = (() => {
        try {
          return JSON.parse(localStorage.getItem("kb-cloud-settings") || "{}")
        } catch {
          return {}
        }
      })()
      localStorage.setItem(
        "kb-cloud-settings",
        JSON.stringify({
          baseUrl: cloudBaseUrl,
          model: cloudModel,
          // Never clobber a saved key with an empty one (another tab may hold it).
          apiKey: cloudApiKey || prev.apiKey || "",
          provider,
        }),
      )
    } catch {
      // ignore storage quota / disabled storage
    }
  }, [cloudBaseUrl, cloudModel, cloudApiKey, provider])

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      const health = await kbHealth()
      if (cancelled) return
      setOnline(Boolean(health))
      if (health) {
        const stats = await kbStats()
        if (!cancelled) setChunks(stats?.chunks ?? null)
      }
    }
    check()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [turns, loading])

  const handleAsk = async () => {
    const query = input.trim()
    if (!query || loading) return
    setInput("")
    setTurns((prev) => [...prev, { role: "user", content: query }])
    setLoading(true)
    try {
      const res = await kbChat({
        query,
        rerank: true,
        provider,
        ...(provider === "cloud"
          ? {
              cloudBaseUrl: cloudBaseUrl.trim() || undefined,
              cloudApiKey: cloudApiKey.trim() || undefined,
              model: cloudModel.trim() || undefined,
            }
          : {}),
      })
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, citations: res.citations },
      ])
      const stats = await kbStats()
      setChunks(stats?.chunks ?? null)
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: mapKbChatError(err, provider, cloudBaseUrl, cloudApiKey),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (online === false) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/20 p-6 text-center">
        <Database className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">Knowledge Base non attiva</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Avvia il sidecar locale per interrogare i documenti:
        </p>
        <code className="mt-2 inline-block rounded bg-muted px-2 py-1 text-xs">
          cd kb &amp;&amp; source .venv/bin/activate &amp;&amp; uvicorn app.main:app --port 8077
        </code>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-muted/30 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-foreground" />
          <span className="text-sm font-medium text-foreground">Chiedi alla Knowledge Base</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <button
            type="button"
            onClick={() => setProvider((p) => (p === "local" ? "cloud" : "local"))}
            title={
              provider === "local"
                ? "Modello locale (Ollama). Clicca per usare il cloud."
                : "Modello cloud. Inserisci una API key nelle impostazioni; le PII vengono anonimizzate prima dell'invio. Clicca per tornare locale."
            }
            className={cn(
              "flex items-center gap-1 rounded-full border px-2 py-0.5 transition-colors",
              provider === "cloud"
                ? "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400"
                : "border-border hover:bg-muted",
            )}
          >
            {provider === "cloud" ? (
              <Cloud className="h-3 w-3" />
            ) : (
              <HardDrive className="h-3 w-3" />
            )}
            {provider === "cloud" ? "Cloud" : "Locale"}
          </button>
          {provider === "cloud" && (
            <button
              type="button"
              onClick={() => setShowSettings((s) => !s)}
              title="Impostazioni cloud (endpoint, API key, modello)"
              className={cn(
                "flex items-center rounded-full border px-1.5 py-0.5 transition-colors",
                showSettings
                  ? "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400"
                  : "border-border hover:bg-muted",
              )}
            >
              <Settings className="h-3 w-3" />
            </button>
          )}
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              online ? "bg-green-500" : "bg-muted-foreground",
            )}
          />
          {chunks !== null ? `${chunks} chunk` : online ? "online" : "…"}
        </div>
      </div>

      {provider === "cloud" && showSettings && (
        <div className="space-y-2 border-b border-border bg-muted/20 px-4 py-3">
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => {
                setCloudBaseUrl("https://api.openai.com/v1")
                setCloudModel("gpt-4o-mini")
              }}
              className="rounded-md border border-border px-2 py-0.5 text-[11px] hover:bg-muted"
            >
              OpenAI
            </button>
            <button
              type="button"
              onClick={() => {
                setCloudBaseUrl("https://api.anthropic.com")
                setCloudModel("claude-3-5-sonnet-20241022")
              }}
              className="rounded-md border border-border px-2 py-0.5 text-[11px] hover:bg-muted"
            >
              Anthropic (Claude)
            </button>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              Endpoint (OpenAI o Anthropic)
            </label>
            <Input
              value={cloudBaseUrl}
              onChange={(e) => setCloudBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
              className="h-8 text-xs"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">API key</label>
            <Input
              type="password"
              value={cloudApiKey}
              onChange={(e) => setCloudApiKey(e.target.value)}
              placeholder="sk-…"
              autoComplete="off"
              className="h-8 text-xs"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Modello</label>
            <Input
              value={cloudModel}
              onChange={(e) => setCloudModel(e.target.value)}
              placeholder="gpt-4o-mini"
              className="h-8 text-xs"
            />
          </div>
          <p className="text-[11px] leading-snug text-muted-foreground">
            Le credenziali restano nel browser e vengono inviate solo al sidecar
            locale. Le PII vengono anonimizzate prima dell&apos;invio al cloud.
          </p>
        </div>
      )}

      <ScrollArea className="h-[360px] w-full">
        <div ref={scrollRef} className="flex flex-col gap-4 p-4">
          {turns.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Fai una domanda sui documenti che hai inviato alla KB. Le risposte
              citano le fonti con riferimenti numerati.
            </p>
          )}
          {turns.map((turn, i) => (
            <div
              key={i}
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                turn.role === "user"
                  ? "self-end bg-foreground text-background"
                  : "self-start bg-muted text-foreground",
              )}
            >
              <p className="whitespace-pre-wrap break-words">{turn.content}</p>
              {turn.citations && turn.citations.length > 0 && (
                <div className="mt-2 space-y-1 border-t border-border/50 pt-2">
                  {turn.citations.map((c) => (
                    <div key={c.n} className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">[{c.n}]</span>{" "}
                      {c.file_name}
                      {c.section_path.length > 0 && ` · ${c.section_path.join(" > ")}`}
                      {c.page != null && ` · p.${c.page}`}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="self-start flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Sto cercando nei documenti…
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="flex items-center gap-2 border-t border-border p-3">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              handleAsk()
            }
          }}
          placeholder="Es. quanti giorni di ferie ho?"
          disabled={loading}
          className="h-9 text-sm"
        />
        <Button
          size="sm"
          onClick={handleAsk}
          disabled={loading || !input.trim()}
          className="h-9 px-3"
        >
          <Send className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
