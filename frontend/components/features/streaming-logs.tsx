"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Pause, Play, Download, Search, X } from "lucide-react"
import { cn } from "@/lib/utils"

interface LogEntry {
  timestamp: string
  level: "info" | "warn" | "error" | "debug"
  source: string
  message: string
  requestId?: string
}

interface StreamingLogsProps {
  runId: string
  initialLogs?: LogEntry[]
}

export function StreamingLogs({ runId, initialLogs = [] }: StreamingLogsProps) {
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs)
  const [isPaused, setIsPaused] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [levelFilter, setLevelFilter] = useState<string>("all")
  const [isStreaming, setIsStreaming] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (isPaused || !isStreaming) return

    // In production, connect to SSE endpoint
    // eventSourceRef.current = new EventSource(`/api/codex/runs/${runId}/logs/stream`)
    const eventSource = eventSourceRef.current

    // Mock: simulate streaming logs
    const interval = setInterval(() => {
      setLogs((prev) => {
        const mockLog: LogEntry = {
          timestamp: new Date().toISOString(),
          level: ["info", "warn", "error", "debug"][Math.floor(Math.random() * 4)] as LogEntry["level"],
          source: ["api", "worker", "scheduler"][Math.floor(Math.random() * 3)],
          message: `Log entry ${prev.length + 1}: Processing task...`,
          requestId: `req-${Math.random().toString(36).substr(2, 9)}`,
        }
        return [...prev, mockLog]
      })
    }, 2000)

    return () => {
      clearInterval(interval)
      eventSource?.close()
    }
  }, [runId, isPaused, isStreaming])
  // </CHANGE>

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (!isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, isPaused])

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.source.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesLevel = levelFilter === "all" || log.level === levelFilter
    return matchesSearch && matchesLevel
  })

  const handleDownload = () => {
    const logText = filteredLogs
      .map((log) => `[${log.timestamp}] [${log.level.toUpperCase()}] [${log.source}] ${log.message}`)
      .join("\n")

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
      {/* Controls */}
      <div className="flex items-center gap-2 p-3 border-b bg-muted/30">
        <div className="flex-1 flex items-center gap-2">
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
          <Select value={levelFilter} onValueChange={setLevelFilter}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Levels</SelectItem>
              <SelectItem value="info">Info</SelectItem>
              <SelectItem value="warn">Warning</SelectItem>
              <SelectItem value="error">Error</SelectItem>
              <SelectItem value="debug">Debug</SelectItem>
            </SelectContent>
          </Select>
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

      {/* Log Output */}
      <ScrollArea className="flex-1 p-3 font-mono text-xs" ref={scrollRef}>
        {filteredLogs.map((log, index) => (
          <div key={index} className="flex gap-2 py-1 hover:bg-muted/50">
            <span className="text-muted-foreground shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
            <span
              className={cn(
                "shrink-0 font-semibold uppercase",
                log.level === "error" && "text-red-500",
                log.level === "warn" && "text-yellow-500",
                log.level === "info" && "text-blue-500",
                log.level === "debug" && "text-gray-500",
              )}
            >
              [{log.level}]
            </span>
            <span className="text-muted-foreground shrink-0">[{log.source}]</span>
            <span className="text-foreground">{log.message}</span>
            {log.requestId && <span className="text-muted-foreground ml-auto shrink-0">req:{log.requestId}</span>}
          </div>
        ))}
        {filteredLogs.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            No logs match your filters
          </div>
        )}
      </ScrollArea>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-3 py-2 border-t bg-muted/30 text-xs text-muted-foreground">
        <span>{filteredLogs.length} log entries</span>
        <span>{isPaused ? "Paused" : isStreaming ? "Streaming" : "Stopped"}</span>
      </div>
    </div>
  )
}
