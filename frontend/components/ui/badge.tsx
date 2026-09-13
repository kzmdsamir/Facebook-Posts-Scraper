import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type BadgeVariant =
  | "default"
  | "secondary"
  | "outline"
  | "destructive"
  | "success"
  | "warning"
  | "blue"
  | "purple"
  | "amber";

const variantClasses: Record<BadgeVariant, string> = {
  default: "border-border bg-secondary text-secondary-foreground",
  secondary: "border-border bg-muted text-muted-foreground",
  outline: "border-border text-muted-foreground bg-transparent",
  destructive: "bg-foreground text-background border-transparent",
  success: "border-border bg-muted text-foreground",
  warning: "border-border bg-muted text-foreground",
  blue: "border-border bg-muted text-muted-foreground",
  purple: "border-border bg-muted text-muted-foreground",
  amber: "border-border bg-muted text-muted-foreground",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-medium transition-colors",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}