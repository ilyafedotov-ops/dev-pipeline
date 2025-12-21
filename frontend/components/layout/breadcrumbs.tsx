"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight, Home } from "lucide-react"
import { Fragment } from "react"

const labelMap: Record<string, string> = {
  projects: "Projects",
  protocols: "Protocols",
  steps: "Steps",
  runs: "Runs",
  ops: "Operations",
  queues: "Queues",
  events: "Events",
  metrics: "Metrics",
  "policy-packs": "Policy Packs",
  settings: "Settings",
  profile: "Profile",
  onboarding: "Onboarding",
  branches: "Branches",
  policy: "Policy",
  clarifications: "Clarifications",
  spec: "Specification",
  logs: "Logs",
  artifacts: "Artifacts",
  execution: "Execution",
  specifications: "Specifications",
  quality: "Quality",
  agents: "Agents",
  sprints: "Execution",
  "sprint-board": "Execution",
}

export function Breadcrumbs() {
  const pathname = usePathname()
  const segments = pathname.split("/").filter(Boolean)

  if (segments.length === 0) return null

  const breadcrumbs = segments.map((segment, index) => {
    const href = "/" + segments.slice(0, index + 1).join("/")
    const label = labelMap[segment] || segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, " ")
    const isLast = index === segments.length - 1

    return { href, label, isLast }
  })

  return (
    <nav data-breadcrumbs className="flex items-center gap-2 border-b bg-muted/30 px-6 py-3 text-sm">
      <Link href="/" className="text-muted-foreground transition-colors hover:text-foreground">
        <Home className="h-4 w-4" />
      </Link>
      {breadcrumbs.map((crumb) => (
        <Fragment key={crumb.href}>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
          {crumb.isLast ? (
            <span className="font-medium text-foreground">{crumb.label}</span>
          ) : (
            <Link href={crumb.href} className="text-muted-foreground transition-colors hover:text-foreground">
              {crumb.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  )
}
