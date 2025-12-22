"use client"

import { useState, useRef, useCallback, useMemo, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Search,
  Download,
  Pause,
  Play,
  AlertCircle,
  Info,
  AlertTriangle,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Filter,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useRecentLogs, useLogStream } from "@/lib/api/hooks/use-logs"
import type { AppLogEntry, LogLevel } from "@/lib/api/types"

interface LogsConsoleProps {
  mode?: "application" | "runs"
  sourceFilter?: string
  className?: string
}

const SUBSYSTEMS = [
  { id: "projects", label: "Projects", pattern: "devgodzilla.api.routes.projects" },
  { id: "protocols", label: "Protocols", pattern: "devgodzilla.services.orchestrator" },
  { id: "steps", label: "Steps", pattern: "devgodzilla.services.execution" },
  { id: "engines", label: "Engines", pattern: "devgodzilla.engines" },
  { id: "git", label: "Git", pattern: "devgodzilla.services.git" },
  { id: "qa", label: "QA", pattern: "devgodzilla.services.quality" },
  { id: "windmill", label: "Windmill", pattern: "devgodzilla.windmill" },
  { id: "discovery", label: "Discovery", pattern: "devgodzilla.services.discovery" },
] as const

const CONTEXT_FIELDS = ["project_id", "protocol_run_id", "step_run_id", "run_id", "request_id"] as const

