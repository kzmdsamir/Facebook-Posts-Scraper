import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * MailAccess display system.
 * Eyebrow/PageHeading/SectionHeading build the big mono-headed hero blocks;
 * StatBox is the flat footer-style label/value row. All tokens come from the
 * stylesheet, so the light theme renders the exact white/black/red spec.
 */
export function Eyebrow({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        "mb-4 block font-sans font-light text-[10px] uppercase tracking-[0.2em] text-highlight",
        className
      )}
      {...props}
    />
  );
}

export function PageHeading({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h1
      className={cn(
        "font-medium tracking-tighter leading-none text-5xl md:text-6xl text-foreground mb-8",
        className
      )}
      {...props}
    />
  );
}

export function SectionHeading({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cn("font-medium tracking-tight text-xl text-foreground mb-3", className)} {...props} />
  );
}

export interface StatBoxProps extends HTMLAttributes<HTMLDivElement> {
  label: ReactNode;
  value: ReactNode;
}

export function StatBox({ label, value, className, ...props }: StatBoxProps) {
  return (
    <div
      className={cn(
        "flex justify-between items-center py-3 border-b border-border font-mono text-xs text-muted-foreground last:border-b-0",
        className
      )}
      {...props}
    >
      <span>{label}</span>
      <span className="text-foreground tabular-nums">{value}</span>
    </div>
  );
}

export function FieldLabel({ className, ...props }: HTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn(
        "block font-sans font-light text-[10px] uppercase tracking-[0.2em] text-muted-foreground",
        className
      )}
      {...props}
    />
  );
}

/** Small bordered flat chip, used for counts/status inside grids. */
export function Chip({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground",
        className
      )}
      {...props}
    />
  );
}