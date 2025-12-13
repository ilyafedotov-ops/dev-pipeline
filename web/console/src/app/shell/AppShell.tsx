import React from 'react';
import { Link, useLocation } from '@tanstack/react-router';
import { Bell, ChevronRight, GitBranch, Layers, LayoutGrid, ListChecks, Settings, ShieldCheck } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';

import { cn } from '@/lib/cn';
import { apiFetchJson } from '@/api/client';
import { loadWatchState, setLastSeenEventId, toggleWatchedProject, toggleWatchedProtocol } from '@/app/watch/store';
import { useSettingsSnapshot } from '@/app/settings/store';
import { useDocumentVisible } from '@/app/polling';

type EventOut = {
  id: number;
  protocol_run_id: number;
  step_run_id?: number | null;
  event_type: string;
  message: string;
  created_at: string;
  metadata?: Record<string, unknown> | null;
  protocol_name?: string | null;
  project_id?: number | null;
  project_name?: string | null;
};

type NavItem = {
  to: string;
  label: string;
  icon: React.ReactNode;
};

const navItems: NavItem[] = [
  { to: '/projects', label: 'Projects', icon: <LayoutGrid className="h-4 w-4" /> },
  { to: '/runs', label: 'Runs', icon: <ListChecks className="h-4 w-4" /> },
  { to: '/ops/queues', label: 'Ops', icon: <Layers className="h-4 w-4" /> },
  { to: '/policy-packs', label: 'Policy Packs', icon: <ShieldCheck className="h-4 w-4" /> },
  { to: '/settings', label: 'Settings', icon: <Settings className="h-4 w-4" /> },
];

function computeActive(pathname: string, itemTo: string): boolean {
  if (itemTo.startsWith('/ops/')) {
    return pathname === itemTo || pathname.startsWith('/ops/');
  }
  return pathname === itemTo || pathname.startsWith(itemTo + '/');
}

