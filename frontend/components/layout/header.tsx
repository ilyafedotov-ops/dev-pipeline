"use client";

import { useState } from "react";
import Link from "next/link";

import { Bell, Command, HelpCircle, Keyboard } from "lucide-react";

import { KeyboardShortcuts } from "@/components/features/keyboard-shortcuts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Header() {
  const { data: health, isError } = useHealth();
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const handleCommandPalette = () => {
    const event = new KeyboardEvent("keydown", { key: "k", metaKey: true });
    document.dispatchEvent(event);
  };

  return (
    <>
      <header
        data-header
        className="bg-background/95 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50 border-b backdrop-blur"
      >
        <div className="flex h-14 items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <div className="border-border bg-muted/50 flex items-center gap-2 rounded-md border px-2 py-1">
              <div
                className={cn(
                  "h-2 w-2 rounded-full",
                  health?.status === "ok"
                    ? "animate-pulse bg-green-500"
                    : isError
                      ? "bg-red-500"
                      : "bg-yellow-500"
                )}
              />
              <span className="text-muted-foreground text-xs">
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
              className="text-muted-foreground h-8 gap-2 bg-transparent px-3 text-xs"
              onClick={handleCommandPalette}
            >
              <Command className="h-3 w-3" />
              <span>Search</span>
              <kbd className="bg-muted pointer-events-none hidden h-5 items-center gap-1 rounded border px-1.5 font-mono text-[10px] font-medium opacity-100 select-none sm:flex">
                <span className="text-xs">⌘</span>K
              </kbd>
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="relative h-8 w-8 overflow-visible">
                  <Bell className="h-4 w-4" />
                  <Badge
                    className="absolute -top-1.5 -right-1.5 flex h-4 min-w-4 items-center justify-center p-0 text-[10px] leading-none"
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
                    <p className="text-muted-foreground text-xs">
                      Project: E-commerce Web App - 2 minutes ago
                    </p>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Policy violation detected</p>
                    <p className="text-muted-foreground text-xs">
                      Step: Code Review - 15 minutes ago
                    </p>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Run failed</p>
                    <p className="text-muted-foreground text-xs">
                      Protocol: CI Pipeline - 1 hour ago
                    </p>
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
                  <Keyboard className="mr-2 h-4 w-4" />
                  Keyboard Shortcuts
                </DropdownMenuItem>
                <DropdownMenuItem>Changelog</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Contact Support</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <div className="bg-border h-6 w-px" />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-8 gap-2 px-2">
                  <div className="bg-primary text-primary-foreground flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold">
                    DU
                  </div>
                  <span className="text-sm">Demo User</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>
                  <div className="flex flex-col gap-1">
                    <p className="text-sm font-medium">Demo User</p>
                    <p className="text-muted-foreground text-xs">demo@devgodzilla.dev</p>
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
  );
}
