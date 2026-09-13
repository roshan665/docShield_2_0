import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "gov" | "ai";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "border-transparent bg-slate-900 text-slate-50 shadow hover:bg-slate-900/80 dark:bg-slate-50 dark:text-slate-900",
    secondary: "border-transparent bg-slate-100 text-slate-900 hover:bg-slate-100/80 dark:bg-slate-800 dark:text-slate-100",
    destructive: "border-transparent bg-rose-600 text-white shadow hover:bg-rose-600/80",
    outline: "text-slate-950 border border-slate-200 dark:text-slate-100 dark:border-slate-800",
    success: "border-transparent bg-emerald-600 text-white shadow hover:bg-emerald-600/80",
    warning: "border-transparent bg-amber-600 text-white shadow hover:bg-amber-600/80",
    gov: "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900/50 dark:bg-blue-950/60 dark:text-blue-300 shadow-sm",
    ai: "border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-900/50 dark:bg-violet-950/60 dark:text-violet-300 shadow-sm",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-slate-950 focus:ring-offset-2",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
