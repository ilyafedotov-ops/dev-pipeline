"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Pause, Play, Download, Search, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { apiClient, useRunLogs } from "@/lib/api"

interface StreamingLogsProps {
  runId: string
}

function splitLines(content: string) {
  const parts = content.split(/\r?\n/)
  const remainder = parts.pop() ?? ""
  return { lines: parts, remainder }
}

export function StreamingLogs({ runId }: StreamingLogsProps) {
  const { data: logData, isLoading } = useRunLogs(runId)
  const [streamState, setStreamState] = useState<{ runId: string; lines: string[]; buffer: string }>(() => ({
    runId,
    lines: [],
    buffer: "",
  }))
  const [isPaused, setIsPaused] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const isTruncated = Boolean(logData?.truncated)
  const scrollRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const streamUrl = useMemo(() => {
    const baseUrl = apiClient.getConfig().baseUrl.replace(/\/$/, "")
    if (baseUrl) {
      return `${baseUrl}/runs/${runId}/logs/stream`
    }
    return `/runs/${runId}/logs/stream`
  }, [runId])
  const parsedLogData = useMemo(() => {
    const content = logData?.content ?? ""
    return splitLines(content)
  }, [logData])
  const effectiveStreamState =
    streamState.runId === runId ? streamState : { runId, lines: [], buffer: "" }

  useEffect(() => {
    if (!isStreaming || isPaused) return

    const source = new EventSource(streamUrl)
    eventSourceRef.current = source

    const handleLogEvent = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as { chunk?: string }
        if (payload.chunk) {
          setStreamState((prev) => {
            const base = prev.runId === runId ? prev : { runId, lines: [], buffer: "" }
            const combined = base.buffer + payload.chunk
            const { lines: chunkLines, remainder } = splitLines(combined)
            return {
              runId,
              lines: chunkLines.length > 0 ? [...base.lines, ...chunkLines] : base.lines,
              buffer: remainder,
            }
          })
        }
      } catch {
        // Ignore malformed chunks
      }
    }

    source.addEventListener("log", handleLogEvent)
    source.addEventListener("error", () => {
      source.close()
      eventSourceRef.current = null
    })

    return () => {
      source.removeEventListener("log", handleLogEvent)
      source.close()
      eventSourceRef.current = null
    }
  }, [isStreaming, isPaused, runId, streamUrl])

  const displayLines = useMemo(() => {
    const merged = [...parsedLogData.lines, ...effectiveStreamState.lines]
    if (parsedLogData.remainder) {
      merged.push(parsedLogData.remainder)
    }
    if (effectiveStreamState.buffer) {
      merged.push(effectiveStreamState.buffer)
    }
    return merged
  }, [effectiveStreamState.buffer, effectiveStreamState.lines, parsedLogData.lines, parsedLogData.remainder])

  useEffect(() => {
    if (!isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [displayLines, isPaused])

  const filteredLines = useMemo(() => {
    if (!searchQuery) return displayLines
    const query = searchQuery.toLowerCase()
    return displayLines.filter((line) => line.toLowerCase().includes(query))
  }, [displayLines, searchQuery])

  const handleDownload = () => {
    const logText = displayLines.join("\n")
    const blob = new Blob([logText], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `logs-${runId}-${new Date().toISOString()}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full border rounded-lg">
      <div className="flex flex-wrap items-center gap-2 p-3 border-b bg-muted/30">
        <div className="flex-1 flex items-center gap-2 min-w-[240px]">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-8"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          {isTruncated && <span className="text-xs text-muted-foreground">Showing first chunk (truncated)</span>}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setIsPaused(!isPaused)}>
            {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIsStreaming(!isStreaming)}>
            {isStreaming ? "Stop" : "Start"} Stream
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="h-4 w-4 mr-1" />
            Download
          </Button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-auto p-3 font-mono text-xs">
        {isLoading && filteredLines.length === 0 ? (
          <div className="text-muted-foreground">Loading logs...</div>
        ) : filteredLines.length > 0 ? (
          filteredLines.map((line, index) => (
            <div key={`${index}-${line}`} className={cn("py-0.5", line ? "text-foreground" : "text-muted-foreground")}>
              {line || " "}
            </div>
          ))
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">No logs yet</div>
        )}
      </div>

      <div className="flex items-center justify-between px-3 py-2 border-t bg-muted/30 text-xs text-muted-foreground">
        <span>{filteredLines.length} line(s)</span>
        <span>{isPaused ? "Paused" : isStreaming ? "Streaming" : "Stopped"}</span>
      </div>
    </div>
  )
}
