export type WatchState = {
  projects: number[];
  protocols: number[];
  lastSeenEventId?: number;
};

const KEY = 'tgz_console_watch_v1';

export function loadWatchState(): WatchState {
  if (typeof window === 'undefined') return { projects: [], protocols: [] };
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return { projects: [], protocols: [] };
    const parsed = JSON.parse(raw) as Partial<WatchState>;
    return {
      projects: Array.isArray(parsed.projects) ? parsed.projects.filter((n) => Number.isFinite(n)) : [],
      protocols: Array.isArray(parsed.protocols) ? parsed.protocols.filter((n) => Number.isFinite(n)) : [],
      lastSeenEventId: typeof parsed.lastSeenEventId === 'number' ? parsed.lastSeenEventId : undefined,
    };
  } catch {
    return { projects: [], protocols: [] };
  }
}

export function saveWatchState(state: WatchState): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(KEY, JSON.stringify(state));
}

export function toggleWatchedProject(projectId: number): WatchState {
  const state = loadWatchState();
  const exists = state.projects.includes(projectId);
  const next = {
    ...state,
    projects: exists ? state.projects.filter((id) => id !== projectId) : [...state.projects, projectId],
  };
  saveWatchState(next);
  return next;
}

export function toggleWatchedProtocol(protocolId: number): WatchState {
  const state = loadWatchState();
  const exists = state.protocols.includes(protocolId);
  const next = {
    ...state,
    protocols: exists ? state.protocols.filter((id) => id !== protocolId) : [...state.protocols, protocolId],
  };
  saveWatchState(next);
  return next;
}

export function setLastSeenEventId(eventId: number): WatchState {
  const state = loadWatchState();
  const next = { ...state, lastSeenEventId: eventId };
  saveWatchState(next);
  return next;
}

