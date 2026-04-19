"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Activity,
  BarChart3,
  Bot,
  ChevronDown,
  ChevronRight,
  FileCode2,
  FileText,
  FolderKanban,
  GitBranch,
  Kanban,
  Layers,
  LayoutDashboard,
  MessageCircle,
  PlayCircle,
  Settings,
  Shield,
  Terminal,
  TrendingUp,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useProjects } from "@/lib/api";
import { cn } from "@/lib/utils";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavGroup {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: NavItem[];
}

const navigationGroups: NavGroup[] = [
  {
    title: "Workspace",
    icon: LayoutDashboard,
    items: [
      { name: "Dashboard", href: "/", icon: LayoutDashboard },
      { name: "Projects", href: "/projects", icon: FolderKanban },
    ],
  },
  {
    title: "Execute",
    icon: Zap,
    items: [
      { name: "Runs", href: "/runs", icon: PlayCircle },
      { name: "Executions", href: "/executions", icon: Terminal },
      { name: "Templates", href: "/templates", icon: Layers },
      { name: "Protocols", href: "/protocols", icon: GitBranch },
      { name: "Sprints", href: "/sprints", icon: Kanban },
      { name: "Specifications", href: "/specifications", icon: FileCode2 },
      { name: "Clarifications", href: "/clarifications", icon: MessageCircle },
    ],
  },
  {
    title: "Automation",
    icon: Bot,
    items: [
      { name: "Agents", href: "/agents", icon: Bot },
      { name: "Quality", href: "/quality", icon: BarChart3 },
      { name: "Policy Packs", href: "/policy-packs", icon: Shield },
    ],
  },
  {
    title: "Operations",
    icon: Activity,
    items: [
      { name: "Queues", href: "/ops/queues", icon: Layers },
      { name: "Events", href: "/ops/events", icon: Activity },
      { name: "Logs", href: "/ops/logs", icon: FileText },
      { name: "Metrics", href: "/ops/metrics", icon: TrendingUp },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<string[]>(["Workspace", "Execute"]);
  const { data: projects = [] } = useProjects();

  const toggleGroup = (title: string) => {
    setExpandedGroups((prev) =>
      prev.includes(title) ? prev.filter((g) => g !== title) : [...prev, title]
    );
  };

  const isItemActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <aside
      data-sidebar
      className={cn(
        "border-sidebar-border bg-sidebar sticky top-0 h-screen border-r transition-all duration-300",
        isCollapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="border-sidebar-border flex h-16 items-center border-b px-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="bg-sidebar-primary flex h-8 w-8 items-center justify-center rounded-lg">
              <Layers className="text-sidebar-primary-foreground h-5 w-5" />
            </div>
            {!isCollapsed && (
              <span className="text-sidebar-foreground font-semibold">DevGodzilla</span>
            )}
          </Link>
        </div>

        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-4">
            {navigationGroups.map((group) => {
              const isExpanded = expandedGroups.includes(group.title);
              const hasActiveItem = group.items.some((item) => isItemActive(item.href));

              return (
                <Collapsible
                  key={group.title}
                  open={isExpanded}
                  onOpenChange={() => toggleGroup(group.title)}
                >
                  <CollapsibleTrigger asChild>
                    <Button
                      variant="ghost"
                      className={cn(
                        "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground w-full justify-start gap-2",
                        hasActiveItem && "bg-sidebar-accent/50"
                      )}
                    >
                      <group.icon className="h-4 w-4 shrink-0" />
                      {!isCollapsed && (
                        <>
                          <span className="flex-1 text-left text-xs font-semibold tracking-wider uppercase">
                            {group.title}
                          </span>
                          {isExpanded ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3" />
                          )}
                        </>
                      )}
                    </Button>
                  </CollapsibleTrigger>
                  {!isCollapsed && (
                    <CollapsibleContent className="border-sidebar-border/50 mt-1 ml-2 space-y-0.5 border-l pl-2">
                      {group.items.map((item) => {
                        const isActive = isItemActive(item.href);
                        return (
                          <Link key={item.href} href={item.href}>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={cn(
                                "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground w-full justify-start gap-2 text-sm",
                                isActive &&
                                  "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                              )}
                            >
                              <item.icon className="h-4 w-4 shrink-0" />
                              <span>{item.name}</span>
                            </Button>
                          </Link>
                        );
                      })}
                    </CollapsibleContent>
                  )}
                </Collapsible>
              );
            })}

            {/* Settings - Always visible at bottom of nav */}
            {!isCollapsed && (
              <div className="border-sidebar-border/50 border-t pt-2">
                <Link href="/settings">
                  <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                      "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground w-full justify-start gap-2 text-sm",
                      pathname.startsWith("/settings") &&
                        "bg-sidebar-accent text-sidebar-accent-foreground"
                    )}
                  >
                    <Settings className="h-4 w-4" />
                    <span>Settings</span>
                  </Button>
                </Link>
              </div>
            )}
          </nav>
        </ScrollArea>

        {/* Recent Projects Section */}
        {!isCollapsed && (
          <>
            <Separator />
            <div className="p-3">
              <div className="text-muted-foreground mb-2 px-2 text-xs font-semibold tracking-wider uppercase">
                Recent Projects
              </div>
              {projects.length === 0 ? (
                <div className="text-muted-foreground px-2 py-2 text-xs">No projects yet.</div>
              ) : (
                <div className="space-y-0.5">
                  {projects.slice(0, 4).map((project) => (
                    <Link key={project.id} href={`/projects/${project.id}`}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-sidebar-foreground hover:bg-sidebar-accent w-full justify-start text-sm"
                      >
                        <FolderKanban className="mr-2 h-3.5 w-3.5" />
                        <span className="truncate">{project.name}</span>
                      </Button>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {/* Collapse Toggle */}
        <div className="border-sidebar-border border-t p-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-full justify-center"
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4 rotate-180" />
            )}
          </Button>
        </div>
      </div>
    </aside>
  );
}
