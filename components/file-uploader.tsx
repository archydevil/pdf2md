"use client"

import type React from "react"
import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Upload, File as FileIcon, AlertCircle, CheckCircle2, Loader2, X } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { Checkbox } from "@/components/ui/checkbox"
import { usePdf2md } from "@/hooks/use-pdf2md"

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

export interface ConversionResult {
  name: string
  markdown: string
}

type ItemStatus = "pending" | "converting" | "done" | "error"

interface FileItem {
  id: string
  file: File
  status: ItemStatus
  markdown?: string
  error?: string
}

interface FileUploaderProps {
  onConversionComplete: (results: ConversionResult[]) => void
  isConverting: boolean
  setIsConverting: (isConverting: boolean) => void
}

export function FileUploader({ onConversionComplete, isConverting, setIsConverting }: FileUploaderProps) {
  const [dragActive, setDragActive] = useState(false)
  const [items, setItems] = useState<FileItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [includeImages, setIncludeImages] = useState(false)
  const [includeAnnotations, setIncludeAnnotations] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const { ready, loadError, convert } = usePdf2md()

  const addFiles = (fileList: FileList | File[]) => {
    setError(null)
    const incoming = Array.from(fileList)
    const accepted: FileItem[] = []
    const rejected: string[] = []

    for (const file of incoming) {
      if (file.type !== "application/pdf") {
        rejected.push(`${file.name}: not a PDF`)
        continue
      }
      if (file.size > MAX_FILE_SIZE) {
        rejected.push(`${file.name}: exceeds 10MB`)
        continue
      }
      accepted.push({
        id: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
        file,
        status: "pending",
      })
    }

    if (rejected.length > 0) {
      setError(`Skipped ${rejected.length} file(s): ${rejected.join(", ")}`)
    }

    if (accepted.length > 0) {
      setItems((prev) => [...prev, ...accepted])
    }
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files)
    }
    // Reset so selecting the same file again re-triggers change
    e.target.value = ""
  }

  const removeItem = (id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id))
  }

  const clearAll = () => {
    setItems([])
    setError(null)
  }

  const handleConvert = async () => {
    if (!ready || items.length === 0 || isConverting) return

    setIsConverting(true)
    setError(null)

    // Reset statuses for a fresh run
    setItems((prev) =>
      prev.map((item) => ({ ...item, status: "pending", markdown: undefined, error: undefined })),
    )

    const results: ConversionResult[] = []

    for (const item of items) {
      setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, status: "converting" } : it)))
      try {
        const markdown = await convert(item.file, { includeImages, includeAnnotations })
        results.push({ name: item.file.name, markdown })
        setItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, status: "done", markdown } : it)))
      } catch (err) {
        console.error("Error converting PDF:", err)
        setItems((prev) =>
          prev.map((it) =>
            it.id === item.id
              ? { ...it, status: "error", error: "Conversion failed (corrupted or unsupported file)." }
              : it,
          ),
        )
      }
    }

    setIsConverting(false)

    if (results.length > 0) {
      onConversionComplete(results)
    } else {
      setError("None of the files could be converted.")
    }
  }

  const doneCount = items.filter((i) => i.status === "done").length
  const hasPending = items.some((i) => i.status === "pending")

  return (
    <>
      {(error || loadError) && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{loadError ?? error}</AlertDescription>
        </Alert>
      )}

      <div
        className={`
          relative rounded-lg border border-dashed p-8 text-center transition-colors
          ${dragActive
            ? "border-foreground/30 bg-muted/50"
            : "border-border hover:border-foreground/20 hover:bg-muted/30"
          }
        `}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center justify-center gap-3">
          <div className="rounded-full bg-muted p-2.5">
            <Upload className="h-5 w-5 text-muted-foreground" />
          </div>

          <div>
            <p className="text-sm font-medium text-foreground mb-1">
              Drop your PDFs here
            </p>
            <p className="text-sm text-muted-foreground">
              or click to browse — you can select multiple files
            </p>
          </div>

          {!isConverting && (
            <div className="flex gap-2 mt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => inputRef.current?.click()}
                className="h-8 px-3 text-sm"
              >
                Select files
              </Button>

              {items.length > 0 && ready && hasPending && (
                <Button size="sm" onClick={handleConvert} className="h-8 px-3 text-sm">
                  Convert {items.length > 1 ? `${items.length} files` : "file"}
                </Button>
              )}
            </div>
          )}

          {isConverting && (
            <div className="w-full max-w-xs mt-2">
              <Progress value={items.length ? (doneCount / items.length) * 100 : 0} className="h-1.5" />
              <p className="text-xs text-muted-foreground mt-2">
                Converting {Math.min(doneCount + 1, items.length)} of {items.length}...
              </p>
            </div>
          )}

          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            aria-label="Upload PDF files"
            onChange={handleChange}
          />
        </div>

        {!isConverting && (
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 border-t border-border pt-4">
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
              <Checkbox
                checked={includeImages}
                onCheckedChange={(checked) => setIncludeImages(checked === true)}
              />
              Include images
            </label>
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
              <Checkbox
                checked={includeAnnotations}
                onCheckedChange={(checked) => setIncludeAnnotations(checked === true)}
              />
              Include form fields &amp; annotations
            </label>
          </div>
        )}
      </div>

      {/* File queue */}
      {items.length > 0 && (
        <div className="mt-4 rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
            <p className="text-sm font-medium text-foreground">
              {items.length} file{items.length > 1 ? "s" : ""}
              {doneCount > 0 && (
                <span className="text-muted-foreground font-normal"> · {doneCount} converted</span>
              )}
            </p>
            {!isConverting && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAll}
                className="h-7 px-2 text-xs text-muted-foreground"
              >
                Clear all
              </Button>
            )}
          </div>
          <ul className="divide-y divide-border">
            {items.map((item) => (
              <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
                <FileIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate text-sm text-foreground">{item.file.name}</span>
                {item.status === "converting" && (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                )}
                {item.status === "done" && <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />}
                {item.status === "error" && (
                  <span className="shrink-0 text-xs text-destructive">Failed</span>
                )}
                {item.status === "pending" && !isConverting && (
                  <button
                    type="button"
                    onClick={() => removeItem(item.id)}
                    className="shrink-0 text-muted-foreground hover:text-foreground"
                    aria-label={`Remove ${item.file.name}`}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
