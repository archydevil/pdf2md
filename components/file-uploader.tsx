"use client"

import type React from "react"
import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Upload, File, AlertCircle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"

import dynamic from "next/dynamic"

const PDF2MDLoader = dynamic(() => import("@/components/pdf2md-loader"), { ssr: false })

interface FileUploaderProps {
  onConversionComplete: (markdown: string, file: File) => void
  isConverting: boolean
  setIsConverting: (isConverting: boolean) => void
}

export function FileUploader({ onConversionComplete, isConverting, setIsConverting }: FileUploaderProps) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pdf2mdLoaded, setPdf2mdLoaded] = useState(false)
  const [progress, setProgress] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isConverting) {
      setProgress(0)
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev < 90) {
            return prev + 1
          }
          return prev
        })
      }, 100)

      return () => clearInterval(interval)
    }
  }, [isConverting])

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
    setError(null)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      if (file.type === "application/pdf") {
        handleFile(file)
      } else {
        setError("Please upload a PDF file")
      }
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    setError(null)

    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      if (file.type === "application/pdf") {
        handleFile(file)
      } else {
        setError("Please upload a PDF file")
      }
    }
  }

  const handleFile = (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      setError("File size exceeds 10MB limit")
      return
    }

    setSelectedFile(file)
  }

  const handleConvert = async () => {
    if (!selectedFile || !pdf2mdLoaded) return

    setIsConverting(true)
    setError(null)

    try {
      // Conversion handled by PDF2MDLoader
    } catch (error) {
      console.error("Error converting PDF:", error)
      setError("Failed to convert PDF. Please try a different file.")
      setIsConverting(false)
    }
  }

  return (
    <>
      <PDF2MDLoader
        file={selectedFile}
        isConverting={isConverting}
        onLoad={() => setPdf2mdLoaded(true)}
        onConversionComplete={(markdown) => {
          if (selectedFile) {
            setProgress(100)
            onConversionComplete(markdown, selectedFile)
            setIsConverting(false)
          }
        }}
        onError={(errorMsg) => {
          setError(errorMsg)
          setIsConverting(false)
        }}
      />

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
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
              Drop your PDF here
            </p>
            <p className="text-sm text-muted-foreground">
              or click to browse
            </p>
          </div>

          {selectedFile && (
            <div className="flex items-center gap-2 text-sm text-foreground mt-1">
              <File className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">{selectedFile.name}</span>
            </div>
          )}

          {isConverting ? (
            <div className="w-full max-w-xs mt-2">
              <Progress value={progress} className="h-1.5" />
              <p className="text-xs text-muted-foreground mt-2">Converting... {progress}%</p>
            </div>
          ) : (
            <div className="flex gap-2 mt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => inputRef.current?.click()}
                disabled={isConverting}
                className="h-8 px-3 text-sm"
              >
                Select file
              </Button>

              {selectedFile && pdf2mdLoaded && (
                <Button
                  size="sm"
                  onClick={handleConvert}
                  disabled={isConverting}
                  className="h-8 px-3 text-sm"
                >
                  Convert
                </Button>
              )}
            </div>
          )}

          <input ref={inputRef} type="file" accept=".pdf" className="hidden" onChange={handleChange} />
        </div>
      </div>
    </>
  )
}
