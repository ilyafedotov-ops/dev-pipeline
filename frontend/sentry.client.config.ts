/**
 * Sentry Client Configuration (Next.js convention)
 *
 * Next.js automatically loads `sentry.client.config.ts` at the root of the
 * frontend directory when present.  This file initialises Sentry for the
 * browser bundle.
 *
 * Requires @sentry/nextjs to be installed:
 *   pnpm add @sentry/nextjs
 *
 * Set NEXT_PUBLIC_SENTRY_DSN in your environment to enable.
 */

import { initSentry } from "@/lib/sentry";

initSentry();