function shortenSource(source: string): string {
  return source
    .replace("devgodzilla.api.routes.", "api.")
    .replace("devgodzilla.services.", "svc.")
    .replace("devgodzilla.engines.", "eng.")
    .replace("devgodzilla.windmill.", "wm.")
    .replace("devgodzilla.", "")
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
  const [activeSubsystems, setActiveSubsystems] = useState<Set<string>>(new Set())
  const [contextFilters, setContextFilters] = useState<Record<string, string>>({})
  const [showFilters, setShowFilters] = useState(false)
  const [expandedMetadata, setExpandedMetadata] = useState<Set<string>>(new Set())
  const [logTimestamps, setLogTimestamps] = useState<number[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  const toggleSubsystem = (id: string) => {
    setActiveSubsystems((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const clearAllFilters = () => {
    setActiveSubsystems(new Set())
    setContextFilters({})
    setLevelFilter("all")
    setSearchQuery("")
  }

  const hasActiveFilters =
    activeSubsystems.size > 0 ||
    Object.keys(contextFilters).length > 0 ||
    levelFilter !== "all" ||
    searchQuery.length > 0

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
        const now = Date.now()
        setLogTimestamps((prev) => {
          const recent = prev.filter((ts) => now - ts < 60000)
          return [...recent, now]
        })
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

  const logsPerMinute = useMemo(() => {
    const now = Date.now()
    return logTimestamps.filter((ts) => now - ts < 60000).length
  }, [logTimestamps])

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

  const filteredLogs = useMemo(() => {
    return combinedLogs.filter((log) => {
      const matchesSearch =
        searchQuery.length === 0 ||
        log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.source.toLowerCase().includes(searchQuery.toLowerCase())

      const normalizedLevel = normalizeLevel(log.level)
      const matchesLevel = levelFilter === "all" || normalizedLevel === levelFilter

      const matchesSubsystem =
        activeSubsystems.size === 0 ||
        Array.from(activeSubsystems).some((id) => {
          const subsystem = SUBSYSTEMS.find((s) => s.id === id)
          return subsystem && log.source.includes(subsystem.pattern)
        })

      const matchesContext = Object.entries(contextFilters).every(([key, value]) => {
        if (!value) return true
        const metaValue = log.metadata?.[key]
        return metaValue !== undefined && String(metaValue).includes(value)
      })

      return matchesSearch && matchesLevel && matchesSubsystem && matchesContext
    })
  }, [combinedLogs, searchQuery, levelFilter, activeSubsystems, contextFilters])

  const logStats = useMemo(() => {
    const stats = { info: 0, warn: 0, error: 0, debug: 0, total: combinedLogs.length }
    combinedLogs.forEach((log) => {
      const level = normalizeLevel(log.level)
      if (level in stats) {
        stats[level as keyof typeof stats]++
      }
    })
    return stats
  }, [combinedLogs])

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
    setStreamState({ key: streamKey, logs: [] })
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
      <CardHeader className="pb-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg">Backend Logs</CardTitle>
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

        {/* Statistics Bar */}
        <div className="flex items-center gap-4 text-xs border rounded-lg p-2 bg-muted/30">
          <div className="flex items-center gap-1.5">
            <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-muted-foreground">Total:</span>
            <span className="font-medium">{logStats.total}</span>
          </div>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-muted-foreground">Info:</span>
              <span className="font-medium">{logStats.info}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-yellow-500" />
              <span className="text-muted-foreground">Warn:</span>
              <span className="font-medium">{logStats.warn}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              <span className="text-muted-foreground">Error:</span>
              <span className="font-medium">{logStats.error}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-500" />
              <span className="text-muted-foreground">Debug:</span>
              <span className="font-medium">{logStats.debug}</span>
            </span>
          </div>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Rate:</span>
            <span className="font-medium">{logsPerMinute}/min</span>
          </div>
          {filteredLogs.length !== logStats.total && (
            <>
              <div className="h-4 w-px bg-border" />
              <span className="text-muted-foreground">
                Showing: <span className="font-medium text-foreground">{filteredLogs.length}</span>
              </span>
            </>
          )}
        </div>

        {/* Subsystem Filter Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground mr-1">Subsystems:</span>
          {SUBSYSTEMS.map((subsystem) => (
            <Button
              key={subsystem.id}
              variant={activeSubsystems.has(subsystem.id) ? "default" : "outline"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => toggleSubsystem(subsystem.id)}
            >
              {subsystem.label}
            </Button>
          ))}
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground" onClick={clearAllFilters}>
              <X className="h-3 w-3 mr-1" />
              Clear filters
            </Button>
          )}
        </div>

        {/* Search and Level Filter */}
        <div className="flex items-center gap-2">
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
          <Button
            variant={showFilters ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="h-4 w-4 mr-1" />
            Context
          </Button>
        </div>

        {/* Context Filters */}
        {showFilters && (
          <div className="flex flex-wrap items-center gap-2 p-3 border rounded-lg bg-muted/20">
            <span className="text-xs text-muted-foreground">Filter by context:</span>
            {CONTEXT_FIELDS.map((field) => (
              <div key={field} className="flex items-center gap-1">
                <label className="text-xs text-muted-foreground">{field}:</label>
                <Input
                  className="h-7 w-24 text-xs"
                  placeholder="value"
                  value={contextFilters[field] || ""}
                  onChange={(e) =>
                    setContextFilters((prev) => ({
                      ...prev,
                      [field]: e.target.value,
                    }))
                  }
                />
              </div>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[calc(100vh-24rem)] px-6 pb-6" ref={scrollRef}>
          <div className="space-y-2 font-mono text-xs">
            {filteredLogs.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                {combinedLogs.length === 0 ? "No logs yet. Waiting for activity..." : "No logs match your filter."}
              </div>
            ) : (
              filteredLogs.map((log, index) => {
                const normalizedLevel = normalizeLevel(log.level)
                const Icon = levelIcons[normalizedLevel] || Info
                const colorClass = levelColors[normalizedLevel] || "text-gray-500"
                const uniqueKey = `${log.id}-${log.timestamp}-${index}`
                const hasMetadata = log.metadata && Object.keys(log.metadata).length > 0
                const isExpanded = expandedMetadata.has(uniqueKey)

                const inlineFields = hasMetadata
                  ? CONTEXT_FIELDS.filter((f) => log.metadata?.[f] !== undefined)
                  : []
                const otherMetadata = hasMetadata
                  ? Object.fromEntries(
                      Object.entries(log.metadata!).filter(
                        ([k]) => !CONTEXT_FIELDS.includes(k as (typeof CONTEXT_FIELDS)[number])
                      )
                    )
                  : {}
                const hasOtherMetadata = Object.keys(otherMetadata).length > 0

                return (
                  <div
                    key={uniqueKey}
                    className={cn("flex items-start gap-3 rounded p-2 hover:bg-muted/50", colorClass)}
                  >
                    <Icon className="h-4 w-4 mt-0.5 shrink-0" />
                    <div className="flex-1 space-y-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-muted-foreground">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                        <Badge variant="outline" className="text-xs" title={log.source}>
                          {shortenSource(log.source)}
                        </Badge>
                        <Badge variant="secondary" className="text-xs uppercase">
                          {normalizedLevel}
                        </Badge>
                        {inlineFields.map((field) => (
                          <Badge
                            key={field}
                            variant="outline"
                            className="text-xs bg-muted/50 cursor-pointer"
                            onClick={() => {
                              setContextFilters((prev) => ({
                                ...prev,
                                [field]: String(log.metadata![field]),
                              }))
                              setShowFilters(true)
                            }}
                            title={`Click to filter by ${field}`}
                          >
                            {field.replace(/_id$/, "").replace(/_/g, " ")}:{" "}
                            <span className="font-mono ml-1">
                              {String(log.metadata![field]).slice(0, 8)}
                            </span>
                          </Badge>
                        ))}
                      </div>
                      <p className="text-foreground break-words">{log.message}</p>
                      {hasOtherMetadata && (
                        <Collapsible
                          open={isExpanded}
                          onOpenChange={(open) => {
                            setExpandedMetadata((prev) => {
                              const next = new Set(prev)
                              if (open) {
                                next.add(uniqueKey)
                              } else {
                                next.delete(uniqueKey)
                              }
                              return next
                            })
                          }}
                        >
                          <CollapsibleTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-5 px-1 text-xs text-muted-foreground hover:text-foreground"
                            >
                              {isExpanded ? (
                                <ChevronDown className="h-3 w-3 mr-1" />
                              ) : (
                                <ChevronRight className="h-3 w-3 mr-1" />
                              )}
                              {Object.keys(otherMetadata).length} more fields
                            </Button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <pre className="text-xs text-muted-foreground overflow-x-auto mt-1 p-2 bg-muted/30 rounded">
                              {JSON.stringify(otherMetadata, null, 2)}
                            </pre>
                          </CollapsibleContent>
                        </Collapsible>
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
