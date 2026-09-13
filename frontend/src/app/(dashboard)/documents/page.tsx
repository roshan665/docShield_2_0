"use client";

import { ShieldCheck, Lock, HardDrive } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DocumentVault } from "@/components/documents/document-vault";

export default function DocumentsPage() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Document Vault & Filings
            </h1>
            <Badge variant="gov" className="font-mono text-[10px] uppercase">
              MinIO S3
            </Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Cryptographically verified documents across authorized cases.
          </p>
        </div>

        {/* Top Status Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 bg-blue-50 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 px-2.5 py-1 rounded-md border border-blue-200 dark:border-blue-900/60 font-mono text-[10px] font-semibold">
            <HardDrive className="h-3 w-3 text-blue-600 dark:text-blue-400" />
            <span>LIVE STORAGE</span>
          </div>

          <div className="flex items-center gap-1.5 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 px-2.5 py-1 rounded-md border border-emerald-200 dark:border-emerald-900/60 font-mono text-[10px] font-semibold">
            <ShieldCheck className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
            <span>SHA-256 VERIFIED</span>
          </div>

          <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-300 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700 font-mono text-[10px] font-semibold">
            <Lock className="h-3 w-3 text-slate-600 dark:text-slate-400" />
            <span>RBAC SCOPED</span>
          </div>
        </div>
      </div>

      {/* Global Document Vault */}
      <DocumentVault canUpload={false} />
    </div>
  );
}
