/**
 * Generate a unique request ID for tracing.
 * Falls back to timestamp+random if crypto.randomUUID() is unsupported.
 * Note: crypto.randomUUID() requires HTTPS in most browsers (Safari/iOS).
 */
function generateRequestId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID()
    }
  } catch {
    // crypto.randomUUID() may throw in insecure contexts
  }
  // Fallback: timestamp + random string
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: Record<string, unknown>,
  ) {
    super(message)
    this.name = "ApiError"
  }

  get type(): ApiErrorType {
    if (this.status === 401) return "unauthorized"
    if (this.status === 403) return "forbidden"
    if (this.status === 404) return "not_found"
    if (this.status === 409) return "conflict"
    if (this.status === 400) return "validation"
    if (this.status >= 500) return "server_error"
    return "server_error"
  }
}

export type ApiErrorType =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "server_error"
  | "network_error"

interface ApiClientConfig {
  baseUrl: string
  token?: string
  projectTokens?: Record<number, string>
  onUnauthorized?: () => void
}

const STORAGE_KEY = "tasksgodzilla_config"

interface StoredConfig {
  apiBase: string
  token: string
  projectTokens: Record<number, string>
}

function getStoredConfig(): StoredConfig | null {
  if (typeof window === "undefined") return null
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : null
  } catch {
    return null
  }
}

function setStoredConfig(config: Partial<StoredConfig>) {
  if (typeof window === "undefined") return
  const current = getStoredConfig() || { apiBase: "", token: "", projectTokens: {} }
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...config }))
}

class ApiClient {
  private config: ApiClientConfig

  constructor() {
    const stored = getStoredConfig()
    // In browser, use empty string (relative paths go through nginx)
    // On server, use environment variable for SSR
    let defaultBaseUrl = ""
    if (typeof window === "undefined") {
      // Server-side rendering: use env var or default
      defaultBaseUrl = process.env?.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8080"
    }
    // If user has stored a custom API base, use that (for development)
    this.config = {
      baseUrl: stored?.apiBase || defaultBaseUrl,
      token: stored?.token,
      projectTokens: stored?.projectTokens || {},
    }
  }

  configure(config: Partial<ApiClientConfig>) {
    this.config = { ...this.config, ...config }
    setStoredConfig({
      apiBase: this.config.baseUrl,
      token: this.config.token,
      projectTokens: this.config.projectTokens,
    })
  }

  getConfig() {
    return { ...this.config }
  }

  setProjectToken(projectId: number, token: string) {
    this.config.projectTokens = {
      ...this.config.projectTokens,
      [projectId]: token,
    }
    setStoredConfig({ projectTokens: this.config.projectTokens })
  }

  async fetch<T>(path: string, options?: RequestInit & { projectId?: number }): Promise<T> {
    const headers = new Headers(options?.headers)
    headers.set("Content-Type", "application/json")

    if (this.config.token) {
      headers.set("Authorization", `Bearer ${this.config.token}`)
    }

    if (options?.projectId && this.config.projectTokens?.[options.projectId]) {
      headers.set("X-Project-Token", this.config.projectTokens[options.projectId])
    }

    headers.set("X-Request-ID", generateRequestId())

    try {
      const response = await fetch(`${this.config.baseUrl}${path}`, {
        ...options,
        headers,
      })

      if (response.status === 401) {
        this.config.onUnauthorized?.()
        throw new ApiError("Unauthorized", 401)
      }

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new ApiError(body.detail || `Request failed with status ${response.status}`, response.status, body)
      }

      const text = await response.text()
      if (!text) return {} as T
      return JSON.parse(text)
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(error instanceof Error ? error.message : "Network error", 0)
    }
  }

  get<T>(path: string, options?: { projectId?: number }) {
    return this.fetch<T>(path, { method: "GET", ...options })
  }

  post<T>(path: string, body?: unknown, options?: { projectId?: number }) {
    return this.fetch<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    })
  }

  put<T>(path: string, body?: unknown, options?: { projectId?: number }) {
    return this.fetch<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    })
  }

  delete<T>(path: string, options?: { projectId?: number }) {
    return this.fetch<T>(path, { method: "DELETE", ...options })
  }
}

export const apiClient = new ApiClient()
