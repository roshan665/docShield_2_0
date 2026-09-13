import { LoadingSpinner } from "@/components/ui/loading-spinner";

export default function Loading() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
      <div className="text-center">
        <LoadingSpinner />
        <p className="mt-2 text-sm text-slate-500 font-medium">Verifying security context...</p>
      </div>
    </div>
  );
}
