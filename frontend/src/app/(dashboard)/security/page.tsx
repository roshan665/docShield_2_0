"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Activity,
  CheckCircle2,
  RefreshCw,
  Clock,
  UserCheck,
  Lock,
  Flame,
  Search,
  Check,
  Radio,
  FileWarning,
  LogIn,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { useAuth } from "@/lib/auth-context";
import {
  SecurityEvent,
  SecurityMetrics,
  SecurityEventSeverity,
  SecurityEventCategory,
  TamperSimulationResponse,
} from "@/types";
import {
  getSecurityMetrics,
  listSecurityEvents,
  resolveSecurityEvent,
  simulateTamper,
} from "@/lib/api";

export default function SecurityCenterPage() {
  const { user } = useAuth();

  // Metrics & Event List state
  const [metrics, setMetrics] = useState<SecurityMetrics | null>(null);
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Event Resolution Modal
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [resolving, setResolving] = useState(false);

  // Tamper Simulation Console (SIH Jury Live Demonstration)
  const [tamperVersionId, setTamperVersionId] = useState("");
  const [tamperReason, setTamperReason] = useState("SIH Jury live tamper simulation and automated intrusion detection test");
  const [simulating, setSimulating] = useState(false);
  const [tamperResult, setTamperResult] = useState<TamperSimulationResponse | null>(null);

  const fetchSecurityData = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [m, eRes] = await Promise.all([
        getSecurityMetrics(),
        listSecurityEvents({
          severity: severityFilter !== "all" ? severityFilter : undefined,
          category: categoryFilter !== "all" ? categoryFilter : undefined,
          resolved: statusFilter === "resolved" ? true : statusFilter === "unresolved" ? false : undefined,
          page: 1,
          size: 50,
        }),
      ]);
      setMetrics(m);
      setEvents(eRes.items || []);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load security monitoring data.");
    } finally {
      setLoading(false);
    }
  }, [severityFilter, categoryFilter, statusFilter]);

  useEffect(() => {
    fetchSecurityData();
  }, [fetchSecurityData]);

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent) return;
    setResolving(true);
    setErrorMsg(null);
    try {
      await resolveSecurityEvent(selectedEvent.id, resolutionNotes);
      setSuccessMsg(`Security event ${selectedEvent.id.slice(0, 8)} marked as RESOLVED.`);
      setSelectedEvent(null);
      setResolutionNotes("");
      await fetchSecurityData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to resolve security incident.");
    } finally {
      setResolving(false);
    }
  };

  const handleSimulateTamper = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tamperVersionId.trim()) return;
    setSimulating(true);
    setTamperResult(null);
    setErrorMsg(null);
    try {
      const res = await simulateTamper({
        document_version_id: tamperVersionId.trim(),
        reason: tamperReason,
      });
      setTamperResult(res);
      setSuccessMsg("Tamper simulation successfully triggered. Real-time CRITICAL security alert logged.");
      await fetchSecurityData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute tamper simulation.");
    } finally {
      setSimulating(false);
    }
  };

  const getSeverityBadge = (sev: SecurityEventSeverity) => {
    switch (sev) {
      case "CRITICAL":
        return <Badge className="bg-red-600 text-white font-bold animate-pulse text-[10px]">CRITICAL</Badge>;
      case "HIGH":
        return <Badge className="bg-orange-500 text-white font-semibold text-[10px]">HIGH</Badge>;
      case "MEDIUM":
        return <Badge className="bg-amber-500 text-white text-[10px]">MEDIUM</Badge>;
      case "LOW":
        return <Badge className="bg-slate-500 text-white text-[10px]">LOW</Badge>;
      default:
        return <Badge variant="outline">{sev}</Badge>;
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-6 bg-slate-900 text-white rounded-xl shadow-lg border border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">
                DocShield Security & Incident Center
                Security Operations Center
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-Time Intrusion Detection &bull; SHA-256 Tamper Alarms &bull; Zero-Trust Audit Stream
                Real-time intrusion detection, tamper monitoring, and audit log analysis.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-300 font-mono">IDS Engine: ACTIVE</span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={fetchSecurityData}
            disabled={loading}
            className="border-slate-700 bg-slate-800 text-white hover:bg-slate-700"
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh Feed
          </Button>
        </div>
      </div>

      {/* Status Notifications */}
      {errorMsg && (
        <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg text-red-800 dark:text-red-200 text-sm">
          <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-600 dark:text-red-400" />
          <div className="flex-1">{errorMsg}</div>
          {errorMsg.toLowerCase().includes("session required") && (
            <Link href="/login">
              <Button size="sm" variant="outline" className="h-7 text-xs bg-white dark:bg-slate-900 border-red-300 text-red-800 dark:text-red-200 gap-1">
                <LogIn className="h-3 w-3" /> Sign In
              </Button>
            </Link>
          )}
          <button onClick={() => setErrorMsg(null)} className="text-xs underline hover:no-underline">Dismiss</button>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center gap-3 p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 rounded-lg text-emerald-800 dark:text-emerald-200 text-sm">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-emerald-600 dark:text-emerald-400" />
          <div className="flex-1">{successMsg}</div>
          <button onClick={() => setSuccessMsg(null)} className="text-xs underline hover:no-underline">Dismiss</button>
        </div>
      )}

      {/* KPI Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="border-slate-200 dark:border-slate-800">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Events</span>
              <Activity className="h-4 w-4 text-slate-400" />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">
              {metrics?.total_events ?? 0}
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Recorded audit incidents</p>
          </CardContent>
        </Card>

        <Card className={`border ${metrics?.critical_events ? "border-red-500/50 bg-red-500/5" : "border-slate-200 dark:border-slate-800"}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wider">Critical</span>
              <AlertOctagon className="h-4 w-4 text-red-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-red-600 dark:text-red-400">
              {metrics?.critical_events ?? 0}
            </div>
            <p className="text-[10px] text-slate-400 mt-1">High-priority alerts</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-orange-500 uppercase tracking-wider">High</span>
              <AlertTriangle className="h-4 w-4 text-orange-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-orange-600 dark:text-orange-400">
              {metrics?.high_events ?? 0}
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Auth & Access violations</p>
          </CardContent>
        </Card>

        <Card className={`border ${metrics?.integrity_compromises ? "border-red-500/80 bg-red-500/10" : "border-slate-200 dark:border-slate-800"}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-rose-600 uppercase tracking-wider">Compromises</span>
              <Flame className="h-4 w-4 text-rose-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-rose-600 dark:text-rose-400">
              {metrics?.integrity_compromises ?? 0}
            </div>
            <p className="text-[10px] text-slate-400 mt-1">SHA-256 hash mismatches</p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-amber-500 uppercase tracking-wider">Unresolved</span>
              <Clock className="h-4 w-4 text-amber-500" />
            </div>
            <div className="mt-2 text-2xl font-bold text-amber-600 dark:text-amber-400">
              {metrics?.unresolved_count ?? 0}
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Action required</p>
          </CardContent>
        </Card>
      </div>

      {/* SIH Jury Live Tamper Simulation Console */}
      <Card className="border-indigo-200 dark:border-indigo-900/60 bg-gradient-to-r from-indigo-950/20 via-purple-950/10 to-slate-900/20">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="h-5 w-5 text-indigo-500 animate-pulse" />
              <CardTitle className="text-sm font-bold text-indigo-900 dark:text-indigo-300">
                SIH Jury Live Demonstration: Forensic Tamper Simulation Console
              </CardTitle>
            </div>
            <Badge variant="outline" className="text-[10px] text-indigo-400 border-indigo-500/40">
              Sandbox-Safe Demo Mode
            </Badge>
          </div>
          <CardDescription className="text-xs">
            Demonstrates DOCSHIELD’s proactive tamper-detection: inject a simulated SHA-256 mutation on any document version to observe immediate download denial, state transition to <code className="text-red-500 font-bold">COMPROMISED</code>, and real-time security alert emission.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <form onSubmit={handleSimulateTamper} className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="Paste Document Version UUID (e.g., from Documents tab)"
              value={tamperVersionId}
              onChange={(e) => setTamperVersionId(e.target.value)}
              className="flex-1 text-xs rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 font-mono text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              required
            />
            <Button
              type="submit"
              disabled={simulating || !tamperVersionId.trim()}
              className="bg-red-600 hover:bg-red-500 text-white text-xs whitespace-nowrap"
            >
              {simulating ? <LoadingSpinner size="sm" className="mr-1.5" /> : <FileWarning className="h-4 w-4 mr-1.5" />}
              Inject Tamper Mutation
            </Button>
          </form>

          {tamperResult && (
            <div className="p-4 rounded-lg bg-red-950/30 border border-red-800/60 text-xs space-y-2">
              <div className="flex items-center gap-2 font-bold text-red-400">
                <AlertOctagon className="h-4 w-4" />
                Tamper Mutation Injected Successfully!
              </div>
              <p className="text-slate-300">{tamperResult.message}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-[11px] pt-1">
                <div className="p-2 bg-slate-900 rounded border border-slate-800">
                  <span className="text-slate-400 text-[10px] block">Recorded Baseline Hash:</span>
                  <span className="text-emerald-400 truncate block">{tamperResult.original_hash}</span>
                </div>
                <div className="p-2 bg-slate-900 rounded border border-slate-800">
                  <span className="text-slate-400 text-[10px] block">Corrupted Mutated Hash:</span>
                  <span className="text-red-400 truncate block">{tamperResult.corrupted_hash}</span>
                </div>
              </div>
              <p className="text-[11px] text-amber-300">
                &rarr; Subsequent downloads of this document will be hard-refused with HTTP 409 and logged to the incident feed below.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Filter Controls & Events Table */}
      <Card className="border-slate-200 dark:border-slate-800">
        <CardHeader className="pb-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <CardTitle className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Activity className="h-4 w-4 text-slate-500" />
                Security Incident & Audit Ledger
              </CardTitle>
              <CardDescription className="text-xs">
                Filterable real-time stream of security events, authorization violations, and cryptographic anomalies.
              </CardDescription>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 text-slate-700 dark:text-slate-300"
              >
                <option value="all">All Severities</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>

              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 text-slate-700 dark:text-slate-300"
              >
                <option value="all">All Categories</option>
                <option value="INTEGRITY">INTEGRITY</option>
                <option value="AUTHORIZATION">AUTHORIZATION</option>
                <option value="AUTHENTICATION">AUTHENTICATION</option>
                <option value="SYSTEM">SYSTEM</option>
                <option value="RATE_LIMIT">RATE_LIMIT</option>
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 text-slate-700 dark:text-slate-300"
              >
                <option value="all">All Status</option>
                <option value="unresolved">Unresolved</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {loading && events.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 space-y-3">
              <LoadingSpinner size="lg" />
              <p className="text-xs text-slate-500">Loading security incidents...</p>
            </div>
          ) : events.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="Zero Incidents Matching Criteria"
              description="No security events or anomalies match the selected filters. System integrity remains verified."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-semibold border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="p-3">Severity</th>
                    <th className="p-3">Event Type</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Timestamp (UTC)</th>
                    <th className="p-3">Details / Context</th>
                    <th className="p-3">Status</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {events.map((ev) => (
                    <tr key={ev.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                      <td className="p-3">{getSeverityBadge(ev.severity)}</td>
                      <td className="p-3 font-mono font-medium text-slate-900 dark:text-slate-100">
                        {ev.event_type}
                      </td>
                      <td className="p-3">
                        <Badge variant="outline" className="text-[10px]">
                          {ev.category}
                        </Badge>
                      </td>
                      <td className="p-3 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                        {new Date(ev.timestamp).toLocaleString()}
                      </td>
                      <td className="p-3 max-w-xs truncate text-slate-600 dark:text-slate-400">
                        {ev.details ? JSON.stringify(ev.details) : "—"}
                      </td>
                      <td className="p-3">
                        {ev.resolved ? (
                          <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300 text-[10px]">
                            Resolved
                          </Badge>
                        ) : (
                          <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-300 text-[10px]">
                            Open Incident
                          </Badge>
                        )}
                      </td>
                      <td className="p-3 text-right">
                        {!ev.resolved ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedEvent(ev);
                              setResolutionNotes("");
                            }}
                            className="text-xs h-7 px-2"
                          >
                            Resolve
                          </Button>
                        ) : (
                          <span className="text-[10px] text-slate-400 italic">
                            Closed
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal: Resolve Incident */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Resolve Security Incident
                </h3>
                <p className="text-xs font-mono text-slate-500 mt-0.5">
                  ID: {selectedEvent.id}
                </p>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                disabled={resolving}
                className="text-slate-400 hover:text-slate-600 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-xs space-y-1">
              <div><span className="font-semibold text-slate-500">Event:</span> {selectedEvent.event_type}</div>
              <div><span className="font-semibold text-slate-500">Severity:</span> {selectedEvent.severity}</div>
              <div><span className="font-semibold text-slate-500">Category:</span> {selectedEvent.category}</div>
            </div>

            <form onSubmit={handleResolve} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Investigation & Resolution Notes
                </label>
                <textarea
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  rows={3}
                  className="w-full text-xs rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Detail forensic findings, root-cause assessment, and corrective actions taken..."
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-200 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedEvent(null)}
                  disabled={resolving}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={resolving || !resolutionNotes.trim()}
                  className="bg-blue-600 hover:bg-blue-500 text-white"
                >
                  {resolving ? <LoadingSpinner size="sm" className="mr-1.5" /> : <Check className="h-4 w-4 mr-1.5" />}
                  Confirm Resolution
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

