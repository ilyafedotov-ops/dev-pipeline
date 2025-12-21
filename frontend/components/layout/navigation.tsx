"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { FolderGit2, PlayCircle, Activity, Shield, FileText, BarChart3, Bot, Kanban } from "lucide-react"

const navItems = [
  { href: "/projects", label: "Projects", icon: FolderGit2 },
  { href: "/execution", label: "Execution", icon: Kanban },
  { href: "/specifications", label: "Specifications", icon: FileText },
  { href: "/runs", label: "Runs", icon: PlayCircle },
  { href: "/quality", label: "Quality", icon: BarChart3 },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/ops", label: "Operations", icon: Activity },
  { href: "/policy-packs", label: "Policy Packs", icon: Shield },
]

export function Navigation() {
  const pathname = usePathname()

  return (
    <nav className="border-b bg-muted/30">
      <div className="flex h-12 items-center gap-1 px-6">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href)
          const Icon = item.icon

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-background/50 hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
