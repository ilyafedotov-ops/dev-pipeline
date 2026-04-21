"use client";

import type { ReactElement } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface DisabledTooltipProps {
  reason: string | null;
  children: ReactElement;
}

/**
 * Wraps a (possibly-disabled) control and shows a reason tooltip on hover when
 * `reason` is non-null. When `reason` is null, renders the child as-is.
 *
 * A <span> wraps the child because Radix Tooltip needs an element that
 * emits pointer events — disabled <button> elements don't.
 */
export function DisabledTooltip({ reason, children }: DisabledTooltipProps) {
  if (!reason) return children;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex">{children}</span>
      </TooltipTrigger>
      <TooltipContent>{reason}</TooltipContent>
    </Tooltip>
  );
}
