"use client"

import { useEffect, useRef, useState } from "react"

/**
 * Loads the @opendocsg/pdf2md library on the client and exposes a `convert`
 * helper that turns a PDF File into a Markdown string.
 */
export function usePdf2md() {
  const [ready, setReady] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const pdf2mdRef = useRef<((buffer: Uint8Array) => Promise<string>) | null>(null)

  useEffect(() => {
    let mounted = true

    import("@opendocsg/pdf2md")
      .then((mod) => {
        if (!mounted) return
        pdf2mdRef.current = mod.default
        setReady(true)
      })
      .catch((error) => {
        console.error("Failed to load pdf2md library:", error)
        if (mounted) {
          setLoadError("Failed to load conversion library. Please try again later.")
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  const convert = async (file: File): Promise<string> => {
    if (!pdf2mdRef.current) {
      throw new Error("Conversion library is not loaded yet.")
    }
    // pdf.js expects a Uint8Array/Buffer, not a raw ArrayBuffer, otherwise it
    // throws "Invalid PDF structure".
    const buffer = new Uint8Array(await file.arrayBuffer())
    return pdf2mdRef.current(buffer)
  }

  return { ready, loadError, convert }
}
