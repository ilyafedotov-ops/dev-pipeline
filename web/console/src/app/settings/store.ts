import React from 'react';

export type Density = 'comfortable' | 'compact';
export type TimeFormat = 'relative' | 'absolute';

export type PollingSettings = {
  enabled: boolean;
  disableInBackground: boolean;
  intervalsMs: {
    protocolSteps: number;
    protocolEvents: number;
    onboardingSummary: number;
    queueStats: number;
    queueJobs: number;
    recentEvents: number;
  };
};

export type ApiSettings = {
  apiBase: string; // optional override (dev / non-same-origin)
  bearerToken: string; // fallback auth (when OIDC disabled)
  projectToken: string; // optional fallback per-project token
};

export type AppSettings = {
  theme: 'dark';
  density: Density;
  timeFormat: TimeFormat;
  polling: PollingSettings;
  api: ApiSettings;
};

const STORAGE_KEY = 'tgz_console_settings_v1';

export function defaultSettings(): AppSettings {
  return {
    theme: 'dark',
    density: 'comfortable',
    timeFormat: 'relative',
    polling: {
      enabled: true,
      disableInBackground: true,
      intervalsMs: {
        protocolSteps: 5000,
        protocolEvents: 5000,
        onboardingSummary: 3000,
        queueStats: 10000,
        queueJobs: 5000,
        recentEvents: 10000,
      },
    },
    api: {
      apiBase: '',
      bearerToken: '',
      projectToken: '',
    },
  };
}

export function loadSettings(): AppSettings {
  const base = defaultSettings();
  if (typeof window === 'undefined') return base;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return base;
    const parsed = JSON.parse(raw) as Partial<AppSettings>;
    return {
      ...base,
      ...parsed,
      polling: {
        ...base.polling,
        ...(parsed.polling ?? {}),
        intervalsMs: {
          ...base.polling.intervalsMs,
          ...(parsed.polling?.intervalsMs ?? {}),
        },
      },
      api: {
        ...base.api,
        ...(parsed.api ?? {}),
      },
    };
  } catch {
    return base;
  }
}

export function saveSettings(next: AppSettings): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  window.dispatchEvent(new Event('tgz_settings_changed'));
}

export function useSettingsSnapshot(): AppSettings {
  const [settings, setSettings] = React.useState<AppSettings>(() => loadSettings());
  React.useEffect(() => {
    const update = () => setSettings(loadSettings());
    window.addEventListener('storage', update);
    window.addEventListener('tgz_settings_changed', update);
    return () => {
      window.removeEventListener('storage', update);
      window.removeEventListener('tgz_settings_changed', update);
    };
  }, []);
  return settings;
}

