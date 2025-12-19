"use client"

import Link from "next/link"
import { useHealth } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Bell, HelpCircle, Command, Keyboard } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"
import { useState } from "react"
import { KeyboardShortcuts } from "@/components/features/keyboard-shortcuts"

export function Header() {
  const { data: health, isError } = useHealth()
  const [shortcutsOpen, setShortcutsOpen] = useState(false)

  const handleCommandPalette = () => {
    const event = new KeyboardEvent("keydown", { key: "k", metaKey: true })
    document.dispatchEvent(event)
  }

  return (
    <>
      <header
        data-header
        className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      >
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 rounded-md border border-border bg-muted/50 px-2 py-1">
              <div
                className={cn(
                  "h-2 w-2 rounded-full",
                  health?.status === "ok" ? "bg-green-500 animate-pulse" : isError ? "bg-red-500" : "bg-yellow-500",
                )}
              />
              <span className="text-xs text-muted-foreground">
                {health?.status === "ok" ? "Connected" : isError ? "Offline" : "Connecting..."}
              </span>
            </div>
            <Badge variant="outline" className="text-xs">
              Development
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="h-8 gap-2 px-3 text-xs text-muted-foreground bg-transparent"
              onClick={handleCommandPalette}
            >
              <Command className="h-3 w-3" />
              <span>Search</span>
              <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 sm:flex">
                <span className="text-xs">⌘</span>K
              </kbd>
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 relative">
                  <Bell className="h-4 w-4" />
                  <Badge
                    className="absolute -top-1 -right-1 h-4 w-4 p-0 flex items-center justify-center text-[10px]"
                    variant="destructive"
                  >
                    3
                  </Badge>
                  <span className="sr-only">Notifications</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80">
                <DropdownMenuLabel>Notifications</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Protocol execution completed</p>
                    <p className="text-xs text-muted-foreground">Project: E-commerce Web App - 2 minutes ago</p>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Policy violation detected</p>
                    <p className="text-xs text-muted-foreground">Step: Code Review - 15 minutes ago</p>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Run failed</p>
                    <p className="text-xs text-muted-foreground">Protocol: CI Pipeline - 1 hour ago</p>
                  </div>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <HelpCircle className="h-4 w-4" />
                  <span className="sr-only">Help</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Help & Resources</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Documentation</DropdownMenuItem>
                <DropdownMenuItem>API Reference</DropdownMenuItem>
                <DropdownMenuItem onClick={() => setShortcutsOpen(true)}>
                  <Keyboard className="h-4 w-4 mr-2" />
                  Keyboard Shortcuts
                </DropdownMenuItem>
                <DropdownMenuItem>Changelog</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Contact Support</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <div className="h-6 w-px bg-border" />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-8 gap-2 px-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                    DU
                  </div>
                  <span className="text-sm">Demo User</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Demo User</p>
                    <p className="text-xs text-muted-foreground">demo@tasksgodzilla.dev</p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/profile">Profile</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/settings">Settings</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive">Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <KeyboardShortcuts open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
    </>
  )
}
