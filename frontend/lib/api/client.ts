/**
 * Generate a unique request ID for tracing.
 * Falls back to timestamp+random if crypto.randomUUID() is unsupported.
 * Note: crypto.randomUUID() requires HTTPS in most browsers (Safari/iOS).
 */
function generateRequestId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // crypto.randomUUID() may throw in insecure contexts
  }
  // Fallback: timestamp + random string
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Sleep utility for retry delays.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Calculate exponential backoff delay.
 */
function calculateBackoff(attempt: number, baseDelay: number, maxDelay: number): number {
  const jitter = Math.random() * 100; // Add jitter to prevent thundering herd
  return Math.min(baseDelay * Math.pow(2, attempt) + jitter, maxDelay);
}

/**
 * Check if an error is retryable.
 */
function isRetryableError(error: unknown): boolean {
  if (error instanceof ApiError) {
    // Retry on server errors and network errors
    return error.status >= 500 || error.status === 0 || error.type === "network_error";
  }
  // Retry on network failures
  return error instanceof TypeError && error.message.includes("fetch");
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiError";
  }

  get type(): ApiErrorType {
    if (this.status === 401) return "unauthorized";
    if (this.status === 403) return "forbidden";
    if (this.status === 404) return "not_found";
    if (this.status === 409) return "conflict";
    if (this.status === 400) return "validation";
    if (this.status >= 500) return "server_error";
    return "server_error";
  }
}

export type ApiErrorType =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "server_error"
  | "network_error";

/**
 * Retry configuration options.
 */
export interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  retryableStatuses: number[];
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 10000,
  retryableStatuses: [0, 429, 500, 502, 503, 504],
};

interface ApiClientConfig {
  baseUrl: string;
  token?: string;
  projectTokens?: Record<number, string>;
  onUnauthorized?: () => void;
  retry?: Partial<RetryConfig>;
}

const STORAGE_KEY = "devgodzilla_config";

interface StoredConfig {
  apiBase: string;
  token: string;
  projectTokens: Record<number, string>;
}

function getStoredConfig(): StoredConfig | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

function setStoredConfig(config: Partial<StoredConfig>) {
  if (typeof window === "undefined") return;
  const current = getStoredConfig() || { apiBase: "", token: "", projectTokens: {} };
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...config }));
}

class ApiClient {
  private config: ApiClientConfig;
  private retryConfig: RetryConfig;

  constructor() {
    const stored = getStoredConfig();
    // In browser, use empty string (relative paths go through nginx)
    // On server, use environment variable for SSR
    // In browser, use /api path so Next.js rewrites (basePath:false) proxy to backend
    // On server, use env var or default to localhost:8080
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8080";
    let defaultBaseUrl = typeof window === "undefined" ? apiBaseUrl : "/api";
    // If user has stored a custom API base, use that (for development)
    this.config = {
      baseUrl: stored?.apiBase || defaultBaseUrl,
      token: stored?.token,
      projectTokens: stored?.projectTokens || {},
    };
    this.retryConfig = DEFAULT_RETRY_CONFIG;
  }

  configure(config: Partial<ApiClientConfig>) {
    this.config = { ...this.config, ...config };
    if (config.retry) {
      this.retryConfig = { ...DEFAULT_RETRY_CONFIG, ...config.retry };
    }
    setStoredConfig({
      apiBase: this.config.baseUrl,
      token: this.config.token,
      projectTokens: this.config.projectTokens,
    });
  }

  getConfig() {
    return { ...this.config };
  }

  setProjectToken(projectId: number, token: string) {
    this.config.projectTokens = {
      ...this.config.projectTokens,
      [projectId]: token,
    };
    setStoredConfig({ projectTokens: this.config.projectTokens });
  }

  /**
   * Make a fetch request with automatic retry logic.
   */
  async fetch<T>(
    path: string,
    options?: RequestInit & { projectId?: number; skipRetry?: boolean }
  ): Promise<T> {
    const { skipRetry, ...fetchOptions } = options || {};
    
    if (skipRetry) {
      return this.singleFetch<T>(path, fetchOptions);
    }

    let lastError: unknown;
    const maxRetries = this.retryConfig.maxRetries;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        return await this.singleFetch<T>(path, fetchOptions);
      } catch (error) {
        lastError = error;

        // Don't retry on client errors (4xx) except 429
        if (error instanceof ApiError) {
          if (!this.retryConfig.retryableStatuses.includes(error.status)) {
            throw error;
          }
        }

        // Check if we should retry
        if (attempt < maxRetries && isRetryableError(error)) {
          const delay = calculateBackoff(
            attempt,
            this.retryConfig.baseDelay,
            this.retryConfig.maxDelay
          );
          console.warn(`API request failed, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries})`, {
            path,
            error: error instanceof Error ? error.message : error,
          });
          await sleep(delay);
        } else {
          throw error;
        }
      }
    }

    throw lastError;
  }

  private async singleFetch<T>(
    path: string,
    options?: RequestInit & { projectId?: number }
  ): Promise<T> {
    const headers = new Headers(options?.headers);
    headers.set("Content-Type", "application/json");

    if (this.config.token) {
      headers.set("Authorization", `Bearer ${this.config.token}`);
    }

    if (options?.projectId && this.config.projectTokens?.[options.projectId]) {
      headers.set("X-Project-Token", this.config.projectTokens[options.projectId]);
    }

    headers.set("X-Request-ID", generateRequestId());

    try {
      const response = await fetch(`${this.config.baseUrl}${path}`, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        this.config.onUnauthorized?.();
        throw new ApiError("Unauthorized", 401);
      }

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiError(
          body.detail || `Request failed with status ${response.status}`,
          response.status,
          body
        );
      }

      const text = await response.text();
      if (!text) return {} as T;

      // Check if response is HTML (e.g., nginx error page)
      if (text.trim().startsWith("<!DOCTYPE") || text.trim().startsWith("<html")) {
        throw new ApiError(
          `API returned HTML instead of JSON. The backend may be unavailable.`,
          response.status || 502
        );
      }

      try {
        return JSON.parse(text);
      } catch {
        throw new ApiError(
          `Invalid JSON response: ${text.slice(0, 100)}...`,
          response.status || 500
        );
      }
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(error instanceof Error ? error.message : "Network error", 0);
    }
  }

  get<T>(path: string, options?: { projectId?: number }) {
    return this.fetch<T>(path, { method: "GET", ...options });
  }

  post<T>(path: string, body?: unknown, options?: { projectId?: number }) {
    return this.fetch<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    });
  }

  put<T>(path: string, body?: unknown, options?: { projectId?: number }) {
    return this.fetch<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    });
  }

  delete<T>(path: string, options?: { projectId?: number }) {
    return this.fetch<T>(path, { method: "DELETE", ...options });
  }

  patch<T>(path: string, body?: unknown, options?: { projectId?: number }) {
    return this.fetch<T>(path, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    });
  }
}

export const apiClient = new ApiClient();
