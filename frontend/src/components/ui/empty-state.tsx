import Link from "next/link";
import { LucideIcon } from "lucide-react";
import { Button } from "./button";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  actionHref?: string;
}

export function EmptyState({ icon: Icon, title, description, actionLabel, onAction, actionHref }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 p-12 text-center transition-colors">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 shadow-sm ring-1 ring-blue-100 dark:ring-blue-900/50">
        <Icon className="h-7 w-7" />
      </div>
      <h3 className="mt-4 text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-slate-500 dark:text-slate-400">{description}</p>
      {actionLabel && onAction && (
        <Button onClick={onAction} size="sm" className="mt-5 bg-blue-600 hover:bg-blue-500 text-white text-xs shadow-sm">
          {actionLabel}
        </Button>
      )}
      {actionLabel && actionHref && !onAction && (
        <Link href={actionHref} className="mt-5">
          <Button size="sm" className="bg-blue-600 hover:bg-blue-500 text-white text-xs shadow-sm">
            {actionLabel}
          </Button>
        </Link>
      )}
    </div>
  );
}
