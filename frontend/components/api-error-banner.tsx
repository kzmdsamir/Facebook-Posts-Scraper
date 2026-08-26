"use client";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ApiErrorBannerProps {
  title: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  variant?: "danger" | "warning";
  className?: string;
}

/** Friendly inline error banner with an optional retry action. */
export function ApiErrorBanner({
  title,
  message,
  onRetry,
  retryLabel = "Try again",
  variant = "danger",
  className,
}: ApiErrorBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex w-full flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
        variant === "danger"
          ? "border-destructive/30 bg-destructive/10 text-destructive"
          : "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
        className
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-5">{title}</p>
          <p className="mt-0.5 break-words text-sm opacity-90">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <Button
          type="button"
          variant={variant === "danger" ? "destructive" : "outline"}
          size="sm"
          onClick={onRetry}
          className="shrink-0"
        >
          {retryLabel}
        </Button>
      ) : null}
    </div>
  );
}