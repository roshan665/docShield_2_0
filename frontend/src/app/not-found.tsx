import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ShieldAlert } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center p-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-700">
        <ShieldAlert className="h-8 w-8" />
      </div>
      <h2 className="mt-4 text-2xl font-bold text-slate-900">Resource Not Found</h2>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        The requested case, document, or evidence record does not exist or you lack authorized access.
      </p>
      <Link href="/dashboard" className="mt-6">
        <Button>Return to Dashboard</Button>
      </Link>
    </div>
  );
}
