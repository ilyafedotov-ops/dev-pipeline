"use client"

import { useMemo } from "react"
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { BurndownPoint } from "@/lib/api/types"
import { cn } from "@/lib/utils"

/**
 * Format a date string for display on the X-axis
 */
export function formatDateLabel(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

/**
 * Custom tooltip component for burndown chart
 * Shows date and points remaining for both ideal and actual lines
 * **Validates: Requirements 5.3**
 */
interface BurndownTooltipProps {
  active?: boolean
  payload?: Array<{
    name: string
    value: number
    color: string
    payload: { date: string; ideal: number; actual: number }
  }>
  label?: string
}

function BurndownTooltip({ active, payload }: BurndownTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null
  }

  const data = payload[0]?.payload
  if (!data) return null

  const formattedDate = formatDateLabel(data.date)

  return (
    <div className="bg-background border border-border rounded-md shadow-md p-3 text-sm">
      <p className="font-medium mb-2">{formattedDate}</p>
      <div className="space-y-1">
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-muted-foreground">{entry.name}:</span>
            <span className="font-medium">{entry.value} points</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export interface BurndownChartProps {
  /** Burndown data points with date, ideal, and actual values */
  data: BurndownPoint[]
  /** Total story points at sprint start (used for Y-axis scaling) */
  totalPoints?: number
  /** Additional CSS classes */
  className?: string
  /** Chart height in pixels */
  height?: number
}

/**
 * BurndownChart Component
 * 
 * Renders a line chart showing ideal vs actual burndown progress.
 * - Ideal line: dashed gray line showing expected progress
 * - Actual line: solid blue line with area fill showing real progress
 * 
 * **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
 */
export function BurndownChart({
  data,
  totalPoints,
  className,
  height = 240,
}: BurndownChartProps) {
  const chartData = useMemo(() => {
    return (data || []).map((p) => ({
      date: p.date,
      ideal: p.ideal,
      actual: p.actual,
      label: formatDateLabel(p.date),
    }))
  }, [data])

  // Calculate Y-axis domain
  const yAxisMax = useMemo(() => {
    if (totalPoints && totalPoints > 0) return totalPoints
    if (chartData.length === 0) return 100
    const maxIdeal = Math.max(...chartData.map(d => d.ideal))
    const maxActual = Math.max(...chartData.map(d => d.actual))
    return Math.max(maxIdeal, maxActual, 1)
  }, [chartData, totalPoints])

  if (!chartData || chartData.length === 0) {
    return (
      <div className={cn("text-sm text-muted-foreground py-6", className)}>
        No burndown data available.
      </div>
    )
  }

  return (
    <div className={cn(className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11 }}
            className="text-muted-foreground"
          />
          <YAxis
            tick={{ fontSize: 11 }}
            width={36}
            domain={[0, yAxisMax]}
            className="text-muted-foreground"
          />
          <Tooltip content={<BurndownTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          
          {/* Area fill under actual line */}
          <Area
            type="monotone"
            dataKey="actual"
            fill="#3b82f6"
            fillOpacity={0.1}
            stroke="none"
          />
          
          {/* Ideal burndown line - dashed */}
          <Line
            type="monotone"
            dataKey="ideal"
            stroke="#64748b"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name="Ideal"
          />
          
          {/* Actual burndown line - solid */}
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Actual"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * Utility function to count the number of lines in burndown chart data
 * Used for property testing to verify dual line rendering
 * **Validates: Requirements 5.2**
 */
export function countBurndownLines(data: BurndownPoint[]): { idealLine: boolean; actualLine: boolean } {
  if (!data || data.length === 0) {
    return { idealLine: false, actualLine: false }
  }
  
  // Check if data has ideal and actual values
  const hasIdeal = data.some(point => typeof point.ideal === 'number')
  const hasActual = data.some(point => typeof point.actual === 'number')
  
  return {
    idealLine: hasIdeal,
    actualLine: hasActual
  }
}

// Legacy export for backward compatibility
export { BurndownChart as default }
