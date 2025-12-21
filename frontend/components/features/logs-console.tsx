"use client"

import { useState, useRef, useCallback, useMemo, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Search, Download, Pause, Play, AlertCircle, Info, AlertTriangle, XCircle, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useRecentLogs, useLogStream } from "@/lib/api/hooks/use-logs"
import type { AppLogEntry, LogLevel } from "@/lib/api/types"

interface LogsConsoleProps {
  mode?: "application" | "runs"
  sourceFilter?: string
  className?: string
}

const levelIcons: Record<string, typeof Info> = {
  info: Info,
  warn: AlertTriangle,
  warning: AlertTriangle,
  error: XCircle,
  debug: AlertCircle,
}

const levelColors: Record<string, string> = {
  info: "text-blue-500",
  warn: "text-yellow-500",
  warning: "text-yellow-500",
  error: "text-red-500",
  debug: "text-gray-500",
}

const MAX_LOGS = 1000

export function LogsConsole({ mode = "application", sourceFilter, className }: LogsConsoleProps) {
  const streamKey = `${mode}:${sourceFilter ?? "all"}`
  const [streamState, setStreamState] = useState<{ key: string; logs: AppLogEntry[] }>(() => ({
    key: streamKey,
    logs: [],
  }))
  const [searchQuery, setSearchQuery] = useState("")
  const [levelFilter, setLevelFilter] = useState<string>("all")
  const [isPaused, setIsPaused] = useState(false)
  const [isStreaming, setIsStreaming] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  const { data: initialLogs, isLoading } = useRecentLogs(
    {
      source: sourceFilter,
      limit: 200,
    },
    { enabled: mode === "application" }
  )

  const combinedLogs = useMemo(() => {
    const baseLogs = initialLogs || []
    const streamLogs = streamState.key === streamKey ? streamState.logs : []
    const merged = [...baseLogs, ...streamLogs]
    return merged.length > MAX_LOGS ? merged.slice(-MAX_LOGS) : merged
  }, [initialLogs, streamKey, streamState])

  const handleNewLog = useCallback(
    (log: AppLogEntry) => {
      if (!isPaused) {
        setStreamState((prev) => {
          const nextKey = streamKey
          const existing = prev.key === nextKey ? prev.logs : []
          const updated = [...existing, log]
          return {
            key: nextKey,
            logs: updated.length > MAX_LOGS ? updated.slice(-MAX_LOGS) : updated,
          }
        })
      }
    },
    [isPaused, streamKey]
  )

  const handleConnected = useCallback(() => {
    setIsStreaming(true)
  }, [])

  const handleError = useCallback(() => {
    setIsStreaming(false)
  }, [])

  useLogStream({
    source: sourceFilter,
    level: levelFilter !== "all" ? levelFilter : undefined,
    onLog: handleNewLog,
    onConnected: handleConnected,
    onError: handleError,
    enabled: mode === "application" && !isPaused,
  })

  useEffect(() => {
    if (!isPaused && scrollRef.current) {
      const scrollElement = scrollRef.current.querySelector("[data-radix-scroll-area-viewport]")
      if (scrollElement) {
        scrollElement.scrollTop = scrollElement.scrollHeight
      }
    }
  }, [combinedLogs, isPaused])

  const normalizeLevel = (level: string): LogLevel => {
    if (level === "warning") return "warn"
    return level as LogLevel
  }

  const filteredLogs = combinedLogs.filter((log) => {
    const matchesSearch =
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.source.toLowerCase().includes(searchQuery.toLowerCase())
    const normalizedLevel = normalizeLevel(log.level)
    const matchesLevel = levelFilter === "all" || normalizedLevel === levelFilter
    return matchesSearch && matchesLevel
  })

  const handleDownload = () => {
    const logContent = filteredLogs
      .map((log) => `[${log.timestamp}] [${log.level.toUpperCase()}] [${log.source}] ${log.message}`)
      .join("\n")
    const blob = new Blob([logContent], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `logs-${mode}-${new Date().toISOString().slice(0, 10)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClear = () => {
    setLogs([])
  }

  if (isLoading) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-96">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg">Application Logs</CardTitle>
            {isStreaming && !isPaused && (
              <Badge variant="outline" className="text-green-500 border-green-500">
                Live
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsPaused(!isPaused)}>
              {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
              {isPaused ? "Resume" : "Pause"}
            </Button>
            <Button variant="outline" size="sm" onClick={handleClear}>
              Clear
            </Button>
            <Button variant="outline" size="sm" onClick={handleDownload}>
              <Download className="h-4 w-4 mr-2" />
              Download
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-4">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              className="pl-9"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
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
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[calc(100vh-24rem)] px-6 pb-6" ref={scrollRef}>
          <div className="space-y-2 font-mono text-xs">
            {filteredLogs.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                {logs.length === 0 ? "No logs yet. Waiting for activity..." : "No logs match your filter."}
              </div>
            ) : (
              filteredLogs.map((log) => {
                const normalizedLevel = normalizeLevel(log.level)
                const Icon = levelIcons[normalizedLevel] || Info
                const colorClass = levelColors[normalizedLevel] || "text-gray-500"
                return (
                  <div
                    key={log.id}
                    className={cn("flex items-start gap-3 rounded p-2 hover:bg-muted/50", colorClass)}
                  >
                    <Icon className="h-4 w-4 mt-0.5 shrink-0" />
                    <div className="flex-1 space-y-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-muted-foreground">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                        <Badge variant="outline" className="text-xs truncate max-w-[200px]">
                          {log.source}
                        </Badge>
                        <Badge variant="secondary" className="text-xs uppercase">
                          {normalizedLevel}
                        </Badge>
                      </div>
                      <p className="text-foreground break-words">{log.message}</p>
                      {log.metadata && Object.keys(log.metadata).length > 0 && (
                        <pre className="text-xs text-muted-foreground overflow-x-auto">
                          {JSON.stringify(log.metadata, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
