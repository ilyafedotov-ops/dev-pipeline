/**
 * DevGodzilla Frontend Sentry Integration
 *
 * Optional error tracking via @sentry/nextjs.
 * Completely disabled (no-op) when NEXT_PUBLIC_SENTRY_DSN is not set.
 *
 * Usage – call `initSentry()` at module level in your root layout or a
 * dedicated `sentry.client.config.ts` file:
 *
 *     import { initSentry } from "@/lib/sentry";
 *     initSentry();
 */

interface SentryConfig {
  dsn: string | undefined;
  environment: string;
  release: string;
  tracesSampleRate: number;
  replaysSessionSampleRate: number;
  replaysOnErrorSampleRate: number;
}

function getConfig(): SentryConfig {
  return {
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || undefined,
    environment: process.env.NODE_ENV || "development",
    release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || "0.1.0",
    tracesSampleRate: Number(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0.2,
    ),
    replaysSessionSampleRate: Number(
      process.env.NEXT_PUBLIC_SENTRY_REPLAYS_SESSION_SAMPLE_RATE ?? 0.1,
    ),
    replaysOnErrorSampleRate: Number(
      process.env.NEXT_PUBLIC_SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE ?? 1.0,
    ),
  };
}

let _initialized = false;

export function initSentry(): boolean {
  if (_initialized) return true;
  if (typeof window === "undefined") return false;

  const config = getConfig();
  if (!config.dsn) {
    // eslint-disable-next-line no-console
    console.debug("[sentry] disabled – NEXT_PUBLIC_SENTRY_DSN not set");
    return false;
  }

  try {
    // Dynamic import would be nicer but @sentry/nextjs is designed for static
    // top-level import.  Keep this as a regular require so the bundler can
    // tree-shake when the package is absent.
    const Sentry = require("@sentry/nextjs") as typeof import("@sentry/nextjs");

    Sentry.init({
      dsn: config.dsn,
      environment: config.environment,
      release: config.release,
      tracesSampleRate: config.tracesSampleRate,
      replaysSessionSampleRate: config.replaysSessionSampleRate,
      replaysOnErrorSampleRate: config.replaysOnErrorSampleRate,
      // Privacy: don't send PII by default
      sendDefaultPii: false,
    });

    _initialized = true;
    // eslint-disable-next-line no-console
    console.debug("[sentry] enabled", {
      environment: config.environment,
      release: config.release,
    });
    return true;
  } catch {
    // @sentry/nextjs not installed – graceful no-op
    // eslint-disable-next-line no-console
    console.debug("[sentry] disabled – @sentry/nextjs not installed");
    return false;
  }
}

export function isSentryInitialized(): boolean {
  return _initialized;
}
