"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  Activity,
  Bot,
  FileCode2,
  FolderKanban,
  GitBranch,
  Kanban,
  Keyboard,
  Layers,
  MessageCircle,
  PlayCircle,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shield,
  TrendingUp,
  Zap,
} from "lucide-react";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { useProjects } from "@/lib/api";

// Navigation shortcuts - accessible via Ctrl/Cmd + key
const navigationItems = [
  { icon: FolderKanban, label: "Projects", href: "/projects", shortcut: "p" },
  { icon: PlayCircle, label: "Runs", href: "/runs", shortcut: "r" },
  { icon: GitBranch, label: "Protocols", href: "/protocols", shortcut: "o" },
  { icon: Kanban, label: "Execution", href: "/execution", shortcut: "s" },
  { icon: Bot, label: "Agents", href: "/agents", shortcut: "a" },
  { icon: Shield, label: "Policy Packs", href: "/policy-packs", shortcut: "l" },
  { icon: FileCode2, label: "Specifications", href: "/specifications", shortcut: "e" },
  { icon: MessageCircle, label: "Clarifications", href: "/clarifications", shortcut: "c" },
];

const operationItems = [
  { icon: Layers, label: "Queues", href: "/ops/queues" },
  { icon: Activity, label: "Events", href: "/ops/events" },
  { icon: TrendingUp, label: "Metrics", href: "/ops/metrics" },
];

const actionItems = [
  { icon: Plus, label: "New Project", href: "/projects/new", shortcut: "n" },
  { icon: RefreshCw, label: "Refresh Page", action: "refresh", shortcut: "." },
];

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { data: projects = [] } = useProjects();

  // Get recent projects (last 5)
  const recentProjects = projects.slice(0, 5);

  // Keyboard shortcut to open palette
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Open command palette: Ctrl/Cmd + K
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setOpen((open) => !open);
    }
    
    // Quick navigation shortcuts (when not in input)
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
      return;
    }

    // Ctrl/Cmd + key shortcuts
    if (e.metaKey || e.ctrlKey) {
      const key = e.key.toLowerCase();
      const navItem = navigationItems.find((item) => item.shortcut === key);
      if (navItem) {
        e.preventDefault();
        router.push(navItem.href);
      }
      
      // Refresh shortcut
      const actionItem = actionItems.find((item) => item.shortcut === key);
      if (actionItem?.action === "refresh") {
        e.preventDefault();
        window.location.reload();
      }
    }
  }, [router]);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const runCommand = useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        
        {/* Quick Navigation */}
        <CommandGroup heading="Navigation">
          {navigationItems.map((item) => (
            <CommandItem
              key={item.href}
              onSelect={() => runCommand(() => router.push(item.href))}
            >
              <item.icon className="mr-2 h-4 w-4" />
              <span>{item.label}</span>
              {item.shortcut && (
                <CommandShortcut>⌘{item.shortcut.toUpperCase()}</CommandShortcut>
              )}
            </CommandItem>
          ))}
        </CommandGroup>
        
        <CommandSeparator />
        
        {/* Operations */}
        <CommandGroup heading="Operations">
          {operationItems.map((item) => (
            <CommandItem
              key={item.href}
              onSelect={() => runCommand(() => router.push(item.href))}
            >
              <item.icon className="mr-2 h-4 w-4" />
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        
        <CommandSeparator />
        
        {/* Recent Projects */}
        {recentProjects.length > 0 && (
          <>
            <CommandGroup heading="Recent Projects">
              {recentProjects.map((project) => (
                <CommandItem
                  key={project.id}
                  onSelect={() => runCommand(() => router.push(`/projects/${project.id}`))}
                >
                  <FolderKanban className="mr-2 h-4 w-4" />
                  <span>{project.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}
        
        {/* Quick Actions */}
        <CommandGroup heading="Actions">
          {actionItems.map((item) => (
            <CommandItem
              key={item.label}
              onSelect={() => {
                if (item.href) {
                  runCommand(() => router.push(item.href));
                } else if (item.action === "refresh") {
                  runCommand(() => window.location.reload());
                }
              }}
            >
              <item.icon className="mr-2 h-4 w-4" />
              <span>{item.label}</span>
              {item.shortcut && (
                <CommandShortcut>⌘{item.shortcut.toUpperCase()}</CommandShortcut>
              )}
            </CommandItem>
          ))}
        </CommandGroup>
        
        <CommandSeparator />
        
        {/* Help */}
        <CommandGroup heading="Help">
          <CommandItem
            onSelect={() => runCommand(() => {
              // Could open a keyboard shortcuts modal
              alert(`Keyboard Shortcuts:
              
⌘K - Open command palette
⌘P - Projects
⌘R - Runs
⌘O - Protocols
⌘S - Execution
⌘A - Agents
⌘N - New Project
⌘. - Refresh page`);
            })}
          >
            <Keyboard className="mr-2 h-4 w-4" />
            <span>Keyboard Shortcuts</span>
            <CommandShortcut>?</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/settings"))}
          >
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