function breadcrumbsFor(pathname: string): Array<{ label: string; to?: string }> {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) return [{ label: 'Home', to: '/projects' }];
  const crumbs: Array<{ label: string; to?: string }> = [{ label: 'Home', to: '/projects' }];
  let accum = '';
  for (let i = 0; i < parts.length; i += 1) {
    const p = parts[i]!;
    accum += `/${p}`;
    const label = p.replace(/-/g, ' ');
    crumbs.push({ label, to: accum });
  }
  // Avoid linking the last breadcrumb to itself (prevents unnecessary reloads)
  if (crumbs.length > 0) {
    crumbs[crumbs.length - 1] = { label: crumbs[crumbs.length - 1]!.label };
  }
  return crumbs;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const crumbs = breadcrumbsFor(location.pathname);
  const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';
  const [inboxOpen, setInboxOpen] = React.useState(false);
  const [watchedOnly, setWatchedOnly] = React.useState(true);
  const [watchState, setWatchState] = React.useState(() => loadWatchState());
  const settings = useSettingsSnapshot();
  const visible = useDocumentVisible();
  const pollEnabled = settings.polling.enabled && (!settings.polling.disableInBackground || visible);
  const { data: authState } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const resp = await fetch(`${apiBase}/auth/me`, { credentials: 'include' });
      if (resp.status === 401) return { enabled: true, user: null } as const;
      if (!resp.ok) throw new Error(`auth/me failed: ${resp.status}`);
      return (await resp.json()) as { enabled: boolean; user: { name?: string; email?: string } | null };
    },
    staleTime: 30_000,
    retry: 0,
  });
  const me = authState?.user ?? null;
  const oidcEnabled = authState?.enabled ?? false;

  const events = useQuery({
    queryKey: ['ops', 'events', 'recent', 'inbox'],
    enabled: inboxOpen,
    queryFn: async () => await apiFetchJson<EventOut[]>('/events?limit=50'),
    staleTime: 5_000,
    refetchInterval: pollEnabled ? settings.polling.intervalsMs.recentEvents : false,
    retry: 1,
  });

  const filteredEvents = React.useMemo(() => {
    const list = events.data ?? [];
    if (!watchedOnly) return list;
    const watchedProjects = new Set(watchState.projects);
    const watchedProtocols = new Set(watchState.protocols);
    return list.filter((e) => {
      const pid = typeof e.project_id === 'number' ? e.project_id : null;
      const pr = typeof e.protocol_run_id === 'number' ? e.protocol_run_id : null;
      return (pid !== null && watchedProjects.has(pid)) || (pr !== null && watchedProtocols.has(pr));
    });
  }, [events.data, watchedOnly, watchState.projects, watchState.protocols]);

  return (
    <div className="min-h-screen">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 flex-col border-r border-border bg-bg-panel md:flex">
          <div className="flex items-center justify-between px-4 py-4">
            <div className="text-sm font-semibold tracking-wide">TasksGodzilla</div>
            <div className="text-xs text-fg-muted">console</div>
          </div>
          <nav className="px-2 py-2">
            {navItems.map((item) => {
              const active = computeActive(location.pathname, item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    'mb-1 flex items-center gap-2 rounded-md px-3 py-2 text-sm text-fg-muted hover:bg-bg-muted hover:text-fg',
                    active && 'bg-bg-muted text-fg',
                  )}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto px-4 py-4 text-xs text-fg-muted">
            <div className="flex items-center gap-2">
              <GitBranch className="h-3 w-3" />
              <span>env: {import.meta.env.MODE}</span>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-border bg-bg-panel px-4 py-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1 text-sm font-medium">
                {crumbs.map((c, idx) => (
                  <React.Fragment key={`${c.label}-${idx}`}>
                    {idx > 0 && <ChevronRight className="h-3 w-3 text-fg-muted" />}
                    {c.to ? (
                      <Link to={c.to} className="text-fg-muted hover:text-fg">
                        {c.label}
                      </Link>
                    ) : (
                      <span className="text-fg">{c.label}</span>
                    )}
                  </React.Fragment>
                ))}
              </div>
              <div className="text-xs text-fg-muted">SSO-first console · live ops</div>
            </div>
            <div className="flex items-center gap-3">
              <Dialog.Root
                open={inboxOpen}
                onOpenChange={(open) => {
                  setInboxOpen(open);
                  if (open) {
                    setWatchState(loadWatchState());
                    // Mark as seen when opening (best-effort).
                    const latest = (events.data ?? [])[0]?.id;
                    if (typeof latest === 'number') setWatchState(setLastSeenEventId(latest));
                  }
                }}
              >
                <Dialog.Trigger asChild>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-md border border-border bg-bg-muted px-3 py-2 text-xs text-fg hover:bg-bg-panel"
                  >
                    <Bell className="h-4 w-4" />
                    <span>Inbox</span>
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 bg-black/50" />
                  <Dialog.Content className="fixed right-4 top-4 h-[85vh] w-[min(720px,calc(100vw-2rem))] overflow-hidden rounded-md border border-border bg-bg-panel shadow-xl">
                    <div className="flex items-center justify-between border-b border-border px-4 py-3">
                      <div>
                        <Dialog.Title className="text-sm font-medium">Inbox</Dialog.Title>
                        <div className="text-xs text-fg-muted">Recent activity, failures, and watched updates.</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="flex items-center gap-2 text-xs text-fg-muted">
                          <input type="checkbox" checked={watchedOnly} onChange={(e) => setWatchedOnly(e.target.checked)} />
                          <span>Watched only</span>
                        </label>
                        <Dialog.Close asChild>
                          <button className="rounded-md border border-border bg-bg-muted px-3 py-2 text-xs hover:bg-bg-panel">
                            Close
                          </button>
                        </Dialog.Close>
                      </div>
                    </div>

                    <Tabs.Root defaultValue="activity" className="flex h-full flex-col">
                      <Tabs.List className="flex gap-2 border-b border-border px-4 py-2">
                        <Tabs.Trigger
                          value="activity"
                          className="rounded-md px-3 py-2 text-sm text-fg-muted data-[state=active]:bg-bg-muted data-[state=active]:text-fg"
                        >
                          Activity
                        </Tabs.Trigger>
                        <Tabs.Trigger
                          value="watch"
                          className="rounded-md px-3 py-2 text-sm text-fg-muted data-[state=active]:bg-bg-muted data-[state=active]:text-fg"
                        >
                          Watches
                        </Tabs.Trigger>
                      </Tabs.List>

                      <Tabs.Content value="activity" className="min-h-0 flex-1 overflow-auto p-4">
                        {(filteredEvents ?? []).length === 0 ? (
                          <div className="text-sm text-fg-muted">{events.isLoading ? 'Loading…' : 'No events.'}</div>
                        ) : (
                          <div className="space-y-2">
                            {filteredEvents.map((e) => {
                              const isNew = typeof watchState.lastSeenEventId === 'number' ? e.id > watchState.lastSeenEventId : false;
                              return (
                                <div
                                  key={e.id}
                                  className={cn(
                                    'rounded-md border border-border bg-bg-muted p-3',
                                    isNew && 'border-sky-400/40',
                                  )}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="text-xs text-fg-muted">
                                      #{e.id} · {e.event_type} · {e.created_at}
                                    </div>
                                    <div className="flex items-center gap-2">
                                      {typeof e.project_id === 'number' ? (
                                        <Link
                                          to="/projects/$projectId"
                                          params={{ projectId: String(e.project_id) }}
                                          className="text-xs text-sky-300 hover:underline"
                                        >
                                          project:{e.project_id}
                                        </Link>
                                      ) : null}
                                      <Link
                                        to="/protocols/$protocolId"
                                        params={{ protocolId: String(e.protocol_run_id) }}
                                        className="text-xs text-sky-300 hover:underline"
                                      >
                                        protocol:{e.protocol_run_id}
                                      </Link>
                                    </div>
                                  </div>
                                  <div className="mt-1 text-sm text-fg">{e.message}</div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </Tabs.Content>

                      <Tabs.Content value="watch" className="min-h-0 flex-1 overflow-auto p-4">
                        <div className="grid gap-3 md:grid-cols-2">
                          <div className="rounded-md border border-border bg-bg-muted p-3">
                            <div className="text-sm font-medium">Watched projects</div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {watchState.projects.length === 0 ? (
                                <div className="text-sm text-fg-muted">None</div>
                              ) : (
                                watchState.projects.map((id) => (
                                  <button
                                    key={id}
                                    type="button"
                                    onClick={() => setWatchState(toggleWatchedProject(id))}
                                    className="rounded-md border border-border bg-bg-panel px-3 py-2 text-xs hover:bg-bg-muted"
                                  >
                                    {id} ×
                                  </button>
                                ))
                              )}
                            </div>
                          </div>
                          <div className="rounded-md border border-border bg-bg-muted p-3">
                            <div className="text-sm font-medium">Watched protocols</div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {watchState.protocols.length === 0 ? (
                                <div className="text-sm text-fg-muted">None</div>
                              ) : (
                                watchState.protocols.map((id) => (
                                  <button
                                    key={id}
                                    type="button"
                                    onClick={() => setWatchState(toggleWatchedProtocol(id))}
                                    className="rounded-md border border-border bg-bg-panel px-3 py-2 text-xs hover:bg-bg-muted"
                                  >
                                    {id} ×
                                  </button>
                                ))
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="mt-4 rounded-md border border-border bg-bg-muted p-3 text-xs text-fg-muted">
                          Tip: use the Watch buttons on Project/Protocol pages to subscribe.
                        </div>
                      </Tabs.Content>
                    </Tabs.Root>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              {me ? (
                <div className="rounded-md border border-border bg-bg-muted px-3 py-2 text-xs text-fg">
                  {me.name || me.email || 'User'}
                </div>
              ) : oidcEnabled ? (
                <a
                  className="rounded-md border border-border bg-bg-muted px-3 py-2 text-xs text-fg hover:bg-bg-panel"
                  href={`${apiBase}/auth/login?next=${encodeURIComponent(
                    typeof window !== 'undefined' ? window.location.pathname + window.location.search : '/console2',
                  )}`}
                >
                  Sign in
                </a>
              ) : (
                <div className="rounded-md border border-border bg-bg-muted px-3 py-2 text-xs text-fg-muted">
                  Auth: disabled
                </div>
              )}
            </div>
          </header>

          <main className="min-w-0 flex-1 p-4">{children}</main>
        </div>
      </div>
    </div>
  );
}
