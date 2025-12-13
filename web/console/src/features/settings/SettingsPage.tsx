import React from 'react';
import { Link, useSearch } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';

import { loadSettings, saveSettings, type AppSettings } from '@/app/settings/store';

const tabs = [
  { key: 'profile', label: 'Profile' },
  { key: 'preferences', label: 'Preferences' },
  { key: 'live_updates', label: 'Live updates' },
  { key: 'integrations', label: 'Integrations' },
  { key: 'shortcuts', label: 'Shortcuts' },
  { key: 'advanced', label: 'Advanced' },
] as const;

export function SettingsPage() {
  const search = useSearch({ from: '/settings' });
  const activeTab = search.tab ?? 'profile';
  const apiBaseFromEnv = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

  const [settings, setSettings] = React.useState<AppSettings>(() => loadSettings());
  React.useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  const { data: authState } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const resp = await fetch(`${apiBaseFromEnv}/auth/me`, { credentials: 'include' });
      if (resp.status === 401) return { enabled: true, user: null } as const;
      if (!resp.ok) throw new Error(`auth/me failed: ${resp.status}`);
      return (await resp.json()) as { enabled: boolean; user: { name?: string; email?: string } | null };
    },
    staleTime: 30_000,
    retry: 0,
  });

  const oidcEnabled = authState?.enabled ?? false;
  const user = authState?.user ?? null;

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const resp = await fetch(`${apiBaseFromEnv}/health`, { credentials: 'include' });
      if (!resp.ok) throw new Error(`health failed: ${resp.status}`);
      return (await resp.json()) as { status: string };
    },
    staleTime: 10_000,
    retry: 1,
  });

  async function logout() {
    await fetch(`${apiBaseFromEnv}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
    window.location.reload();
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Settings</h1>
        <div className="text-xs text-fg-muted">API: {health?.status ?? '...'}</div>
      </div>

      <div className="flex flex-wrap gap-2 rounded-md border border-border bg-bg-panel p-2">
        {tabs.map((t) => (
          <Link
            key={t.key}
            to="/settings"
            search={{ tab: t.key }}
            className={[
              'rounded-md px-3 py-2 text-sm',
              activeTab === t.key ? 'bg-bg-muted text-fg' : 'text-fg-muted hover:bg-bg-muted hover:text-fg',
            ].join(' ')}
          >
            {t.label}
          </Link>
        ))}
      </div>

      {activeTab === 'profile' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Profile</div>
          <div className="mt-1 text-xs text-fg-muted">SSO identity and session management.</div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-border bg-bg-muted p-3">
              <div className="text-xs text-fg-muted">Auth mode</div>
              <div className="mt-1 text-sm">{oidcEnabled ? 'OIDC/SSO (cookie session)' : 'Disabled / token fallback'}</div>
            </div>
            <div className="rounded-md border border-border bg-bg-muted p-3">
              <div className="text-xs text-fg-muted">User</div>
              <div className="mt-1 text-sm">{user?.name || user?.email || (oidcEnabled ? 'Not signed in' : '—')}</div>
            </div>
          </div>

          {oidcEnabled && (
            <div className="mt-4">
              <button
                type="button"
                className="rounded-md border border-border bg-bg-muted px-3 py-2 text-sm hover:bg-bg-panel"
                onClick={logout}
              >
                Log out
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'preferences' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Preferences</div>
          <div className="mt-1 text-xs text-fg-muted">UI density and time formatting.</div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="grid gap-2 text-sm">
              <span className="text-xs text-fg-muted">Density</span>
              <select
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                value={settings.density}
                onChange={(e) => setSettings({ ...settings, density: e.target.value as AppSettings['density'] })}
              >
                <option value="comfortable">Comfortable</option>
                <option value="compact">Compact</option>
              </select>
            </label>

            <label className="grid gap-2 text-sm">
              <span className="text-xs text-fg-muted">Time format</span>
              <select
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                value={settings.timeFormat}
                onChange={(e) => setSettings({ ...settings, timeFormat: e.target.value as AppSettings['timeFormat'] })}
              >
                <option value="relative">Relative</option>
                <option value="absolute">Absolute</option>
              </select>
            </label>
          </div>
        </div>
      )}

      {activeTab === 'live_updates' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Live updates</div>
          <div className="mt-1 text-xs text-fg-muted">Polling toggles and intervals (ms).</div>

          <div className="mt-4 flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={settings.polling.enabled}
                onChange={(e) => setSettings({ ...settings, polling: { ...settings.polling, enabled: e.target.checked } })}
              />
              <span>Enable polling</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={settings.polling.disableInBackground}
                onChange={(e) =>
                  setSettings({ ...settings, polling: { ...settings.polling, disableInBackground: e.target.checked } })
                }
              />
              <span>Pause in background tab</span>
            </label>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {Object.entries(settings.polling.intervalsMs).map(([key, value]) => (
              <label key={key} className="grid gap-2 text-sm">
                <span className="text-xs text-fg-muted">{key}</span>
                <input
                  className="rounded-md border border-border bg-bg-muted px-3 py-2"
                  inputMode="numeric"
                  value={String(value)}
                  onChange={(e) => {
                    const nextVal = Number(e.target.value);
                    setSettings({
                      ...settings,
                      polling: {
                        ...settings.polling,
                        intervalsMs: { ...settings.polling.intervalsMs, [key]: Number.isFinite(nextVal) ? nextVal : value },
                      },
                    });
                  }}
                />
              </label>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'integrations' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Integrations</div>
          <div className="mt-1 text-xs text-fg-muted">Status surfaces for Git/CI (read-only by default).</div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-border bg-bg-muted p-3">
              <div className="text-xs text-fg-muted">Git</div>
              <div className="mt-1 text-sm">Configured per-project (branches + PR links coming next).</div>
            </div>
            <div className="rounded-md border border-border bg-bg-muted p-3">
              <div className="text-xs text-fg-muted">CI</div>
              <div className="mt-1 text-sm">Webhook-driven status already lands in Events; UI surfaces are next.</div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'shortcuts' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Keyboard shortcuts</div>
          <div className="mt-1 text-xs text-fg-muted">Power-user flows (command palette will be added).</div>

          <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-fg-muted">
            <li>
              <span className="text-fg">Cmd/Ctrl+K</span> — command palette (planned)
            </li>
            <li>
              <span className="text-fg">/</span> — focus search (planned)
            </li>
            <li>
              <span className="text-fg">Esc</span> — close dialog / drawer
            </li>
          </ul>
        </div>
      )}

      {activeTab === 'advanced' && (
        <div className="rounded-md border border-border bg-bg-panel p-4">
          <div className="text-sm font-medium">Advanced</div>
          <div className="mt-1 text-xs text-fg-muted">
            Token-based access is a fallback for deployments without OIDC/SSO.
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="grid gap-2 text-sm">
              <span className="text-xs text-fg-muted">API base override</span>
              <input
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                placeholder="(empty = same origin)"
                value={settings.api.apiBase}
                onChange={(e) => setSettings({ ...settings, api: { ...settings.api, apiBase: e.target.value } })}
              />
            </label>
            <label className="grid gap-2 text-sm">
              <span className="text-xs text-fg-muted">Bearer token</span>
              <input
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                placeholder={oidcEnabled ? 'Not needed when OIDC is enabled' : 'Bearer …'}
                value={settings.api.bearerToken}
                onChange={(e) => setSettings({ ...settings, api: { ...settings.api, bearerToken: e.target.value } })}
              />
            </label>
            <label className="grid gap-2 text-sm">
              <span className="text-xs text-fg-muted">Project token</span>
              <input
                className="rounded-md border border-border bg-bg-muted px-3 py-2"
                placeholder="X-Project-Token"
                value={settings.api.projectToken}
                onChange={(e) => setSettings({ ...settings, api: { ...settings.api, projectToken: e.target.value } })}
              />
            </label>
          </div>

          <div className="mt-4 rounded-md border border-border bg-bg-muted p-3 text-xs text-fg-muted">
            Note: tokens are stored in <span className="text-fg">localStorage</span>. Prefer OIDC in production.
          </div>
        </div>
      )}
    </div>
  );
}
