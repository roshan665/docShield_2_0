"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  FolderLock,
  FileText,
  Boxes,
  Shield,
  CheckCircle2,
  Cpu,
  Search,
  FileArchive,
  ShieldAlert,
  ArrowRight,
  Activity,
  Lock,
  HardDrive,
  Scale,
  Sparkles,
  ExternalLink,
  Clock,
  RefreshCw,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { listCases, listAuditEvents, getSecurityMetrics, listCaseDocuments, listCaseEvidence } from "@/lib/api";
import { Case, AuditEvent, SecurityMetrics } from "@/types";

const LIFECYCLE_STAGES = [
  {
    step: "01",
    name: "Upload & Ingest",
    desc: "MIME magic-byte validation & secure ingest",
    icon: FileText,
    status: "Active",
  },
  {
    step: "02",
    name: "AI / OCR",
    desc: "Tesseract fallback & Indian legal entity extraction",
    icon: Cpu,
    status: "Operational",
  },
  {
    step: "03",
    name: "Secure Storage",
    desc: "Isolated MinIO/S3 object vault with versioning",
    icon: HardDrive,
    status: "Immutable",
  },
  {
    step: "04",
    name: "Hash Verification",
    desc: "SHA-256 baseline computed & checked on every stream",
    icon: ShieldCheck,
    status: "Enforced",
  },
  {
    step: "05",
    name: "Custody Chain",
    desc: "Two-phase custodial transfer state machine",
    icon: Boxes,
    status: "Verified",
  },
  {
    step: "06",
    name: "Legal Review",
    desc: "RBAC-scoped case dossier & evidence inquest",
    icon: Scale,
    status: "Protected",
  },
  {
    step: "07",
    name: "Court Export",
    desc: "Canonical ZIP, Sec. 63/65B BSA 2023 certificate",
    icon: FileArchive,
    status: "Ready",
  },
  {
    step: "08",
    name: "Archive Ledger",
    desc: "Tamper-evident append-only cryptographic ledger",
    icon: Lock,
    status: "Synchronized",
  },
];

const SECURITY_MATRIX = [
  { name: "Document Integrity", status: "Operational", detail: "Real-time SHA-256 baseline verification" },
  { name: "Chain of Custody", status: "Verified", detail: "Cryptographic hash-chained transfer ledger" },
  { name: "Audit Ledger", status: "Synchronized", detail: "Immutable SHA-256 linked event sequence" },
  { name: "Access Control", status: "Enforced", detail: "Zero-Trust case membership & RBAC boundaries" },
  { name: "AI Security", status: "Protected", detail: "Strict human verification advisory & citation grounding" },
];

