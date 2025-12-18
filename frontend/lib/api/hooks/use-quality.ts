"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient } from "../client"
import { queryKeys } from "../query-keys"

// Types for Quality Dashboard
export interface QAOverview {
    total_protocols: number
    passed: number
    warnings: number
    failed: number
    average_score: number
}

export interface QAFinding {
    id: number
    protocol_id: number
    project_name: string
    article: string
    article_name: string
    severity: string
    message: string
    timestamp: string
}

export interface ConstitutionalGate {
    article: string
    name: string
    status: string
    checks: number
}

export interface QualityDashboard {
    overview: QAOverview
    recent_findings: QAFinding[]
    constitutional_gates: ConstitutionalGate[]
}

// Get Quality Dashboard
export function useQualityDashboard() {
    return useQuery({
        queryKey: queryKeys.quality.dashboard(),
        queryFn: () => apiClient.get<QualityDashboard>("/quality/dashboard"),
    })
}
