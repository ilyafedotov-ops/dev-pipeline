"use client"

import { useState, useRef, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Search, Download, Pause, Play, AlertCircle, Info, AlertTriangle, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"

interface LogEntry {
  id: string
  timestamp: string
  level: "info" | "warn" | "error" | "debug"
  source: string
  message: string
  metadata?: Record<string, unknown>
}

interface LogsConsoleProps {
  runId?: string
  protocolId?: string
  className?: string
}

const mockLogs: LogEntry[] = [
  {
    id: "1",
    timestamp: "2024-01-15T10:30:00Z",
    level: "info",
    source: "protocol-engine",
    message: "Protocol execution started",
    metadata: { protocolId: "proto-123" },
  },
  {
    id: "2",
    timestamp: "2024-01-15T10:30:05Z",
    level: "debug",
    source: "step-executor",
    message: "Executing step: analyze_requirements",
  },
  {
    id: "3",
    timestamp: "2024-01-15T10:30:10Z",
    level: "warn",
    source: "policy-checker",
    message: "Policy violation detected: code complexity exceeds threshold",
  },
  {
    id: "4",
    timestamp: "2024-01-15T10:30:15Z",
    level: "error",
    source: "code-executor",
    message: "Run failed: syntax error in generated code",
    metadata: { error: "SyntaxError: Unexpected token" },
  },
  {
    id: "5",
    timestamp: "2024-01-15T10:30:20Z",
    level: "info",
    source: "protocol-engine",
    message: "Step completed successfully",
  },
]

const levelIcons = {
  info: Info,
  warn: AlertTriangle,
  error: XCircle,
  debug: AlertCircle,
}

const levelColors = {
  info: "text-blue-500",
  warn: "text-yellow-500",
  error: "text-red-500",
  debug: "text-gray-500",
}

export function LogsConsole({ runId, protocolId, className }: LogsConsoleProps) {
  const [logs] = useState<LogEntry[]>(mockLogs)
  const [searchQuery, setSearchQuery] = useState("")
  const [levelFilter, setLevelFilter] = useState<string>("all")
  const [isPaused, setIsPaused] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isPaused && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, isPaused])

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) || log.source.includes(searchQuery)
    const matchesLevel = levelFilter === "all" || log.level === levelFilter
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
    a.download = `logs-${runId || protocolId || "export"}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Logs Console</CardTitle>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsPaused(!isPaused)}>
              {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
              {isPaused ? "Resume" : "Pause"}
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
        <ScrollArea className="h-96 px-6 pb-6" ref={scrollRef}>
          <div className="space-y-2 font-mono text-xs">
            {filteredLogs.map((log) => {
              const Icon = levelIcons[log.level]
              return (
                <div
                  key={log.id}
                  className={cn("flex items-start gap-3 rounded p-2 hover:bg-muted/50", levelColors[log.level])}
                >
                  <Icon className="h-4 w-4 mt-0.5 shrink-0" />
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">{new Date(log.timestamp).toLocaleTimeString()}</span>
                      <Badge variant="outline" className="text-xs">
                        {log.source}
                      </Badge>
                      <Badge variant="secondary" className="text-xs uppercase">
                        {log.level}
                      </Badge>
                    </div>
                    <p className="text-foreground">{log.message}</p>
                    {log.metadata && (
                      <pre className="text-xs text-muted-foreground">{JSON.stringify(log.metadata, null, 2)}</pre>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