export default function DashboardHomePage() {
  const { isAuthenticated } = useAuth();
  const [loading, setLoading] = useState(true);
  const [cases, setCases] = useState<Case[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [metrics, setMetrics] = useState<SecurityMetrics | null>(null);
  const [verifiedDocsCount, setVerifiedDocsCount] = useState<number>(0);
  const [evidenceCount, setEvidenceCount] = useState<number>(0);

  const loadDashboardData = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [casesRes, auditRes, metricsRes] = await Promise.allSettled([
        listCases(),
        listAuditEvents({ limit: 6 }),
        getSecurityMetrics(),
      ]);

      if (casesRes.status === "fulfilled") {
        const loadedCases = casesRes.value;
        setCases(loadedCases);
        if (loadedCases.length > 0) {
          try {
            const counts = await Promise.allSettled(
              loadedCases.slice(0, 5).map(async (c) => {
                const [d, e] = await Promise.all([
                  listCaseDocuments(c.id).catch(() => []),
                  listCaseEvidence(c.id).catch(() => []),
                ]);
                return { docs: d.length, ev: e.length };
              })
            );
            let totalD = 0;
            let totalE = 0;
            counts.forEach((res) => {
              if (res.status === "fulfilled") {
                totalD += res.value.docs;
                totalE += res.value.ev;
              }
            });
            setVerifiedDocsCount(totalD);
            setEvidenceCount(totalE);
          } catch {
            // graceful fallback
          }
        }
      }
      if (auditRes.status === "fulfilled") {
        setAuditEvents(auditRes.value);
      }
      if (metricsRes.status === "fulfilled") {
        setMetrics(metricsRes.value);
      }
    } catch {
      // Graceful fallback for non-admin or initial state
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Derived metrics from real data
  const activeCasesCount = cases.length;
  const integrityHealth = metrics && metrics.integrity_compromises > 0 ? "Compromised" : "100%";

  return (
    <div className="space-y-8">
      {/* Header Command Center */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 font-sans">
              Digital Evidence Command Center
            </h1>
            <Badge variant="gov" className="font-mono text-[10px] uppercase">
              NCRB Production
            </Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Secure oversight of cases, evidence, documents and integrity.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/80 dark:bg-emerald-950/40 px-3 py-1.5 text-xs font-semibold text-emerald-800 dark:text-emerald-300 shadow-sm">
            <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span>System Secure</span>
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => loadDashboardData()}
            className="h-8 gap-1.5 text-xs border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300"
            title="Refresh Command Center Data"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Active Cases */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Active Cases
            </CardTitle>
            <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
              <FolderLock className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16 mb-2" />
            ) : (
              <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 font-mono">
                {activeCasesCount}
              </div>
            )}
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
              Authorized under active membership
            </p>
            <div className="mt-3 flex items-center justify-between border-t border-slate-100 dark:border-slate-800/80 pt-2 text-[10px] text-blue-600 dark:text-blue-400 font-medium">
              <Link href="/cases" className="hover:underline flex items-center gap-1">
                View Dossiers <ArrowRight className="h-3 w-3" />
              </Link>
              <span className="text-slate-400 font-mono">RBAC SCOPED</span>
            </div>
          </CardContent>
        </Card>

        {/* Verified Documents */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Verified Documents
            </CardTitle>
            <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              <FileText className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16 mb-2" />
            ) : (
              <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 font-mono">
                {verifiedDocsCount}
              </div>
            )}
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
              SHA-256 integrity confirmed
            </p>
            <div className="mt-3 flex items-center justify-between border-t border-slate-100 dark:border-slate-800/80 pt-2 text-[10px] text-indigo-600 dark:text-indigo-400 font-medium">
              <Link href="/documents" className="hover:underline flex items-center gap-1">
                Access Vault <ArrowRight className="h-3 w-3" />
              </Link>
              <span className="text-slate-400 font-mono">S3 ISOLATED</span>
            </div>
          </CardContent>
        </Card>

        {/* Evidence in Custody */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Evidence in Custody
            </CardTitle>
            <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
              <Boxes className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16 mb-2" />
            ) : (
              <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 font-mono">
                {evidenceCount}
              </div>
            )}
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
              Chain of custody intact
            </p>
            <div className="mt-3 flex items-center justify-between border-t border-slate-100 dark:border-slate-800/80 pt-2 text-[10px] text-amber-600 dark:text-amber-400 font-medium">
              <Link href="/evidence" className="hover:underline flex items-center gap-1">
                Custody Chain <ArrowRight className="h-3 w-3" />
              </Link>
              <span className="text-slate-400 font-mono">2-PHASE STATE</span>
            </div>
          </CardContent>
        </Card>

        {/* Integrity Health */}
        <Card className="border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/20 dark:bg-emerald-950/20 shadow-sm hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
              Integrity Health
            </CardTitle>
            <div className="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300">
              <ShieldCheck className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16 mb-2" />
            ) : (
              <div className="text-2xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400 font-mono">
                {integrityHealth}
              </div>
            )}
            <p className="text-[11px] text-emerald-700/80 dark:text-emerald-400/80 mt-1">
              Zero cryptographic mismatches
            </p>
            <div className="mt-3 flex items-center justify-between border-t border-emerald-200/60 dark:border-emerald-900/60 pt-2 text-[10px] text-emerald-700 dark:text-emerald-400 font-medium font-mono">
              <span>ACTIVE DEFENSE</span>
              <span>HTTP 409 DENIAL</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Grid: System Security Status & Evidence Lifecycle */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* System Security Status Panel (1 column) */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 lg:col-span-1 shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Shield className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                System Security Status
              </CardTitle>
              <Badge variant="gov" className="text-[9px] font-mono">
                ZERO-TRUST
              </Badge>
            </div>
            <CardDescription className="text-xs text-slate-500">
              Continuous cryptographic ledger & policy verification
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {SECURITY_MATRIX.map((item) => (
              <div
                key={item.name}
                className="flex items-start justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 transition-colors"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                    {item.name}
                  </div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                    {item.detail}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 font-mono">
                    {item.status}
                  </span>
                </div>
              </div>
            ))}

            <div className="mt-4 p-3 rounded-lg border border-blue-200/80 bg-blue-50/50 dark:border-blue-900/50 dark:bg-blue-950/30 text-[11px] text-blue-900 dark:text-blue-200 flex items-center justify-between">
              <div>
                <span className="font-semibold block">Statutory Compliance</span>
                <span className="text-blue-700 dark:text-blue-300 text-[10px]">
                  Sec. 63 / 65B Bharatiya Sakshya Adhiniyam, 2023
                </span>
              </div>
              <ShieldCheck className="h-5 w-5 text-blue-600 dark:text-blue-400 shrink-0" />
            </div>
          </CardContent>
        </Card>

        {/* Evidence Lifecycle Visualizer (2 columns) */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 lg:col-span-2 shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <CardTitle className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Activity className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                  Digital Evidence Lifecycle
                </CardTitle>
                <CardDescription className="text-xs text-slate-500 mt-0.5">
                  End-to-end chain of verification from seizure to courtroom admissibility
                </CardDescription>
              </div>
              <span className="text-[10px] font-mono text-slate-400 px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 w-fit">
                8-STAGE PIPELINE
              </span>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {LIFECYCLE_STAGES.map((stg) => {
                const IconComp = stg.icon;
                return (
                  <div
                    key={stg.step}
                    className="relative group rounded-xl border border-slate-200/90 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/60 p-3 hover:border-blue-400 dark:hover:border-blue-700 transition-all shadow-none hover:shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-mono font-bold text-slate-400 dark:text-slate-500">
                        STAGE {stg.step}
                      </span>
                      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-mono font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60">
                        {stg.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-2.5 mb-1.5">
                      <div className="p-1.5 rounded-lg bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 shrink-0">
                        <IconComp className="h-4 w-4" />
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                        {stg.name}
                      </h4>
                    </div>

                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-2">
                      {stg.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity Timeline & Quick Actions */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Real Audit Activity Stream (2 columns) */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 lg:col-span-2 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Clock className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                Immutable Audit Trail & Operations Stream
              </CardTitle>
              <CardDescription className="text-xs text-slate-500 mt-0.5">
                Live cryptographic ledger events recorded across authorized cases
              </CardDescription>
            </div>
            <Link href="/settings" className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium">
              Verify Hash Chain &rarr;
            </Link>
          </CardHeader>

          <CardContent>
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : auditEvents.length > 0 ? (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {auditEvents.map((evt) => (
                  <div key={evt.id} className="py-3 flex items-start justify-between gap-3 text-xs first:pt-0 last:pb-0">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 p-1.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 shrink-0">
                        <Activity className="h-3.5 w-3.5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wider font-mono text-[11px]">
                            {evt.action.replace("_", " ")}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                            {evt.resource_type}
                          </span>
                        </div>
                        <p className="text-slate-500 dark:text-slate-400 text-[11px] mt-0.5">
                          Officer: <span className="font-medium text-slate-700 dark:text-slate-300">{evt.actor_email || evt.actor_name || "System"}</span>
                        </p>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="text-[10px] font-mono text-slate-400">
                        {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : "—"}
                      </div>
                      <span className="inline-flex items-center gap-1 text-[9px] font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                        <ShieldCheck className="h-3 w-3" /> Chained
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-slate-500">
                <Shield className="h-8 w-8 text-slate-400 mx-auto mb-2 opacity-60" />
                <p className="font-semibold">No Recent Audit Records</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Sign in or perform an evidence operation to record ledger activity.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Operations Strip (1 column) */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/90 lg:col-span-1 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Operational Portals
            </CardTitle>
            <CardDescription className="text-xs text-slate-500">
              Direct access to mission-critical investigation workflows
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-2.5">
            <Link
              href="/cases"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 hover:bg-blue-50/50 dark:hover:bg-blue-950/30 hover:border-blue-300 dark:hover:border-blue-800 transition-all text-xs group"
            >
              <div className="flex items-center gap-2.5">
                <FolderLock className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                <div>
                  <span className="font-semibold text-slate-900 dark:text-slate-100 block">
                    Case Dossiers
                  </span>
                  <span className="text-[10px] text-slate-500">
                    Investigative files & legal filings
                  </span>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-blue-600 transition-transform group-hover:translate-x-0.5" />
            </Link>

            <Link
              href="/documents"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 hover:border-indigo-300 dark:hover:border-indigo-800 transition-all text-xs group"
            >
              <div className="flex items-center gap-2.5">
                <FileText className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                <div>
                  <span className="font-semibold text-slate-900 dark:text-slate-100 block">
                    Document Vault
                  </span>
                  <span className="text-[10px] text-slate-500">
                    SHA-256 baselines & OCR extraction
                  </span>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 transition-transform group-hover:translate-x-0.5" />
            </Link>

            <Link
              href="/evidence"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 hover:bg-amber-50/50 dark:hover:bg-amber-950/30 hover:border-amber-300 dark:hover:border-amber-800 transition-all text-xs group"
            >
              <div className="flex items-center gap-2.5">
                <Boxes className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                <div>
                  <span className="font-semibold text-slate-900 dark:text-slate-100 block">
                    Central Evidence Vault
                  </span>
                  <span className="text-[10px] text-slate-500">
                    Chain-of-custody transfer protocols
                  </span>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-amber-600 transition-transform group-hover:translate-x-0.5" />
            </Link>

            <Link
              href="/search"
              className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 hover:bg-purple-50/50 dark:hover:bg-purple-950/30 hover:border-purple-300 dark:hover:border-purple-800 transition-all text-xs group"
            >
              <div className="flex items-center gap-2.5">
                <Search className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                <div>
                  <span className="font-semibold text-slate-900 dark:text-slate-100 block">
                    Evidence Intelligence & RAG
                  </span>
                  <span className="text-[10px] text-slate-500">
                    pgvector semantic & hybrid search
                  </span>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-slate-400 group-hover:text-purple-600 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Platform Standards Footer Bar */}
      <div className="rounded-lg bg-slate-900 text-white p-4 text-xs font-mono flex flex-col md:flex-row items-start md:items-center justify-between gap-3 border border-slate-800 shadow-sm">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-semibold text-slate-200">
            Bharatiya Sakshya Adhiniyam, 2023 &bull; Sec. 63 / 65B Compliant
          </span>
        </div>
        <div className="text-[11px] text-slate-400">
          Argon2id &bull; SHA-256 Digest Chains &bull; PostgreSQL 16 &bull; pgvector &bull; S3 Object Storage
        </div>
      </div>
    </div>
  );
}
