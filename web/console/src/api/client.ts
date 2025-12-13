import { loadSettings } from '@/app/settings/store';

function normalizeBase(base: string): string {
  const b = base.trim();
  if (!b) return '';
  return b.endsWith('/') ? b.slice(0, -1) : b;
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function apiFetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const settings = loadSettings();
  const envBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';
  const base = normalizeBase(settings.api.apiBase || envBase);

  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  headers.set('X-Request-ID', crypto.randomUUID());
  if (settings.api.bearerToken) {
    headers.set('Authorization', `Bearer ${settings.api.bearerToken}`);
  }
  if (settings.api.projectToken) {
    headers.set('X-Project-Token', settings.api.projectToken);
  }

  const resp = await fetch(`${base}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });

  const contentType = resp.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const body = isJson ? await resp.json().catch(() => null) : await resp.text().catch(() => '');

  if (!resp.ok) {
    const message =
      typeof body === 'object' && body && 'detail' in (body as any) ? String((body as any).detail) : `Request failed`;
    throw new ApiError(message, resp.status, body);
  }

  return body as T;
}

