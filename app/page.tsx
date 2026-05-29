"use client"

import { useState } from "react"
import { FileUploader, type ConversionResult } from "@/components/file-uploader"
import { MarkdownPreview } from "@/components/markdown-preview"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FileText, Code, Download, Copy, Check, Archive, ChevronDown } from "lucide-react"
import { FaqSection } from "@/components/faq-section"
import { ScrollArea } from "@/components/ui/scroll-area"
import { GitHubStarButton } from "@/components/github-star-button"
import {
  FORMAT_META,
  buildExportBlob,
  withExtension,
  type ExportFormat,
} from "@/lib/export"

const EXPORT_FORMATS: ExportFormat[] = ["md", "txt", "docx"]

export default function Home() {
  const [results, setResults] = useState<ConversionResult[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [isConverting, setIsConverting] = useState(false)
  const [copied, setCopied] = useState(false)

  const selected = results[selectedIndex] ?? null

  const handleCopy = async () => {
    if (!selected) return
    await navigator.clipboard.writeText(selected.markdown)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const downloadBlob = (blob: Blob, filename: string) => {
    const element = document.createElement("a")
    element.href = URL.createObjectURL(blob)
    element.download = filename
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
    URL.revokeObjectURL(element.href)
  }

  const handleDownload = async (format: ExportFormat) => {
    if (!selected) return
    const blob = await buildExportBlob(selected.markdown, format)
    downloadBlob(blob, withExtension(selected.name, FORMAT_META[format].extension))
  }

  const handleDownloadAll = async (format: ExportFormat) => {
    if (results.length === 0) return
    const { default: JSZip } = await import("jszip")
    const zip = new JSZip()
    const used = new Map<string, number>()
    const { extension } = FORMAT_META[format]
    for (const result of results) {
      let filename = withExtension(result.name, extension)
      // Avoid collisions when multiple PDFs share a name
      const count = used.get(filename) ?? 0
      used.set(filename, count + 1)
      if (count > 0) {
        filename = filename.replace(new RegExp(`\\${extension}$`), `-${count}${extension}`)
      }
      const blob = await buildExportBlob(result.markdown, format)
      zip.file(filename, blob)
    }
    const blob = await zip.generateAsync({ type: "blob" })
    downloadBlob(blob, "pdf2md-export.zip")
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="container mx-auto py-16 px-4 max-w-3xl">
        {/* Header */}
        <header className="mb-16">
          <div className="flex flex-col items-center text-center">
            <div className="inline-flex items-center px-3 py-1 mb-6 rounded-full text-xs font-medium text-muted-foreground border border-border">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-2" />
              Browser-based conversion
            </div>

            <h1 className="text-4xl font-semibold tracking-tight text-foreground mb-3">
              PDF to Markdown
            </h1>

            <p className="text-base text-muted-foreground max-w-md mb-8">
              Convert PDF documents to clean Markdown. Files are processed locally in your browser.
            </p>

            <div className="flex items-center gap-3">
              <Button
                className="h-9 px-4 text-sm font-medium"
                onClick={() => {
                  document.querySelector('#file-uploader')?.scrollIntoView({ behavior: 'smooth' })
                }}
              >
                Convert PDF
              </Button>
              <GitHubStarButton />
            </div>
          </div>
        </header>

        {/* File Uploader */}
        <section className="mb-12" id="file-uploader">
          <FileUploader
            onConversionComplete={(newResults) => {
              setResults(newResults)
              setSelectedIndex(0)
            }}
            isConverting={isConverting}
            setIsConverting={setIsConverting}
          />
        </section>

        {/* Result */}
        {selected && (
          <section className="mb-16">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-lg font-medium text-foreground">
                  {results.length > 1 ? `Results (${results.length})` : "Result"}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {selected.name.replace(/\.pdf$/i, '')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopy}
                  className="h-8 px-3 text-sm"
                >
                  {copied ? (
                    <>
                      <Check className="mr-1.5 h-3.5 w-3.5" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="mr-1.5 h-3.5 w-3.5" />
                      Copy
                    </>
                  )}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" className="h-8 px-3 text-sm">
                      <Download className="mr-1.5 h-3.5 w-3.5" />
                      Download
                      <ChevronDown className="ml-1 h-3.5 w-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {EXPORT_FORMATS.map((format) => (
                      <DropdownMenuItem key={format} onSelect={() => handleDownload(format)}>
                        {FORMAT_META[format].label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
                {results.length > 1 && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline" size="sm" className="h-8 px-3 text-sm">
                        <Archive className="mr-1.5 h-3.5 w-3.5" />
                        Download all (.zip)
                        <ChevronDown className="ml-1 h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {EXPORT_FORMATS.map((format) => (
                        <DropdownMenuItem key={format} onSelect={() => handleDownloadAll(format)}>
                          {FORMAT_META[format].label}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            </div>

            {results.length > 1 && (
              <div className="mb-4 flex flex-wrap gap-2">
                {results.map((result, index) => (
                  <button
                    key={`${result.name}-${index}`}
                    type="button"
                    onClick={() => setSelectedIndex(index)}
                    className={`max-w-[200px] truncate rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                      index === selectedIndex
                        ? "border-foreground/30 bg-muted text-foreground"
                        : "border-border text-muted-foreground hover:bg-muted/50"
                    }`}
                    title={result.name}
                  >
                    {result.name.replace(/\.pdf$/i, '')}
                  </button>
                ))}
              </div>
            )}

            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <Tabs defaultValue="preview" className="w-full">
                <TabsList className="flex h-10 items-center gap-1 px-3 border-b border-border bg-muted/30 rounded-none justify-start">
                  <TabsTrigger
                    value="preview"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=inactive]:text-muted-foreground transition-colors"
                  >
                    <FileText className="h-3.5 w-3.5" />
                    Preview
                  </TabsTrigger>
                  <TabsTrigger
                    value="markdown"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=inactive]:text-muted-foreground transition-colors"
                  >
                    <Code className="h-3.5 w-3.5" />
                    Markdown
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="preview" className="p-5">
                  <MarkdownPreview markdown={selected.markdown} />
                </TabsContent>
                <TabsContent value="markdown">
                  <ScrollArea className="h-[500px] w-full">
                    <div className="p-5">
                      <pre className="text-sm font-mono text-foreground/80 overflow-x-auto">
                        <code className="whitespace-pre-wrap [overflow-wrap:anywhere]">{selected.markdown}</code>
                      </pre>
                    </div>
                  </ScrollArea>
                </TabsContent>
              </Tabs>
            </div>
          </section>
        )}

        {/* FAQ */}
        <section className="mb-16">
          <FaqSection />
        </section>

        {/* Footer */}
        <footer className="text-center text-sm text-muted-foreground border-t border-border pt-8">
          <div className="flex justify-center mb-3">
            <GitHubStarButton />
          </div>
          <p>
            Built by{" "}
            <a
              href="https://twitter.com/michael_chomsky"
              target="_blank"
              rel="noopener noreferrer"
              className="text-foreground hover:underline underline-offset-4"
            >
              @michael_chomsky
            </a>
          </p>
        </footer>
      </div>
    </main>
  )
}
