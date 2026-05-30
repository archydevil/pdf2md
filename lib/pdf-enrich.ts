/**
 * Optional enrichment of the Markdown produced by pdf2md, addressing two of the
 * converter's limitations:
 *  - embedded raster images (pdf2md drops them entirely);
 *  - form fields, text annotations and comments.
 *
 * Everything runs client-side: images are rebuilt from raw pixels via <canvas>,
 * and annotations are read through pdf.js (exposed by unpdf).
 */

export interface EnrichOptions {
  includeImages?: boolean
  includeAnnotations?: boolean
}

interface ExtractedImage {
  data: Uint8Array | Uint8ClampedArray
  width: number
  height: number
  channels: 1 | 3 | 4
  key: string
}

/** Rebuild a PNG data URL from raw pixel data (grayscale, RGB or RGBA). */
function imageToPngDataUrl(image: ExtractedImage): string | null {
  if (typeof document === "undefined") return null
  const { data, width, height, channels } = image
  const canvas = document.createElement("canvas")
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext("2d")
  if (!ctx) return null

  const rgba = new Uint8ClampedArray(width * height * 4)
  for (let i = 0; i < width * height; i++) {
    if (channels === 1) {
      const v = data[i]
      rgba[i * 4] = v
      rgba[i * 4 + 1] = v
      rgba[i * 4 + 2] = v
      rgba[i * 4 + 3] = 255
    } else if (channels === 3) {
      rgba[i * 4] = data[i * 3]
      rgba[i * 4 + 1] = data[i * 3 + 1]
      rgba[i * 4 + 2] = data[i * 3 + 2]
      rgba[i * 4 + 3] = 255
    } else {
      rgba[i * 4] = data[i * 4]
      rgba[i * 4 + 1] = data[i * 4 + 1]
      rgba[i * 4 + 2] = data[i * 4 + 2]
      rgba[i * 4 + 3] = data[i * 4 + 3]
    }
  }
  ctx.putImageData(new ImageData(rgba, width, height), 0, 0)
  return canvas.toDataURL("image/png")
}

interface PdfAnnotation {
  subtype?: string
  fieldName?: string
  fieldValue?: string | string[]
  contents?: string
  title?: string
  alternativeText?: string
}

function formatAnnotations(annotations: PdfAnnotation[]): string[] {
  const lines: string[] = []
  for (const a of annotations) {
    // Form fields (text inputs, checkboxes, dropdowns, ...)
    if (a.fieldName) {
      const value = Array.isArray(a.fieldValue) ? a.fieldValue.join(", ") : a.fieldValue
      if (value !== undefined && value !== null && String(value).trim() !== "") {
        lines.push(`- **${a.fieldName.trim()}:** ${String(value).trim()}`)
      }
    } else {
      // Text notes / comments / popups
      const text = (a.contents || a.alternativeText || "").trim()
      if (text) {
        const author = a.title?.trim()
        lines.push(author ? `- **${author}:** ${text}` : `- ${text}`)
      }
    }
  }
  return lines
}

/**
 * Produce a Markdown fragment with the extra content (images, form fields,
 * annotations) to append to the pdf2md output. Returns an empty string when
 * nothing extra is found or no option is enabled.
 */
export async function enrichMarkdown(buffer: Uint8Array, options: EnrichOptions): Promise<string> {
  if (!options.includeImages && !options.includeAnnotations) return ""

  const { extractImages, getDocumentProxy, getResolvedPDFJS } = await import("unpdf")
  await getResolvedPDFJS()
  const pdf = await getDocumentProxy(buffer)

  const sections: string[] = []
  const seenImageKeys = new Set<string>()
  const imageRefs: string[] = []
  const annotationLines: string[] = []

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
    if (options.includeImages) {
      try {
        const images = (await extractImages(pdf, pageNumber)) as unknown as ExtractedImage[]
        console.log("[enrich] page", pageNumber, "images:", images?.length, images?.map((i) => ({ w: i.width, h: i.height, ch: i.channels, key: i.key })))
        for (const image of images) {
          if (seenImageKeys.has(image.key)) continue
          seenImageKeys.add(image.key)
          const dataUrl = imageToPngDataUrl(image)
          if (dataUrl) {
            imageRefs.push(`![Image from page ${pageNumber}](${dataUrl})`)
          }
        }
      } catch (e) {
        console.error("[enrich] extractImages failed on page", pageNumber, e)
      }
    }

    if (options.includeAnnotations) {
      try {
        const page = await pdf.getPage(pageNumber)
        const annotations = (await page.getAnnotations()) as PdfAnnotation[]
        annotationLines.push(...formatAnnotations(annotations))
      } catch {
        // Skip pages without readable annotations.
      }
    }
  }

  if (imageRefs.length > 0) {
    sections.push(`## Images\n\n${imageRefs.join("\n\n")}`)
  }
  if (annotationLines.length > 0) {
    sections.push(`## Form fields & annotations\n\n${annotationLines.join("\n")}`)
  }

  return sections.length > 0 ? `\n\n${sections.join("\n\n")}\n` : ""
}
