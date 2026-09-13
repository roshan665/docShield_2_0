import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function LoadingSpinner({ className, size = "md" }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "h-4 w-4",
    md: "h-8 w-8",
    lg: "h-12 w-12",
  }[size];

  if (size === "sm") {
    return <Loader2 className={cn("animate-spin text-current", sizeClasses, className)} />;
  }

  return (
    <div className="flex h-full w-full items-center justify-center p-8">
      <Loader2 className={cn("animate-spin text-slate-700 dark:text-slate-300", sizeClasses, className)} />
    </div>
  );
}
