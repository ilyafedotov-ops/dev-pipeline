"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  FolderKanban,
  PlayCircle,
  Activity,
  Shield,
  Settings,
  ChevronDown,
  ChevronRight,
  Layers,
  BarChart3,
  Bot,
  Kanban,
  Sparkles,
  MessageCircle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { SpecKitLaunchDialog, type SpecKitWizardAction } from "@/components/wizards/speckit-launch-dialog"
import { useProjects } from "@/lib/api"

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Projects", href: "/projects", icon: FolderKanban },
  { name: "Execution", href: "/execution", icon: Kanban },
  {
    name: "SpecKit",
    href: "/specifications",
    icon: Sparkles,
    children: [
      { name: "All Specifications", href: "/specifications" },
      { name: "Generate Spec", action: "generate-specs" },
      { name: "Design Solution", action: "design-solution" },
      { name: "Generate Tasks", action: "implement-feature" },
    ],
  },
  { name: "Runs", href: "/runs", icon: PlayCircle },
  { name: "Clarifications", href: "/clarifications", icon: MessageCircle },
  { name: "Quality", href: "/quality", icon: BarChart3 },
  { name: "Agents", href: "/agents", icon: Bot },
  {
    name: "Operations",
    href: "/ops",
    icon: Activity,
    children: [
      { name: "Overview", href: "/ops" },
      { name: "Queues", href: "/ops/queues" },
      { name: "Events", href: "/ops/events" },
      { name: "Metrics", href: "/ops/metrics" },
    ],
  },
  { name: "Policy Packs", href: "/policy-packs", icon: Shield },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [expandedSections, setExpandedSections] = useState<string[]>(["Operations"])
  const [specKitAction, setSpecKitAction] = useState<SpecKitWizardAction | null>(null)
  const { data: projects = [] } = useProjects()

  const toggleSection = (name: string) => {
    setExpandedSections((prev) => (prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]))
  }

  return (
    <aside
      data-sidebar
      className={cn(
        "sticky top-0 h-screen border-r border-sidebar-border bg-sidebar transition-all duration-300",
        isCollapsed ? "w-16" : "w-64",
      )}
    >
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-16 items-center border-b border-sidebar-border px-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sidebar-primary">
              <Layers className="h-5 w-5 text-sidebar-primary-foreground" />
            </div>
            {!isCollapsed && <span className="font-semibold text-sidebar-foreground">TasksGodzilla</span>}
          </Link>
        </div>

        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-1">
            {navigation.map((item) => {
              const isActive = pathname === item.href
              const hasChildren = item.children && item.children.length > 0
              const isExpanded = expandedSections.includes(item.name)

              if (hasChildren) {
                return (
                  <Collapsible key={item.name} open={isExpanded} onOpenChange={() => toggleSection(item.name)}>
                    <CollapsibleTrigger asChild>
                      <Button
                        variant="ghost"
                        className={cn(
                          "w-full justify-start gap-3 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                          isActive && "bg-sidebar-accent text-sidebar-accent-foreground",
                        )}
                      >
                        <item.icon className="h-5 w-5 shrink-0" />
                        {!isCollapsed && (
                          <>
                            <span className="flex-1 text-left">{item.name}</span>
                            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                          </>
                        )}
                      </Button>
                    </CollapsibleTrigger>
                    {!isCollapsed && (
                      <CollapsibleContent className="ml-8 mt-1 space-y-1">
                        {item.children.map((child) => {
                          if ("action" in child && child.action) {
                            return (
                              <Button
                                key={child.name}
                                variant="ghost"
                                className="w-full justify-start text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                                onClick={() => setSpecKitAction(child.action as SpecKitWizardAction)}
                              >
                                {child.name}
                              </Button>
                            )
                          }

                          const isChildActive = pathname === child.href
                          return (
                            <Link key={child.href} href={child.href}>
                              <Button
                                variant="ghost"
                                className={cn(
                                  "w-full justify-start text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                                  isChildActive && "bg-sidebar-accent text-sidebar-accent-foreground",
                                )}
                              >
                                {child.name}
                              </Button>
                            </Link>
                          )
                        })}
                      </CollapsibleContent>
                    )}
                  </Collapsible>
                )
              }

              return (
                <Link key={item.name} href={item.href}>
                  <Button
                    variant="ghost"
                    className={cn(
                      "w-full justify-start gap-3 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                      isActive && "bg-sidebar-accent text-sidebar-accent-foreground",
                    )}
                  >
                    <item.icon className="h-5 w-5 shrink-0" />
                    {!isCollapsed && <span>{item.name}</span>}
                  </Button>
                </Link>
              )
            })}
          </nav>
        </ScrollArea>

        {/* Recent Projects Section */}
        {!isCollapsed && (
          <>
            <Separator />
            <div className="p-3">
              <div className="mb-2 px-2 text-xs font-semibold text-muted-foreground">RECENT PROJECTS</div>
              {projects.length === 0 ? (
                <div className="px-2 py-2 text-xs text-muted-foreground">No projects yet.</div>
              ) : (
                <div className="space-y-1">
                  {projects.slice(0, 4).map((project) => (
                    <Link key={project.id} href={`/projects/${project.id}`}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-sm text-sidebar-foreground hover:bg-sidebar-accent"
                      >
                        <FolderKanban className="mr-2 h-4 w-4" />
                        {project.name}
                      </Button>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {/* Collapse Toggle */}
        <div className="border-t border-sidebar-border p-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-full justify-center"
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronRight className="h-4 w-4 rotate-180" />}
          </Button>
        </div>
      </div>

      {specKitAction && (
        <SpecKitLaunchDialog
          open
          action={specKitAction}
          onOpenChange={(open) => {
            if (!open) setSpecKitAction(null)
          }}
        />
      )}
    </aside>
  )
}
