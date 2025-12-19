"use client"

import { useState } from "react"
import { useProtocolClarifications, useAnswerClarification } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { LoadingState } from "@/components/ui/loading-state"
import { EmptyState } from "@/components/ui/empty-state"
import { Lock, Unlock, CheckCircle2, MessageCircle } from "lucide-react"
import { toast } from "sonner"
import { formatRelativeTime } from "@/lib/format"
import type { Clarification } from "@/lib/api/types"

const resolveClarificationText = (value: Clarification["answer"] | Clarification["recommended"]) => {
  if (!value) return ""
  if (typeof value === "string") return value
  const candidate =
    value.text || value.value || value.answer || value.recommended || value.default || value.option || ""
  return typeof candidate === "string" ? candidate : ""
}

interface ClarificationsTabProps {
  protocolId: number
}

export function ClarificationsTab({ protocolId }: ClarificationsTabProps) {
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const { data: clarifications, isLoading } = useProtocolClarifications(protocolId, statusFilter || undefined)

  if (isLoading) return <LoadingState message="Loading clarifications..." />

  const openCount = clarifications?.filter((c) => c.status === "open").length || 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Clarifications</h3>
          <p className="text-sm text-muted-foreground">{openCount} open</p>
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="answered">Answered</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!clarifications || clarifications.length === 0 ? (
        <EmptyState
          icon={MessageCircle}
          title="No clarifications"
          description="No clarification questions for this protocol."
        />
      ) : (
        <div className="space-y-4">
          {clarifications.map((clarification) => (
            <ClarificationCard key={clarification.id} clarification={clarification} protocolId={protocolId} />
          ))}
        </div>
      )}
    </div>
  )
}

function ClarificationCard({ clarification, protocolId }: { clarification: Clarification; protocolId: number }) {
  const [answer, setAnswer] = useState(resolveClarificationText(clarification.answer))
  const answerMutation = useAnswerClarification()
  const clarificationKey = clarification.key || ""

  const handleSubmit = async () => {
    if (!answer.trim()) return
    if (!clarificationKey) {
      toast.error("Clarification key missing")
      return
    }
    try {
      await answerMutation.mutateAsync({
        scope: "protocol",
        scopeId: protocolId,
        key: clarificationKey,
        answer: answer.trim(),
      })
      toast.success("Answer submitted")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to submit answer")
    }
  }

  return (
    <Card className={clarification.blocking && clarification.status === "open" ? "border-yellow-500/50" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            {clarification.blocking ? (
              <Lock className="h-4 w-4 text-yellow-500" />
            ) : (
              <Unlock className="h-4 w-4 text-muted-foreground" />
            )}
            <CardTitle className="text-base font-mono">
              {clarificationKey || `clarification-${clarification.id}`}
            </CardTitle>
          </div>
          {clarification.status === "answered" && <CheckCircle2 className="h-5 w-5 text-green-500" />}
        </div>
        {clarification.applies_to && <CardDescription>Applies to: {clarification.applies_to}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm">{clarification.question}</p>

        {clarification.recommended && (
          <p className="text-sm text-muted-foreground">
            Recommended: <span className="font-medium">{resolveClarificationText(clarification.recommended)}</span>
          </p>
        )}

        {clarification.status === "open" ? (
          <div className="space-y-3">
            {clarification.options && clarification.options.length > 0 ? (
              <Select value={answer} onValueChange={setAnswer}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an option" />
                </SelectTrigger>
                <SelectContent>
                  {clarification.options.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input placeholder="Enter your answer" value={answer} onChange={(e) => setAnswer(e.target.value)} />
            )}
            <Button onClick={handleSubmit} disabled={!answer.trim() || answerMutation.isPending} size="sm">
              {answerMutation.isPending ? "Submitting..." : "Submit Answer"}
            </Button>
          </div>
        ) : (
          <div className="rounded-lg bg-muted p-3">
            <p className="text-sm">
              <span className="font-medium">Answer:</span> {resolveClarificationText(clarification.answer)}
            </p>
            {clarification.answered_by && (
              <p className="text-xs text-muted-foreground mt-1">
                Answered by {clarification.answered_by} • {formatRelativeTime(clarification.answered_at)}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
