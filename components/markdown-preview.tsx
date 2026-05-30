"use client"
import { ScrollArea } from "@/components/ui/scroll-area"
import ReactMarkdown, { defaultUrlTransform } from "react-markdown"
import remarkGfm from "remark-gfm"
import { cn } from "@/lib/utils"

interface MarkdownPreviewProps {
  markdown: string
  className?: string
}

/**
 * Allow inline base64 images (extracted from PDFs) while keeping react-markdown's
 * default URL sanitization for every other attribute (links, etc.).
 */
function urlTransform(url: string, key: string, node: { tagName?: string }): string {
  if (key === "src" && node.tagName === "img" && url.startsWith("data:image/")) {
    return url
  }
  return defaultUrlTransform(url)
}

export function MarkdownPreview({ markdown, className }: MarkdownPreviewProps) {
  return (
    <ScrollArea className="h-[500px] w-full">
      <div className={cn("prose prose-sm dark:prose-invert max-w-none break-words", className)}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          urlTransform={urlTransform}
          components={{
            pre: ({ ...props }) => (
              <pre
                {...props}
                className="overflow-x-auto p-4 bg-muted rounded text-sm [overflow-wrap:anywhere]"
              />
            ),
            code: ({ inline, ...props }: { inline?: boolean; className?: string; children?: React.ReactNode }) => (
              <code
                {...props}
                className={cn(
                  "text-sm",
                  inline
                    ? "bg-muted px-1 py-0.5 rounded"
                    : "block overflow-x-auto [overflow-wrap:anywhere]"
                )}
              />
            ),
            table: ({ children }) => (
              <div className="my-4 overflow-x-auto">
                <table className="min-w-full border-collapse border border-border">
                  {children}
                </table>
              </div>
            ),
            th: ({ children }) => (
              <th className="border border-border bg-muted px-3 py-2 text-left text-sm font-medium">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="border border-border px-3 py-2 text-sm">
                {children}
              </td>
            ),
            img: ({ src, alt }) => {
              const url = typeof src === "string" && src ? src : null
              if (!url) return null
              // Native <img> handles arbitrary data: URLs from extracted PDF
              // images better than next/image (which warns on empty/long URLs).
              // eslint-disable-next-line @next/next/no-img-element
              return <img src={url} alt={alt || ""} className="max-w-full h-auto rounded" />
            },
            p: ({ children }) => (
              <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] leading-relaxed">{children}</p>
            ),
            a: ({ href, children }) => (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-foreground underline underline-offset-4 hover:text-muted-foreground transition-colors"
              >
                {children}
              </a>
            ),
            h1: ({ children }) => (
              <h1 className="text-xl font-semibold mt-6 mb-3 first:mt-0">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-lg font-semibold mt-5 mb-2">{children}</h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-base font-semibold mt-4 mb-2">{children}</h3>
            ),
          }}
        >
          {markdown}
        </ReactMarkdown>
      </div>
    </ScrollArea>
  )
}
