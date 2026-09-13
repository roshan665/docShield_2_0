"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error boundary triggered:", error);
  }, [error]);

  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center p-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-red-600">
        <AlertTriangle className="h-8 w-8" />
      </div>
      <h2 className="mt-4 text-xl font-bold text-slate-900">Application Error</h2>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        An unexpected error occurred within the secure session. All security boundaries remain active.
      </p>
      <Button onClick={() => reset()} className="mt-6">
        Attempt Safe Recovery
      </Button>
    </div>
  );
}
