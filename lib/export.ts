import type { ISectionOptions } from "docx"

export type ExportFormat = "md" | "txt" | "docx"

export const FORMAT_META: Record<ExportFormat, { label: string; extension: string; mime: string }> = {
  md: { label: "Markdown (.md)", extension: ".md", mime: "text/markdown" },
  txt: { label: "Plain text (.txt)", extension: ".txt", mime: "text/plain" },
  docx: {
    label: "Word (.docx)",
    extension: ".docx",
    mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  },
}

/** Replace the .pdf (or any) extension of the source name with the target one. */
export function withExtension(name: string, extension: string): string {
  return name.replace(/\.[^./\\]+$/i, "") + extension
}

/** Strip the most common Markdown syntax to produce readable plain text. */
export function markdownToPlainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, (block) => block.replace(/```[^\n]*\n?/g, "").replace(/```$/g, ""))
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "• ")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/~~(.*?)~~/g, "$2")
    .replace(/^\s*([-*_]\s?){3,}\s*$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

interface InlineToken {
  text: string
  bold?: boolean
  italics?: boolean
  code?: boolean
}

/** Parse inline Markdown emphasis/code into styled runs. */
function parseInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = []
  // Strip links/images down to their visible text first.
  const cleaned = text
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")

  const regex = /(\*\*|__)(.+?)\1|(\*|_)(.+?)\3|`([^`]+)`/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(cleaned)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ text: cleaned.slice(lastIndex, match.index) })
    }
    if (match[1]) {
      tokens.push({ text: match[2], bold: true })
    } else if (match[3]) {
      tokens.push({ text: match[4], italics: true })
    } else if (match[5]) {
      tokens.push({ text: match[5], code: true })
    }
    lastIndex = regex.lastIndex
  }

  if (lastIndex < cleaned.length) {
    tokens.push({ text: cleaned.slice(lastIndex) })
  }

  return tokens.length > 0 ? tokens : [{ text: cleaned }]
}

/** Convert a Markdown string to a .docx Blob using the `docx` library. */
export async function markdownToDocxBlob(markdown: string): Promise<Blob> {
  const { Document, Packer, Paragraph, TextRun, HeadingLevel } = await import("docx")

  const headingLevels = [
    HeadingLevel.HEADING_1,
    HeadingLevel.HEADING_2,
    HeadingLevel.HEADING_3,
    HeadingLevel.HEADING_4,
    HeadingLevel.HEADING_5,
    HeadingLevel.HEADING_6,
  ]

  const lines = markdown.replace(/\r\n/g, "\n").split("\n")
  const paragraphs: Paragraph[] = []
  let inCodeBlock = false

  const toRuns = (text: string) =>
    parseInline(text).map(
      (token) =>
        new TextRun({
          text: token.text,
          bold: token.bold,
          italics: token.italics,
          font: token.code ? "Courier New" : undefined,
        }),
    )

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/g, "")

    if (/^```/.test(line.trim())) {
      inCodeBlock = !inCodeBlock
      continue
    }

    if (inCodeBlock) {
      paragraphs.push(
        new Paragraph({
          children: [new TextRun({ text: rawLine, font: "Courier New" })],
        }),
      )
      continue
    }

    if (line.trim() === "") {
      paragraphs.push(new Paragraph({ children: [] }))
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      paragraphs.push(
        new Paragraph({
          heading: headingLevels[heading[1].length - 1],
          children: toRuns(heading[2]),
        }),
      )
      continue
    }

    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line)
    if (bullet) {
      paragraphs.push(new Paragraph({ bullet: { level: 0 }, children: toRuns(bullet[1]) }))
      continue
    }

    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    if (numbered) {
      paragraphs.push(
        new Paragraph({ numbering: { reference: "md-numbering", level: 0 }, children: toRuns(numbered[1]) }),
      )
      continue
    }

    const quote = /^\s*>\s?(.*)$/.exec(line)
    if (quote) {
      paragraphs.push(new Paragraph({ style: "IntenseQuote", children: toRuns(quote[1]) }))
      continue
    }

    if (/^\s*([-*_]\s?){3,}\s*$/.test(line)) {
      paragraphs.push(new Paragraph({ thematicBreak: true, children: [] }))
      continue
    }

    paragraphs.push(new Paragraph({ children: toRuns(line) }))
  }

  const section: ISectionOptions = { children: paragraphs }

  const doc = new Document({
    numbering: {
      config: [
        {
          reference: "md-numbering",
          levels: [{ level: 0, format: "decimal", text: "%1.", alignment: "left" }],
        },
      ],
    },
    sections: [section],
  })

  return Packer.toBlob(doc)
}

/** Build a downloadable Blob for the given Markdown content in the requested format. */
export async function buildExportBlob(markdown: string, format: ExportFormat): Promise<Blob> {
  if (format === "docx") {
    return markdownToDocxBlob(markdown)
  }
  if (format === "txt") {
    return new Blob([markdownToPlainText(markdown)], { type: FORMAT_META.txt.mime })
  }
  return new Blob([markdown], { type: FORMAT_META.md.mime })
}
