import { ShieldCheck, ArrowRightLeft, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EvidenceVault } from "@/components/evidence/evidence-vault";

export default function EvidencePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Central Evidence Vault
            </h1>
            <Badge variant="gov" className="font-mono text-[10px] uppercase">
              Chain-of-Custody
            </Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            SECURE &bull; VERIFIED &bull; TRACEABLE &bull; Sec. 63/65B Bharatiya Sakshya Adhiniyam, 2023 Compliant Evidence Repository
          </p>
        </div>

        {/* Security & Protocol Badges */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 px-2.5 py-1 rounded-md border border-emerald-200 dark:border-emerald-900/60 font-mono text-[10px] font-semibold">
            <ShieldCheck className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
            <span>CHAIN VERIFIED</span>
          </div>

          <div className="flex items-center gap-1.5 bg-blue-50 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300 px-2.5 py-1 rounded-md border border-blue-200 dark:border-blue-900/60 font-mono text-[10px] font-semibold">
            <ArrowRightLeft className="h-3 w-3 text-blue-600 dark:text-blue-400" />
            <span>2-PHASE HANDOVER</span>
          </div>

          <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-300 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700 font-mono text-[10px] font-semibold">
            <Lock className="h-3 w-3 text-slate-600 dark:text-slate-400" />
            <span>SEC-63/65B BSA</span>
          </div>
        </div>
      </div>

      <EvidenceVault />
    </div>
  );
}
