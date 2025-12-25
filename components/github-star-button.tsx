"use client"

import { Button } from "@/components/ui/button"
import { Github } from "lucide-react"
import { cn } from "@/lib/utils"

interface GitHubStarButtonProps {
  repoUrl?: string
  className?: string
}

export function GitHubStarButton({
  repoUrl = "https://github.com/mrmps/pdf2md",
  className,
}: GitHubStarButtonProps) {
  return (
    <Button
      variant="outline"
      size="sm"
      className={cn("h-9 px-3 text-sm font-medium", className)}
      onClick={() => window.open(repoUrl, "_blank", "noopener,noreferrer")}
    >
      <Github className="h-4 w-4 mr-2" />
      Star on GitHub
    </Button>
  )
}
