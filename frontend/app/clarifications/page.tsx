"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import { useClarifications, useAnswerClarificationById, useProjects } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { MessageCircle, Lock, Unlock, CheckCircle2 } from "lucide-react"
import { toast } from "sonner"
import type { Clarification } from "@/lib/api/types"

const resolveClarificationText = (value: Clarification["answer"] | Clarification["recommended"]) => {
  if (!value) return ""
  if (typeof value === "string") return value
  const candidate =
    value.text || value.value || value.answer || value.recommended || value.default || value.option || ""
  return typeof candidate === "string" ? candidate : ""
}

export default function ClarificationsPage() {
  const [statusFilter, setStatusFilter] = useState("open")
  const { data: clarifications, isLoading } = useClarifications(statusFilter === "all" ? undefined : statusFilter)
  const { data: projects } = useProjects()
  const answerClarification = useAnswerClarificationById()
  const [drafts, setDrafts] = useState<Record<number, string>>({})

  const projectMap = useMemo(() => {
    return new Map((projects || []).map((project) => [project.id, project.name]))
  }, [projects])

  if (isLoading) {
    return <LoadingState message="Loading clarifications..." />
  }

  if (!clarifications || clarifications.length === 0) {
    return (
      <div className="flex h-full flex-col gap-6 p-6">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Clarifications Inbox</h1>
          <p className="text-sm text-muted-foreground">Answer open questions across projects and protocols</p>
        </div>
        <EmptyState
          icon={MessageCircle}
          title="No clarifications found"
          description="You're all caught up. New questions will appear here."
        />
      </div>
    )
  }

  const handleAnswer = async (clarification: Clarification) => {
    const answer = (drafts[clarification.id] || "").trim()
    if (!answer) return
    try {
      await answerClarification.mutateAsync({ id: clarification.id, answer })
      toast.success("Clarification answered")
      setDrafts((prev) => ({ ...prev, [clarification.id]: "" }))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to answer clarification")
    }
  }

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Clarifications Inbox</h1>
          <p className="text-sm text-muted-foreground">Answer open questions across projects and protocols</p>
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="answered">Answered</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-4">
        {clarifications.map((clarification) => {
          const projectName = clarification.project_id ? projectMap.get(clarification.project_id) : null
          const isOpen = clarification.status === "open"
          const resolvedAnswer = resolveClarificationText(clarification.answer)
          return (
            <Card key={clarification.id} className={clarification.blocking && isOpen ? "border-amber-500/40" : ""}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <CardTitle className="text-base flex items-center gap-2">
                      {clarification.blocking ? (
                        <Lock className="h-4 w-4 text-amber-500" />
                      ) : (
                        <Unlock className="h-4 w-4 text-muted-foreground" />
                      )}
                      {clarification.key || `clarification-${clarification.id}`}
                    </CardTitle>
                    <CardDescription>
                      {projectName ? (
                        <span>
                          Project:{" "}
                          <Link className="underline" href={`/projects/${clarification.project_id}`}>
                            {projectName}
                          </Link>
                        </span>
                      ) : (
                        "Project: Unknown"
                      )}
                      {clarification.protocol_run_id && (
                        <>
                          {" "}
                          • Protocol:{" "}
                          <Link className="underline" href={`/protocols/${clarification.protocol_run_id}`}>
                            {clarification.protocol_run_id}
                          </Link>
                        </>
                      )}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    {clarification.applies_to && <Badge variant="secondary">{clarification.applies_to}</Badge>}
                    {clarification.status === "answered" && <CheckCircle2 className="h-5 w-5 text-green-500" />}
                    <Badge variant={isOpen ? "outline" : "default"}>{clarification.status}</Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm">{clarification.question}</p>
                {clarification.recommended && (
                  <p className="text-sm text-muted-foreground">
                    Recommended: <span className="font-medium">{resolveClarificationText(clarification.recommended)}</span>
                  </p>
                )}
                {clarification.options && clarification.options.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {clarification.options.map((option) => (
                      <Badge key={option} variant="outline">
                        {option}
                      </Badge>
                    ))}
                  </div>
                )}
                {isOpen ? (
                  <div className="flex flex-wrap gap-2">
                    <Input
                      placeholder="Answer..."
                      value={drafts[clarification.id] || ""}
                      onChange={(event) =>
                        setDrafts((prev) => ({ ...prev, [clarification.id]: event.target.value }))
                      }
                      className="flex-1 min-w-[240px]"
                    />
                    <Button
                      onClick={() => handleAnswer(clarification)}
                      disabled={answerClarification.isPending || !(drafts[clarification.id] || "").trim()}
                    >
                      {answerClarification.isPending ? "Saving..." : "Submit"}
                    </Button>
                  </div>
                ) : (
                  resolvedAnswer && (
                    <div className="rounded-lg bg-muted p-3 text-sm">
                      <span className="font-medium">Answer:</span> {resolvedAnswer}
                    </div>
                  )
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
