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

/**
 * Raw image object returned by pdf.js `page.objs.get()`. Depending on the
 * pdf.js build and browser capabilities the pixels are exposed either as a
 * decoded `ImageBitmap` (modern path) or as a raw pixel buffer in `data`.
 */
interface PdfImageObject {
  width: number
  height: number
  bitmap?: ImageBitmap
  data?: Uint8Array | Uint8ClampedArray | null
}

/** Draw an already-decoded ImageBitmap onto a canvas and return a PNG data URL. */
function bitmapToPngDataUrl(bitmap: ImageBitmap, width: number, height: number): string | null {
  if (typeof document === "undefined") return null
  const canvas = document.createElement("canvas")
  canvas.width = width || bitmap.width
  canvas.height = height || bitmap.height
  const ctx = canvas.getContext("2d")
  if (!ctx) return null
  ctx.drawImage(bitmap, 0, 0)
  return canvas.toDataURL("image/png")
}

/** Rebuild a PNG data URL from raw pixel data (grayscale, RGB or RGBA). */
function rawPixelsToPngDataUrl(
  data: Uint8Array | Uint8ClampedArray,
  width: number,
  height: number,
): string | null {
  if (typeof document === "undefined") return null
  const channels = data.length / (width * height)
  if (![1, 3, 4].includes(channels)) return null
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

/** Convert a pdf.js image object (bitmap or raw pixels) to a PNG data URL. */
function imageObjectToPngDataUrl(image: PdfImageObject): string | null {
  if (image.bitmap) {
    return bitmapToPngDataUrl(image.bitmap, image.width, image.height)
  }
  if (image.data) {
    return rawPixelsToPngDataUrl(image.data, image.width, image.height)
  }
  return null
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

  const { getDocumentProxy, getResolvedPDFJS } = await import("unpdf")
  const { OPS } = await getResolvedPDFJS()
  const pdf = await getDocumentProxy(buffer)

  const sections: string[] = []
  const seenImageKeys = new Set<string>()
  const imageRefs: string[] = []
  const annotationLines: string[] = []

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
    const page = await pdf.getPage(pageNumber)

    if (options.includeImages) {
      try {
        const opList = await page.getOperatorList()
        for (let i = 0; i < opList.fnArray.length; i++) {
          const op = opList.fnArray[i]
          if (op !== OPS.paintImageXObject && op !== OPS.paintInlineImageXObject) continue
          const arg = opList.argsArray[i][0]
          // Inline images carry the object directly; XObjects carry a string key.
          let image: PdfImageObject | null = null
          let dedupeKey: string
          if (typeof arg === "string") {
            dedupeKey = arg
            if (seenImageKeys.has(dedupeKey)) continue
            const objs = arg.startsWith("g_") ? page.commonObjs : page.objs
            image = await new Promise<PdfImageObject>((resolve) => objs.get(arg, resolve))
          } else {
            image = arg as PdfImageObject
            dedupeKey = `inline_${pageNumber}_${i}`
          }
          seenImageKeys.add(dedupeKey)
          if (!image) continue
          const dataUrl = imageObjectToPngDataUrl(image)
          if (dataUrl) {
            imageRefs.push(`![Image from page ${pageNumber}](${dataUrl})`)
          }
        }
      } catch {
        // Skip pages whose images cannot be decoded.
      }
    }

    if (options.includeAnnotations) {
      try {
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
