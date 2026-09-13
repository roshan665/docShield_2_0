"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  Boxes,
  ShieldCheck,
  ShieldAlert,
  ArrowRightLeft,
  CheckCircle2,
  AlertCircle,
  Search,
  RefreshCw,
  PlusCircle,
  FileText,
  HardDrive,
  Camera,
  Video,
  Mic,
  Cpu,
  Package,
  History,
  Copy,
  Check,
  Ban,
  UserCheck,
  Eye,
  Link2,
  Lock,
  ExternalLink,
  Shield,
  FileCheck,
  X,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { useAuth } from "@/lib/auth-context";
import {
  CaseMember,
  CustodyChainVerificationResult,
  Document,
  Evidence,
  EvidenceCustodyEvent,
  EvidenceRegisterRequest,
  EvidenceSensitivity,
  EvidenceStatus,
  EvidenceType,
} from "@/types";
import {
  acknowledgeCustodyTransfer,
  cancelCustodyTransfer,
  getEvidenceById,
  initiateCustodyTransfer,
  listAllAccessibleEvidence,
  listCaseDocuments,
  listCaseEvidence,
  listCaseMembers,
  listEvidenceCustodyHistory,
  registerEvidence,
  transitionEvidenceStatus,
  verifyEvidenceCustodyChain,
  verifyEvidenceDigitalIntegrity,
} from "@/lib/api";

interface EvidenceVaultProps {
  caseId?: string;
  caseTitle?: string;
  canManage?: boolean;
  onEvidenceCountChange?: (count: number) => void;
}

const EVIDENCE_TYPE_ICONS: Record<EvidenceType, typeof Boxes> = {
  digital_document: FileText,
  device: HardDrive,
  image: Camera,
  video: Video,
  audio: Mic,
  forensic_artifact: Cpu,
  physical_evidence: Package,
  other: Boxes,
};

const EVIDENCE_TYPE_LABELS: Record<EvidenceType, string> = {
  digital_document: "Digital Document",
  device: "Seized Hardware",
  image: "Forensic Image",
  video: "CCTV / Video",
  audio: "Audio Intercept",
  forensic_artifact: "Forensic Artifact",
  physical_evidence: "Physical Seizure",
  other: "Evidence Item",
};

const STATUS_CONFIG: Record<EvidenceStatus, { label: string; color: string; dotColor: string }> = {
  registered: {
    label: "Registered",
    color: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700",
    dotColor: "bg-slate-400",
  },
  in_custody: {
    label: "In Custody",
    color: "bg-blue-50 text-blue-800 dark:bg-blue-950/80 dark:text-blue-200 border-blue-300 dark:border-blue-800",
    dotColor: "bg-blue-500",
  },
  in_analysis: {
    label: "Forensic Analysis",
    color: "bg-purple-50 text-purple-800 dark:bg-purple-950/80 dark:text-purple-200 border-purple-300 dark:border-purple-800",
    dotColor: "bg-purple-500",
  },
  analyzed: {
    label: "Analyzed",
    color: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-200 border-emerald-300 dark:border-emerald-800",
    dotColor: "bg-emerald-500",
  },
  submitted_to_court: {
    label: "Court Exhibit",
    color: "bg-amber-50 text-amber-800 dark:bg-amber-950/80 dark:text-amber-200 border-amber-300 dark:border-amber-800",
    dotColor: "bg-amber-500",
  },
  archived: {
    label: "Archived",
    color: "bg-neutral-100 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-300 border-neutral-300 dark:border-neutral-700",
    dotColor: "bg-neutral-400",
  },
};

const SENSITIVITY_COLORS: Record<EvidenceSensitivity, string> = {
  standard: "bg-slate-50 text-slate-600 border-slate-200 dark:bg-slate-800/80 dark:text-slate-400 dark:border-slate-700",
  sensitive: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/60 dark:text-sky-300 dark:border-sky-800",
  highly_sensitive: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800",
  confidential: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800",
  secret: "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/60 dark:text-orange-300 dark:border-orange-800",
  classified: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800 font-bold",
};

const VALID_TRANSITIONS: Record<EvidenceStatus, EvidenceStatus[]> = {
  registered: ["in_custody"],
  in_custody: ["in_analysis", "submitted_to_court"],
  in_analysis: ["analyzed", "in_custody"],
  analyzed: ["in_custody", "submitted_to_court"],
  submitted_to_court: ["archived"],
  archived: [],
};

interface HashDetailModalData {
  number: string;
  title: string;
  hash: string;
  status: string;
  date?: string;
  collectionLocation?: string | null;
}

export function EvidenceVault({
  caseId,
  canManage = true,
  onEvidenceCountChange,
}: EvidenceVaultProps) {
  const { user: currentUser } = useAuth();

  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [caseMembers, setCaseMembers] = useState<CaseMember[]>([]);
  const [caseDocuments, setCaseDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sensitivityFilter, setSensitivityFilter] = useState<string>("all");
  const [filterCompromisedOnly, setFilterCompromisedOnly] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modals state
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [activeEvidenceForTransfer, setActiveEvidenceForTransfer] = useState<Evidence | null>(null);
  const [activeEvidenceForAck, setActiveEvidenceForAck] = useState<Evidence | null>(null);
  const [activeEvidenceForStatus, setActiveEvidenceForStatus] = useState<Evidence | null>(null);
  const [activeEvidenceForCustody, setActiveEvidenceForCustody] = useState<Evidence | null>(null);
  const [viewingHashItem, setViewingHashItem] = useState<HashDetailModalData | null>(null);
  const [custodyEvents, setCustodyEvents] = useState<EvidenceCustodyEvent[]>([]);
  const [loadingCustody, setLoadingCustody] = useState(false);

  // Chain & Integrity Verification State
  const [verifyingChain, setVerifyingChain] = useState<string | null>(null);
  const [chainVerifyResult, setChainVerifyResult] = useState<CustodyChainVerificationResult | null>(null);
  const [verifyingIntegrity, setVerifyingIntegrity] = useState<string | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Form states
  const [registerForm, setRegisterForm] = useState<EvidenceRegisterRequest>({
    title: "",
    description: "",
    evidence_type: "device",
    sensitivity_level: "standard",
    collection_location: "",
    source: "",
    notes: "",
  });
  const [registering, setRegistering] = useState(false);

  const [transferRecipientId, setTransferRecipientId] = useState("");
  const [transferReason, setTransferReason] = useState("");
  const [transferLocation, setTransferLocation] = useState("");
  const [transferring, setTransferring] = useState(false);

  const [ackNotes, setAckNotes] = useState("");
  const [ackLocation, setAckLocation] = useState("");
  const [acknowledging, setAcknowledging] = useState(false);

  const [targetStatus, setTargetStatus] = useState<EvidenceStatus>("in_analysis");
  const [statusReason, setStatusReason] = useState("");
  const [statusLocation, setStatusLocation] = useState("");
  const [transitioning, setTransitioning] = useState(false);

  // Copy helper
  const handleCopyHash = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Human-readable error transformer
  const sanitizeErrorMessage = (err: unknown): string => {
    if (err instanceof Error) {
      const msg = err.message.toLowerCase();
      if (msg.includes("401") || msg.includes("unauthorized") || msg.includes("session required") || msg.includes("token")) {
        return "Session Required: Please sign in to access protected evidence.";
      }
      if (msg.includes("409") || msg.includes("hash mismatch") || msg.includes("compromised") || msg.includes("integrity")) {
        return "Integrity Verification Failed: This artifact does not match its authoritative SHA-256 record. Access has been blocked.";
      }
      if (msg.includes("403") || msg.includes("forbidden") || msg.includes("not a member")) {
        return "Access Denied: You do not have permission to view or manage this evidence item.";
      }
      return err.message;
    }
    return "An unexpected error occurred while processing the request.";
  };

  // Fetch Evidence List
  const fetchEvidence = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      let items: Evidence[] = [];
      if (caseId) {
        items = await listCaseEvidence(caseId, {
          evidence_type: typeFilter !== "all" ? typeFilter : undefined,
          status: statusFilter !== "all" ? statusFilter : undefined,
          sensitivity_level: sensitivityFilter !== "all" ? sensitivityFilter : undefined,
          search: searchQuery.trim() || undefined,
        });
      } else {
        items = await listAllAccessibleEvidence({
          evidence_type: typeFilter !== "all" ? typeFilter : undefined,
          status: statusFilter !== "all" ? statusFilter : undefined,
          sensitivity_level: sensitivityFilter !== "all" ? sensitivityFilter : undefined,
          search: searchQuery.trim() || undefined,
        });
      }
      setEvidenceList(items);
      if (onEvidenceCountChange) {
        onEvidenceCountChange(items.length);
      }
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [caseId, typeFilter, statusFilter, sensitivityFilter, searchQuery, onEvidenceCountChange]);

  // Fetch contextual case members and documents if caseId is provided
  useEffect(() => {
    if (caseId) {
      listCaseMembers(caseId)
        .then((members) => setCaseMembers(members.filter((m) => m.is_active)))
        .catch(() => {});

      listCaseDocuments(caseId)
        .then((docs) => setCaseDocuments(docs))
        .catch(() => {});
    }
  }, [caseId]);

  useEffect(() => {
    fetchEvidence();
  }, [fetchEvidence]);

  // Handler: Register Evidence
  const handleRegisterEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId) return;
    setRegistering(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const created = await registerEvidence(caseId, registerForm);
      setSuccessMsg(`Evidence ${created.evidence_number} successfully registered into custody ledger.`);
      setShowRegisterModal(false);
      setRegisterForm({
        title: "",
        description: "",
        evidence_type: "device",
        sensitivity_level: "standard",
        collection_location: "",
        source: "",
        notes: "",
      });
      await fetchEvidence();
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    } finally {
      setRegistering(false);
    }
  };

  // Handler: Initiate Transfer
  const handleInitiateTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeEvidenceForTransfer || !transferRecipientId || !transferReason.trim()) return;

    setTransferring(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const updated = await initiateCustodyTransfer(activeEvidenceForTransfer.id, {
        to_user_id: transferRecipientId,
        reason: transferReason.trim(),
        location: transferLocation.trim() || undefined,
      });
      setSuccessMsg(`Custody transfer initiated for ${updated.evidence_number}. Pending recipient acknowledgment.`);
      setActiveEvidenceForTransfer(null);
      setTransferRecipientId("");
      setTransferReason("");
      setTransferLocation("");
      await fetchEvidence();
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    } finally {
      setTransferring(false);
    }
  };

  // Handler: Acknowledge Transfer
  const handleAcknowledgeTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeEvidenceForAck) return;

    setAcknowledging(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const updated = await acknowledgeCustodyTransfer(activeEvidenceForAck.id, {
        notes: ackNotes.trim() || undefined,
        location: ackLocation.trim() || undefined,
      });
      setSuccessMsg(`Custody handover acknowledged for ${updated.evidence_number}. You are now the active legal custodian.`);
      setActiveEvidenceForAck(null);
      setAckNotes("");
      setAckLocation("");
      await fetchEvidence();
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    } finally {
      setAcknowledging(false);
    }
  };

  // Handler: Cancel Transfer
  const handleCancelTransfer = async (evidence: Evidence) => {
    if (!confirm(`Cancel pending custody transfer for ${evidence.evidence_number}?`)) return;

    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await cancelCustodyTransfer(evidence.id);
      setSuccessMsg(`Custody transfer cancelled for ${evidence.evidence_number}.`);
      await fetchEvidence();
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    }
  };

  // Handler: Transition Status
  const handleStatusTransition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeEvidenceForStatus || !statusReason.trim()) return;

    setTransitioning(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const updated = await transitionEvidenceStatus(activeEvidenceForStatus.id, {
        target_status: targetStatus,
        reason: statusReason.trim(),
        location: statusLocation.trim() || undefined,
      });
      setSuccessMsg(`Evidence ${updated.evidence_number} transitioned to '${updated.status}'.`);
      setActiveEvidenceForStatus(null);
      setStatusReason("");
      setStatusLocation("");
      await fetchEvidence();
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    } finally {
      setTransitioning(false);
    }
  };

  // Handler: Open Custody History
  const handleOpenCustodyHistory = async (evidence: Evidence) => {
    setActiveEvidenceForCustody(evidence);
    setCustodyEvents([]);
    setLoadingCustody(true);
    setChainVerifyResult(null);

    try {
      const events = await listEvidenceCustodyHistory(evidence.id);
      setCustodyEvents(events);
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    } finally {
      setLoadingCustody(false);
    }
  };

  // Handler: Verify Chain Continuity
  const handleVerifyChain = async (evidenceId: string) => {
    setVerifyingChain(evidenceId);
    setChainVerifyResult(null);
    try {
      const result = await verifyEvidenceCustodyChain(evidenceId);
      setChainVerifyResult(result);
    } catch (err: unknown) {
      setErrorMsg("Custody chain verification failed.");
    } finally {
      setVerifyingChain(null);
    }
  };

  // Handler: Verify Digital Integrity
  const handleVerifyDigitalIntegrity = async (evidenceId: string) => {
    setVerifyingIntegrity(evidenceId);
    try {
      await verifyEvidenceDigitalIntegrity(evidenceId);
      // Refresh item in list
      const updatedItem = await getEvidenceById(evidenceId);
      setEvidenceList((prev) => prev.map((item) => (item.id === evidenceId ? updatedItem : item)));
      setSuccessMsg(`Authoritative SHA-256 verification confirmed for ${updatedItem.evidence_number}.`);
    } catch (err: unknown) {
      setErrorMsg(sanitizeErrorMessage(err));
    } finally {
      setVerifyingIntegrity(null);
    }
  };

  // Calculate high-level metrics
  const totalCount = evidenceList.length;
  const inCustodyCount = evidenceList.filter((e) => e.status === "in_custody").length;
  const inAnalysisCount = evidenceList.filter((e) => e.status === "in_analysis").length;
  const courtSubmissionsCount = evidenceList.filter((e) => e.status === "submitted_to_court").length;
  const pendingTransferCount = evidenceList.filter((e) => e.transfer_pending).length;
  const compromisedCount = evidenceList.filter((e) => e.integrity_status === "compromised").length;

  // Filtered evidence list considering compromised filter toggle
  const displayedEvidenceList = useMemo(() => {
    if (filterCompromisedOnly) {
      return evidenceList.filter((e) => e.integrity_status === "compromised");
    }
    return evidenceList;
  }, [evidenceList, filterCompromisedOnly]);

  // Items pending acknowledgment by CURRENT user
  const incomingPendingHandovers = evidenceList.filter(
    (e) => e.transfer_pending && e.pending_custodian_id === currentUser?.id
  );

  return (
    <div className="space-y-6">
      {/* SUCCESS / ERROR NOTIFICATIONS */}
      {successMsg && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50/90 p-4 text-emerald-900 dark:border-emerald-900/60 dark:bg-emerald-950/50 dark:text-emerald-200 shadow-sm">
          <div className="flex items-center gap-2.5 text-xs font-semibold">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-600 text-xs font-bold hover:underline">
            &times;
          </button>
        </div>
      )}

      {errorMsg && (
        <div className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50/90 p-4 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/50 dark:text-rose-200 shadow-sm">
          <div className="flex items-center gap-2.5 text-xs font-semibold">
            <AlertCircle className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {errorMsg.toLowerCase().includes("session required") && (
              <Link
                href="/login"
                className="inline-flex items-center px-3 py-1 text-xs font-medium rounded-md bg-rose-600 text-white hover:bg-rose-700 transition-colors shadow-xs"
              >
                Sign In
              </Link>
            )}
            <button onClick={() => setErrorMsg(null)} className="text-rose-600 text-xs font-bold hover:underline ml-1">
              &times;
            </button>
          </div>
        </div>
      )}

      {/* INCOMING HANDOVER ACTION BANNER */}
      {incomingPendingHandovers.length > 0 && (
        <div className="rounded-xl border border-amber-300 bg-amber-50/90 p-4 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/40">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="rounded-full bg-amber-500/20 p-2 text-amber-700 dark:text-amber-400">
                <ArrowRightLeft className="h-5 w-5 animate-pulse" />
              </div>
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900 dark:text-amber-200">
                  Custody Handover Pending Your Acknowledgment ({incomingPendingHandovers.length})
                </h4>
                <p className="text-xs text-amber-800/80 dark:text-amber-300/80 mt-0.5">
                  An evidence parcel or digital artifact has been transferred to you. In compliance with legal procedure, legal custody does not transition until you explicitly acknowledge receipt.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {incomingPendingHandovers.map((item) => (
                <Button
                  key={item.id}
                  size="sm"
                  onClick={() => setActiveEvidenceForAck(item)}
                  className="h-8 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium shadow-sm gap-1.5"
                >
                  <UserCheck className="h-3.5 w-3.5" /> Acknowledge {item.evidence_number}
                </Button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TOP METRIC KPI TILES WITH HIGH-VISIBILITY INTEGRITY TILE */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <Card className="p-3 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Total Evidence</div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">{totalCount}</span>
            <Boxes className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-1 text-[10px] text-slate-400 font-mono">ALL ARTIFACTS</div>
        </Card>

        <Card className="p-3 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">In Custody</div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-blue-600 dark:text-blue-400">{inCustodyCount}</span>
            <ShieldCheck className="h-4 w-4 text-blue-500" />
          </div>
          <div className="mt-1 text-[10px] text-blue-600/80 dark:text-blue-400/80 font-mono">ACTIVE HOLD</div>
        </Card>

        <Card className="p-3 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">In Analysis</div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-purple-600 dark:text-purple-400">{inAnalysisCount}</span>
            <Cpu className="h-4 w-4 text-purple-500" />
          </div>
          <div className="mt-1 text-[10px] text-purple-600/80 dark:text-purple-400/80 font-mono">CFSL LAB</div>
        </Card>

        <Card className="p-3 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Court Exhibits</div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">{courtSubmissionsCount}</span>
            <FileText className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-1 text-[10px] text-amber-600/80 dark:text-amber-400/80 font-mono">JUDICIAL DEPOSIT</div>
        </Card>

        <Card className="p-3 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Pending Transfers</div>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-orange-600 dark:text-orange-400">{pendingTransferCount}</span>
            <ArrowRightLeft className="h-4 w-4 text-orange-500" />
          </div>
          <div className="mt-1 text-[10px] text-orange-600/80 dark:text-orange-400/80 font-mono">2-PHASE TRANSIT</div>
        </Card>

        {/* HIGH-VISIBILITY INTEGRITY STATUS TILE */}
        <Card
          onClick={() => {
            if (compromisedCount > 0) {
              setFilterCompromisedOnly(!filterCompromisedOnly);
            }
          }}
          className={`p-3 border shadow-sm transition-all ${
            compromisedCount > 0
              ? "bg-rose-50/90 dark:bg-rose-950/40 border-rose-300 dark:border-rose-900/80 cursor-pointer hover:shadow-md"
              : "bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/50"
          }`}
          title={compromisedCount > 0 ? "Click to toggle display of compromised evidence records" : "All evidence records match authoritative SHA-256 baselines"}
        >
          <div className="flex items-center justify-between">
            <span className={`text-[10px] font-bold uppercase tracking-wider ${
              compromisedCount > 0 ? "text-rose-800 dark:text-rose-300" : "text-emerald-800 dark:text-emerald-300"
            }`}>
              Integrity Status
            </span>
            {compromisedCount > 0 ? (
              <ShieldAlert className="h-4 w-4 text-rose-600 dark:text-rose-400 animate-pulse" />
            ) : (
              <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            )}
          </div>

          <div className="mt-1.5 flex items-baseline justify-between">
            <span
              className={`text-sm sm:text-base font-bold tracking-tight font-mono ${
                compromisedCount > 0
                  ? "text-rose-700 dark:text-rose-300"
                  : "text-emerald-700 dark:text-emerald-300"
              }`}
            >
              {compromisedCount > 0
                ? `${compromisedCount} Integrity Alert${compromisedCount > 1 ? "s" : ""}`
                : "✓ 100% Verified"}
            </span>
          </div>

          <div className="mt-1 text-[10px] font-medium flex items-center justify-between">
            <span className={compromisedCount > 0 ? "text-rose-600 dark:text-rose-400 font-mono" : "text-emerald-600 dark:text-emerald-400 font-mono"}>
              {compromisedCount > 0 ? (filterCompromisedOnly ? "FILTER APPLIED" : "CLICK TO ISOLATE") : "SHA-256 INTACT"}
            </span>
            {compromisedCount > 0 && (
              <span className="text-[9px] underline text-rose-700 dark:text-rose-300">
                {filterCompromisedOnly ? "Show All" : "View"}
              </span>
            )}
          </div>
        </Card>
      </div>

      {/* FILTER CONTROLS & ACTIONS */}
      <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
        <CardContent className="p-3.5">
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between">
            <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
              <div className="relative flex-1 md:w-64">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                <Input
                  placeholder="Search by ID, title, custodian, location..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 h-9 text-xs"
                />
              </div>

              {/* Type Filter */}
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="h-9 rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-2.5 text-xs text-slate-700 dark:text-slate-300"
              >
                <option value="all">All Categories</option>
                <option value="digital_document">Digital Document</option>
                <option value="device">Seized Device</option>
                <option value="forensic_artifact">Forensic Artifact</option>
                <option value="physical_evidence">Physical Evidence</option>
                <option value="image">Image / Photo</option>
                <option value="video">Video / CCTV</option>
                <option value="audio">Audio Recording</option>
                <option value="other">Other</option>
              </select>

              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-9 rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-2.5 text-xs text-slate-700 dark:text-slate-300"
              >
                <option value="all">All Custody Statuses</option>
                <option value="in_custody">In Custody</option>
                <option value="in_analysis">Under Analysis</option>
                <option value="analyzed">Analyzed</option>
                <option value="submitted_to_court">Submitted to Court</option>
                <option value="archived">Archived</option>
                <option value="registered">Registered</option>
              </select>

              {/* Sensitivity Filter */}
              <select
                value={sensitivityFilter}
                onChange={(e) => setSensitivityFilter(e.target.value)}
                className="h-9 rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-2.5 text-xs text-slate-700 dark:text-slate-300"
              >
                <option value="all">All Classifications</option>
                <option value="standard">Standard</option>
                <option value="sensitive">Sensitive</option>
                <option value="highly_sensitive">Highly Sensitive</option>
                <option value="confidential">Confidential</option>
                <option value="secret">Secret</option>
                <option value="classified">Classified</option>
              </select>

              {filterCompromisedOnly && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setFilterCompromisedOnly(false)}
                  className="h-9 px-2.5 text-xs text-rose-600 border-rose-300 bg-rose-50 dark:bg-rose-950/60 dark:border-rose-900 hover:bg-rose-100"
                >
                  <X className="h-3.5 w-3.5 mr-1" /> Clear Alert Filter
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchEvidence()}
                disabled={loading}
                className="h-9 px-3 text-xs border-slate-200 dark:border-slate-800"
                title="Refresh evidence list"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              </Button>
            </div>

            {/* Action button */}
            {canManage && caseId && (
              <Button
                onClick={() => setShowRegisterModal(true)}
                className="h-9 bg-blue-600 hover:bg-blue-700 text-white text-xs gap-1.5 shrink-0 shadow-sm"
              >
                <PlusCircle className="h-3.5 w-3.5" /> Register Evidence
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* FILTER ACTIVE BANNER */}
      {filterCompromisedOnly && (
        <div className="flex items-center justify-between p-3 rounded-lg border border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200 text-xs">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-rose-600 shrink-0 animate-pulse" />
            <span className="font-semibold">
              Displaying compromised records only ({displayedEvidenceList.length} items flagged).
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setFilterCompromisedOnly(false)}
            className="h-7 text-xs text-rose-700 hover:text-rose-900 hover:bg-rose-100 dark:hover:bg-rose-900"
          >
            Show All Evidence
          </Button>
        </div>
      )}

      {/* EVIDENCE REGISTRY TABLE / CARDS */}
      {loading && displayedEvidenceList.length === 0 ? (
        <div className="flex h-48 items-center justify-center">
          <LoadingSpinner className="h-6 w-6 text-blue-600" />
        </div>
      ) : displayedEvidenceList.length === 0 ? (
        <EmptyState
          icon={Boxes}
          title={
            filterCompromisedOnly
              ? "No Compromised Records Found"
              : searchQuery || typeFilter !== "all" || statusFilter !== "all"
              ? "No Matching Evidence Found"
              : "No Evidence Registered"
          }
          description={
            filterCompromisedOnly
              ? "All evidence records currently pass authoritative cryptographic hash baseline audits."
              : searchQuery || typeFilter !== "all" || statusFilter !== "all"
              ? "No evidence items match your active filter criteria. Try resetting the filters or modifying your search."
              : caseId
              ? "Begin by registering seized artifacts, physical evidence, or digital records to initialize the hash-chained custody ledger."
              : "You do not currently have access to any case evidence. Join an investigation or create a case to access evidence."
          }
        />
      ) : (
        <div className="space-y-3.5">
          {displayedEvidenceList.map((item) => {
            const TypeIcon = EVIDENCE_TYPE_ICONS[item.evidence_type] || Boxes;
            const statusCfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.registered;
            const isCurrentCustodian = item.current_custodian_id === currentUser?.id;
            const isPendingCustodian = item.pending_custodian_id === currentUser?.id;
            const hasAllowedTransitions = (VALID_TRANSITIONS[item.status] || []).length > 0;

            return (
              <Card
                key={item.id}
                className={`border transition-all shadow-sm hover:shadow-md ${
                  item.integrity_status === "compromised"
                    ? "border-rose-300 dark:border-rose-900/80 bg-rose-50/20 dark:bg-rose-950/20"
                    : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                }`}
              >
                <CardContent className="p-4 sm:p-5">
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                    {/* Left: Primary Evidence Information */}
                    <div className="space-y-3 flex-1 min-w-0">
                      {/* 1. Evidence ID + Secondary Category Meta */}
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/80 px-2.5 py-0.5 rounded border border-blue-200/80 dark:border-blue-900/60 tracking-wider shadow-2xs">
                          {item.evidence_number}
                        </span>

                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                          <TypeIcon className="h-3 w-3 text-slate-500 shrink-0" />
                          <span>{EVIDENCE_TYPE_LABELS[item.evidence_type]}</span>
                        </span>

                        <span className="text-slate-300 dark:text-slate-700">&bull;</span>

                        <span
                          className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded border ${
                            SENSITIVITY_COLORS[item.sensitivity_level] || ""
                          }`}
                        >
                          {item.sensitivity_level.replace("_", " ")}
                        </span>
                      </div>

                      {/* Visually Dominant Title */}
                      <div>
                        <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight leading-snug">
                          {item.title}
                        </h3>
                        {item.description && (
                          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                            {item.description}
                          </p>
                        )}
                      </div>

                      {/* 2 & 3. Primary Security & Status Badges Hierarchy */}
                      <div className="flex flex-wrap items-center gap-2 pt-0.5">
                        {/* Primary Badge 1: Custody Status */}
                        <span
                          className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-md border ${statusCfg.color} uppercase tracking-wider font-mono shadow-2xs`}
                        >
                          <span className={`h-2 w-2 rounded-full ${statusCfg.dotColor} ${item.status === "in_custody" ? "animate-pulse" : ""}`} />
                          {statusCfg.label}
                        </span>

                        {/* Primary Badge 2: Integrity Status */}
                        {item.integrity_status === "verified" ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-md border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 font-mono uppercase tracking-wider shadow-2xs">
                            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                            HASH VERIFIED
                          </span>
                        ) : item.integrity_status === "compromised" ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-md border border-rose-400 bg-rose-50 dark:bg-rose-950/80 text-rose-800 dark:text-rose-200 font-mono uppercase tracking-wider shadow-2xs animate-pulse">
                            <ShieldAlert className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" />
                            INTEGRITY COMPROMISED
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 text-[11px] font-mono">
                            <AlertCircle className="h-3 w-3 text-amber-600" />
                            VERIFICATION REQUIRED
                          </span>
                        )}

                        {/* Primary Badge 3: Chain of Custody */}
                        {item.integrity_status === "compromised" ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-mono font-bold px-2 py-0.5 rounded-md border border-rose-300 bg-rose-50 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300">
                            <ShieldAlert className="h-3 w-3 text-rose-600" />
                            CHAIN VERIFICATION FAILED
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold px-2 py-0.5 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300">
                            <ShieldCheck className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                            CHAIN VERIFIED &bull; {item.custody_events_count || 1} EVENT{(item.custody_events_count || 1) > 1 ? "S" : ""}
                          </span>
                        )}
                      </div>

                      {/* 4. Metadata Grid */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5 text-xs pt-2 border-t border-slate-100 dark:border-slate-800">
                        <div>
                          <span className="text-slate-400 dark:text-slate-500 text-[10px] uppercase tracking-wider font-semibold block mb-0.5">
                            Active Custodian
                          </span>
                          <span className="font-bold text-slate-900 dark:text-slate-100 text-xs flex items-center gap-1">
                            {item.current_custodian_name || "Investigating Officer"}
                            {isCurrentCustodian && (
                              <span className="text-[10px] font-normal text-blue-600 dark:text-blue-400 font-mono bg-blue-50 dark:bg-blue-950 px-1 rounded">
                                (You)
                              </span>
                            )}
                          </span>
                        </div>

                        <div>
                          <span className="text-slate-400 dark:text-slate-500 text-[10px] uppercase tracking-wider font-semibold block mb-0.5">
                            Registered By
                          </span>
                          <span className="font-medium text-slate-700 dark:text-slate-300 text-xs">
                            {item.registered_by_name || "Officer"}
                          </span>
                        </div>

                        <div>
                          <span className="text-slate-400 dark:text-slate-500 text-[10px] uppercase tracking-wider font-semibold block mb-0.5">
                            Collection Site / Date
                          </span>
                          <span className="font-medium text-slate-700 dark:text-slate-300 text-xs">
                            {item.collection_location || "Evidence Room"} &bull;{" "}
                            {item.collection_date
                              ? new Date(item.collection_date).toLocaleDateString()
                              : new Date(item.created_at).toLocaleDateString()}
                          </span>
                        </div>

                        <div>
                          <span className="text-slate-400 dark:text-slate-500 text-[10px] uppercase tracking-wider font-semibold block mb-0.5">
                            Chain Continuity
                          </span>
                          <span className="font-semibold text-slate-800 dark:text-slate-200 text-xs flex items-center gap-1">
                            <Link2 className="h-3 w-3 text-blue-500" />
                            {item.custody_events_count || 1} Audited Blocks
                          </span>
                        </div>
                      </div>

                      {/* Pending Handover Notice Banner */}
                      {item.transfer_pending && (
                        <div className="rounded-md border border-amber-200 bg-amber-50/80 dark:border-amber-900/50 dark:bg-amber-950/40 p-2.5 flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2 text-amber-900 dark:text-amber-200">
                            <ArrowRightLeft className="h-4 w-4 text-amber-600 shrink-0 animate-pulse" />
                            <span>
                              Custody handover initiated to{" "}
                              <strong className="font-semibold">
                                {item.pending_custodian_name || "Designated Officer"}
                              </strong>
                              {isPendingCustodian && " (You)"}. Awaiting receipt confirmation.
                            </span>
                          </div>
                          {isCurrentCustodian && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCancelTransfer(item)}
                              className="h-7 px-2 text-[11px] text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950"
                            >
                              <Ban className="h-3 w-3 mr-1" /> Retract Transfer
                            </Button>
                          )}
                        </div>
                      )}

                      {/* Compact SHA-256 Display with [Copy] and [View] */}
                      {item.original_file_hash && (
                        <div className="flex items-center justify-between gap-2 font-mono text-xs bg-slate-50 dark:bg-slate-950/80 px-3 py-2 rounded-lg border border-slate-200/80 dark:border-slate-800">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-[10px] font-sans font-bold uppercase tracking-wider text-slate-400 shrink-0">
                              SHA-256:
                            </span>
                            <span className="text-slate-800 dark:text-slate-200 truncate font-mono text-[11px] font-semibold">
                              {item.original_file_hash.substring(0, 12)}...{item.original_file_hash.substring(item.original_file_hash.length - 8)}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleCopyHash(item.original_file_hash!)}
                              className="h-6 px-2 text-[10px] font-sans text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
                              title="Copy complete SHA-256 checksum"
                            >
                              {copiedHash === item.original_file_hash ? (
                                <>
                                  <Check className="h-3 w-3 text-emerald-600 mr-1" /> Copied
                                </>
                              ) : (
                                <>
                                  <Copy className="h-3 w-3 mr-1" /> Copy
                                </>
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setViewingHashItem({
                                number: item.evidence_number,
                                title: item.title,
                                hash: item.original_file_hash!,
                                status: item.integrity_status,
                                date: item.created_at,
                                collectionLocation: item.collection_location,
                              })}
                              className="h-6 px-2 text-[10px] font-sans text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950 flex items-center gap-1"
                            >
                              <Eye className="h-3 w-3" /> View
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Right: Clear Action Hierarchy */}
                    <div className="flex flex-row lg:flex-col gap-2 shrink-0 border-t lg:border-t-0 lg:border-l border-slate-100 dark:border-slate-800 pt-3 lg:pt-0 lg:pl-4 justify-end lg:w-44">
                      {/* PRIMARY ACTION: Verify Artifact (for digital items) */}
                      {item.storage_key ? (
                        <Button
                          size="sm"
                          onClick={() => handleVerifyDigitalIntegrity(item.id)}
                          disabled={verifyingIntegrity === item.id}
                          className="h-8 text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white gap-1.5 shadow-sm"
                          title="Execute authoritative streaming cryptographic SHA-256 check against storage vault"
                        >
                          <ShieldCheck
                            className={`h-3.5 w-3.5 ${
                              verifyingIntegrity === item.id ? "animate-spin" : ""
                            }`}
                          />
                          Verify Artifact
                        </Button>
                      ) : (
                        /* Physical Artifact or Standalone verification */
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenCustodyHistory(item)}
                          className="h-8 text-xs font-medium border-blue-200 dark:border-blue-900 text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950 gap-1.5"
                        >
                          <ShieldCheck className="h-3.5 w-3.5 text-blue-600" /> Audit Ledger
                        </Button>
                      )}

                      {/* SECONDARY ACTION: Custody Ledger */}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenCustodyHistory(item)}
                        className="h-8 text-xs font-medium text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 gap-1.5"
                        title="Inspect immutable cryptographic chain of custody"
                      >
                        <History className="h-3.5 w-3.5 text-slate-500" /> Custody Ledger
                      </Button>

                      {/* CONTEXTUAL ACTION: Designated Recipient Acknowledgment */}
                      {isPendingCustodian && item.transfer_pending && (
                        <Button
                          size="sm"
                          onClick={() => setActiveEvidenceForAck(item)}
                          className="h-8 text-xs gap-1.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold shadow-sm animate-pulse"
                        >
                          <UserCheck className="h-3.5 w-3.5" /> Acknowledge Handover
                        </Button>
                      )}

                      {/* CONTEXTUAL ACTION: Custody Handover Actions */}
                      {isCurrentCustodian && !item.transfer_pending && item.status !== "archived" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setActiveEvidenceForTransfer(item);
                            setTransferRecipientId("");
                            setTransferReason("");
                            setTransferLocation("");
                          }}
                          className="h-8 text-xs gap-1.5 text-blue-600 border-blue-200 dark:border-blue-900 hover:bg-blue-50 dark:hover:bg-blue-950 font-medium"
                        >
                          <ArrowRightLeft className="h-3.5 w-3.5" /> Transfer Custody
                        </Button>
                      )}

                      {/* CONTEXTUAL ACTION: Status Transition Button */}
                      {isCurrentCustodian && hasAllowedTransitions && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setActiveEvidenceForStatus(item);
                            const nextStates = VALID_TRANSITIONS[item.status] || [];
                            setTargetStatus(nextStates[0] || "in_analysis");
                            setStatusReason("");
                            setStatusLocation("");
                          }}
                          className="h-8 text-xs gap-1.5 text-purple-600 border-purple-200 dark:border-purple-900 hover:bg-purple-50 dark:hover:bg-purple-950 font-medium"
                        >
                          <RefreshCw className="h-3.5 w-3.5" /> Advance State
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* MODAL: FULL SHA-256 HASH DETAIL DIALOG */}
      {viewingHashItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-emerald-600" />
                  Authoritative SHA-256 Checksum
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Item: <strong className="font-mono text-slate-700 dark:text-slate-300">{viewingHashItem.number}</strong> &bull; {viewingHashItem.title}
                </p>
              </div>
              <button
                onClick={() => setViewingHashItem(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold text-lg"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                  <span>Cryptographic Digest:</span>
                  <span className="font-mono text-[10px] bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 rounded text-slate-700 dark:text-slate-300">
                    SHA-256 (FIPS 180-4)
                  </span>
                </div>
                <div className="p-2.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 font-mono text-[11px] break-all leading-relaxed text-slate-900 dark:text-slate-100 select-all">
                  {viewingHashItem.hash}
                </div>
                <div className="flex justify-end pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleCopyHash(viewingHashItem.hash)}
                    className="h-7 text-xs gap-1.5"
                  >
                    {copiedHash === viewingHashItem.hash ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-emerald-600" /> Copied to Clipboard
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" /> Copy Checksum
                      </>
                    )}
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2.5 rounded border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/50">
                  <span className="text-slate-400 block mb-0.5">Integrity State</span>
                  <span className={`font-bold font-mono uppercase ${
                    viewingHashItem.status === "verified" ? "text-emerald-600" : viewingHashItem.status === "compromised" ? "text-rose-600" : "text-amber-600"
                  }`}>
                    {viewingHashItem.status || "Verified Baseline"}
                  </span>
                </div>
                <div className="p-2.5 rounded border border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/50">
                  <span className="text-slate-400 block mb-0.5">Statutory Baseline</span>
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    Sec. 63/65B BSA 2023
                  </span>
                </div>
              </div>

              <div className="rounded-md border border-blue-200/80 bg-blue-50/60 dark:border-blue-900/50 dark:bg-blue-950/30 p-2.5 text-[11px] text-blue-900 dark:text-blue-300 leading-relaxed">
                This cryptographic digest is computed at intake and continuously verified on every custodial transfer and download operation. Any byte-level modification invalidates admissibility.
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setViewingHashItem(null)}
                className="h-8 text-xs"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 1: REGISTER EVIDENCE */}
      {showRegisterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-xl bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <PlusCircle className="h-4 w-4 text-blue-600" /> Evidence Intake & Registration
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Establishes the immutable genesis block for this item in the DOCSHIELD chain of custody.
                </p>
              </div>
              <button
                onClick={() => setShowRegisterModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold text-lg"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleRegisterEvidence} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Evidence Title / Designation <span className="text-rose-500">*</span>
                </label>
                <Input
                  required
                  placeholder="e.g. Western Digital 2TB External Hard Drive, Blood Sample Vial"
                  value={registerForm.title}
                  onChange={(e) => setRegisterForm({ ...registerForm, title: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Evidence Category <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={registerForm.evidence_type}
                    onChange={(e) =>
                      setRegisterForm({ ...registerForm, evidence_type: e.target.value as EvidenceType })
                    }
                    className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                  >
                    <option value="device">Seized Hardware / Device</option>
                    <option value="digital_document">Digital Document / File</option>
                    <option value="forensic_artifact">Forensic Artifact / Dump</option>
                    <option value="physical_evidence">Physical Evidence / Seizure</option>
                    <option value="image">Forensic Image / Photo</option>
                    <option value="video">CCTV / Video Recording</option>
                    <option value="audio">Audio Recording / Intercept</option>
                    <option value="other">Other Evidence Item</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Sensitivity Level <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={registerForm.sensitivity_level}
                    onChange={(e) =>
                      setRegisterForm({ ...registerForm, sensitivity_level: e.target.value as EvidenceSensitivity })
                    }
                    className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                  >
                    <option value="standard">Standard</option>
                    <option value="sensitive">Sensitive</option>
                    <option value="highly_sensitive">Highly Sensitive</option>
                    <option value="confidential">Confidential</option>
                    <option value="secret">Secret</option>
                    <option value="classified">Classified</option>
                  </select>
                </div>
              </div>

              {/* Document linkage selector if digital document or if documents exist */}
              {caseDocuments.length > 0 && (
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Link Authoritative Case Document (Captures SHA-256 and MinIO Storage Key)
                  </label>
                  <select
                    value={registerForm.document_id || ""}
                    onChange={(e) =>
                      setRegisterForm({ ...registerForm, document_id: e.target.value || undefined })
                    }
                    className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                  >
                    <option value="">None (Physical / Standalone Evidence)</option>
                    {caseDocuments.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.title} ({doc.file_name || "Document"}) - {doc.file_hash_sha256?.substring(0, 16)}...
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Seizure / Collection Site
                  </label>
                  <Input
                    placeholder="e.g. Suspect Office Desk, Raid Location"
                    value={registerForm.collection_location || ""}
                    onChange={(e) => setRegisterForm({ ...registerForm, collection_location: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Seizure Source / Witness Panchnama
                  </label>
                  <Input
                    placeholder="e.g. Independent Witness Panchnama #4"
                    value={registerForm.source || ""}
                    onChange={(e) => setRegisterForm({ ...registerForm, source: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Item Description & Physical Condition
                </label>
                <textarea
                  rows={2}
                  placeholder="Record serial numbers, physical markings, tamper seals, state of preservation..."
                  value={registerForm.description || ""}
                  onChange={(e) => setRegisterForm({ ...registerForm, description: e.target.value })}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 text-xs text-slate-900 dark:text-slate-100"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Genesis Custody Ledger Notes
                </label>
                <textarea
                  rows={2}
                  placeholder="Official seizure record notes, seal ID, packaging description..."
                  value={registerForm.notes || ""}
                  onChange={(e) => setRegisterForm({ ...registerForm, notes: e.target.value })}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 text-xs text-slate-900 dark:text-slate-100"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowRegisterModal(false)}
                  disabled={registering}
                  className="h-8 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={registering || !registerForm.title.trim()}
                  className="h-8 text-xs bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
                >
                  {registering ? (
                    <>
                      <LoadingSpinner className="h-3.5 w-3.5" /> Committing Genesis Block...
                    </>
                  ) : (
                    <>
                      <PlusCircle className="h-3.5 w-3.5" /> Commit to Ledger
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: INITIATE CUSTODY TRANSFER */}
      {activeEvidenceForTransfer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ArrowRightLeft className="h-4 w-4 text-blue-600" /> Initiate Custody Transfer
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Handover for item: <strong className="font-mono text-slate-700 dark:text-slate-300">{activeEvidenceForTransfer.evidence_number}</strong>
                </p>
              </div>
              <button
                onClick={() => setActiveEvidenceForTransfer(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold text-lg"
              >
                &times;
              </button>
            </div>

            <div className="rounded-md border border-blue-200 bg-blue-50/70 dark:border-blue-900/50 dark:bg-blue-950/40 p-3 text-xs text-blue-900 dark:text-blue-200">
              <strong className="font-semibold block mb-0.5">Two-Phase Protocol Note:</strong>
              You remain the legally responsible custodian until the designated recipient explicitly verifies and acknowledges receipt.
            </div>

            <form onSubmit={handleInitiateTransfer} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Recipient Officer (Authorized Case Member) <span className="text-rose-500">*</span>
                </label>
                <select
                  required
                  value={transferRecipientId}
                  onChange={(e) => setTransferRecipientId(e.target.value)}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                >
                  <option value="">-- Select Recipient Officer --</option>
                  {caseMembers
                    .filter((m) => m.user_id !== currentUser?.id)
                    .map((m) => (
                      <option key={m.id} value={m.user_id}>
                        {m.full_name || m.email} ({m.role_in_case.replace("_", " ")})
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Transfer Purpose / Reason <span className="text-rose-500">*</span>
                </label>
                <textarea
                  required
                  rows={2}
                  placeholder="e.g. Handover to CFSL for forensic imaging and artifact extraction"
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 text-xs text-slate-900 dark:text-slate-100"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Handover Location
                </label>
                <Input
                  placeholder="e.g. CFSL Digital Forensics Lab Room 204"
                  value={transferLocation}
                  onChange={(e) => setTransferLocation(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setActiveEvidenceForTransfer(null)}
                  disabled={transferring}
                  className="h-8 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={transferring || !transferRecipientId || !transferReason.trim()}
                  className="h-8 text-xs bg-blue-600 hover:bg-blue-700 text-white gap-1.5"
                >
                  {transferring ? (
                    <>
                      <LoadingSpinner className="h-3.5 w-3.5" /> Recording Transfer Block...
                    </>
                  ) : (
                    <>
                      <ArrowRightLeft className="h-3.5 w-3.5" /> Authorize & Send Handover
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: ACKNOWLEDGE CUSTODY RECEIPT */}
      {activeEvidenceForAck && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <UserCheck className="h-4 w-4 text-emerald-600" /> Confirm Custody Receipt
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Item: <strong className="font-mono text-slate-700 dark:text-slate-300">{activeEvidenceForAck.evidence_number}</strong>
                </p>
              </div>
              <button
                onClick={() => setActiveEvidenceForAck(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold text-lg"
              >
                &times;
              </button>
            </div>

            <div className="rounded-md border border-amber-200 bg-amber-50/70 dark:border-amber-900/40 dark:bg-amber-950/30 p-3 text-xs text-amber-900 dark:text-amber-200 space-y-1">
              <div>
                Transfer Reason: <span className="font-semibold">{activeEvidenceForAck.transfer_reason}</span>
              </div>
              <div>
                Current Custodian:{" "}
                <span className="font-semibold">
                  {activeEvidenceForAck.current_custodian_name || "Investigating Officer"}
                </span>
              </div>
            </div>

            <form onSubmit={handleAcknowledgeTransfer} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Receipt & Physical Verification Location
                </label>
                <Input
                  placeholder="e.g. CFSL Evidence Locker Room 3, New Delhi"
                  value={ackLocation}
                  onChange={(e) => setAckLocation(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Verification Notes / Tamper Seal Inspection
                </label>
                <textarea
                  rows={2}
                  placeholder="Confirm intact seals, matching serial numbers, packaging condition..."
                  value={ackNotes}
                  onChange={(e) => setAckNotes(e.target.value)}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 text-xs text-slate-900 dark:text-slate-100"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setActiveEvidenceForAck(null)}
                  disabled={acknowledging}
                  className="h-8 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={acknowledging}
                  className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 font-semibold"
                >
                  {acknowledging ? (
                    <>
                      <LoadingSpinner className="h-3.5 w-3.5" /> Committing Acknowledgment Block...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5" /> Accept Legal Custody
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: TRANSITION EVIDENCE STATUS */}
      {activeEvidenceForStatus && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <RefreshCw className="h-4 w-4 text-purple-600" /> Advance Evidence Status
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Item: <strong className="font-mono text-slate-700 dark:text-slate-300">{activeEvidenceForStatus.evidence_number}</strong>
                </p>
              </div>
              <button
                onClick={() => setActiveEvidenceForStatus(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold text-lg"
              >
                &times;
              </button>
            </div>

            <div className="text-xs text-slate-600 dark:text-slate-400">
              Current Status: <Badge variant="outline" className="font-semibold capitalize">{activeEvidenceForStatus.status.replace("_", " ")}</Badge>
            </div>

            <form onSubmit={handleStatusTransition} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Target Legal State <span className="text-rose-500">*</span>
                </label>
                <select
                  required
                  value={targetStatus}
                  onChange={(e) => setTargetStatus(e.target.value as EvidenceStatus)}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                >
                  {(VALID_TRANSITIONS[activeEvidenceForStatus.status] || []).map((state) => (
                    <option key={state} value={state}>
                      {STATUS_CONFIG[state]?.label || state}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Reason for Transition <span className="text-rose-500">*</span>
                </label>
                <textarea
                  required
                  rows={2}
                  placeholder="e.g. Forwarded for forensic hard drive imaging / court exhibition..."
                  value={statusReason}
                  onChange={(e) => setStatusReason(e.target.value)}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 text-xs text-slate-900 dark:text-slate-100"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Action Location
                </label>
                <Input
                  placeholder="e.g. District & Sessions Court Room 4"
                  value={statusLocation}
                  onChange={(e) => setStatusLocation(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setActiveEvidenceForStatus(null)}
                  disabled={transitioning}
                  className="h-8 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={transitioning || !statusReason.trim()}
                  className="h-8 text-xs bg-purple-600 hover:bg-purple-700 text-white gap-1.5"
                >
                  {transitioning ? (
                    <>
                      <LoadingSpinner className="h-3.5 w-3.5" /> Committing State Block...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5" /> Commit State Transition
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 5: STRUCTURED CUSTODY TIMELINE & CRYPTOGRAPHIC LEDGER */}
      {activeEvidenceForCustody && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
          <div className="w-full max-w-3xl bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-5 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-blue-600" /> Cryptographic Custody Ledger & Audit Dossier
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Item: <strong className="font-mono text-slate-700 dark:text-slate-300">{activeEvidenceForCustody.evidence_number}</strong> &bull;{" "}
                  {activeEvidenceForCustody.title}
                </p>
              </div>
              <button
                onClick={() => setActiveEvidenceForCustody(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 font-bold text-lg"
              >
                &times;
              </button>
            </div>

            {/* SECTION 1: EVIDENCE IDENTITY */}
            <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 bg-slate-50/50 dark:bg-slate-950/40 space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                1. EVIDENCE IDENTITY
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 text-[10px] block">Item Designation</span>
                  <span className="font-bold text-slate-900 dark:text-slate-100">{activeEvidenceForCustody.title}</span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Classification</span>
                  <span className="font-mono uppercase font-semibold text-slate-800 dark:text-slate-200">
                    {activeEvidenceForCustody.sensitivity_level}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Category</span>
                  <span className="font-medium text-slate-800 dark:text-slate-200 capitalize">
                    {EVIDENCE_TYPE_LABELS[activeEvidenceForCustody.evidence_type]}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Intake Timestamp</span>
                  <span className="font-mono text-slate-700 dark:text-slate-300">
                    {new Date(activeEvidenceForCustody.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>

            {/* SECTION 2: STATUS & CUSTODIAN */}
            <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 bg-slate-50/50 dark:bg-slate-950/40 space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                2. STATUS & CURRENT CUSTODIAN
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 text-[10px] block">Legal Status</span>
                  <span className="font-bold font-mono text-blue-700 dark:text-blue-300 uppercase">
                    {activeEvidenceForCustody.status.replace("_", " ")}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Active Custodian</span>
                  <span className="font-bold text-slate-900 dark:text-slate-100">
                    {activeEvidenceForCustody.current_custodian_name || "Investigating Officer"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block">Current Location</span>
                  <span className="text-slate-700 dark:text-slate-300">
                    {activeEvidenceForCustody.collection_location || "Evidence Depository"}
                  </span>
                </div>
              </div>
            </div>

            {/* SECTION 3: CHAIN OF CUSTODY (MATHEMATICAL AUDIT) */}
            <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3.5 bg-slate-50/70 dark:bg-slate-950/70 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                    3. CHAIN OF CUSTODY CONTINUITY
                  </div>
                  <div className="text-xs font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                    Mathematical Continuity Audit
                  </div>
                  <div className="text-[11px] text-slate-500">
                    Verifies hash-link sequence: H_n = SHA256(canonical_data || H_n-1) from genesis block to current tip.
                  </div>
                </div>
                <Button
                  size="sm"
                  onClick={() => handleVerifyChain(activeEvidenceForCustody.id)}
                  disabled={verifyingChain === activeEvidenceForCustody.id}
                  className="h-8 text-xs bg-blue-600 hover:bg-blue-700 text-white gap-1.5 shadow-sm shrink-0"
                >
                  {verifyingChain === activeEvidenceForCustody.id ? (
                    <>
                      <LoadingSpinner className="h-3.5 w-3.5" /> Auditing Chain...
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="h-3.5 w-3.5" /> Audit Hash Continuity
                    </>
                  )}
                </Button>
              </div>

              {/* Chain Verification Result Banner */}
              {chainVerifyResult && (
                <div
                  className={`p-3 rounded-lg border text-xs ${
                    chainVerifyResult.valid
                      ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200"
                      : "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/50 dark:text-rose-200"
                  }`}
                >
                  <div className="flex items-center gap-2 font-bold mb-1">
                    {chainVerifyResult.valid ? (
                      <>
                        <ShieldCheck className="h-4 w-4 text-emerald-600" />
                        <span>CHAIN INTEGRITY VALIDATED &bull; {chainVerifyResult.events_checked} BLOCKS VERIFIED</span>
                      </>
                    ) : (
                      <>
                        <ShieldAlert className="h-4 w-4 text-rose-600 animate-pulse" />
                        <span>CHAIN INTEGRITY TAMPERING DETECTED!</span>
                      </>
                    )}
                  </div>
                  {chainVerifyResult.valid ? (
                    <div className="text-[11px] text-emerald-800 dark:text-emerald-300 space-y-0.5 font-mono">
                      <div>Genesis Hash: <code>{chainVerifyResult.genesis_hash}</code></div>
                      <div>Tip Hash: <code>{chainVerifyResult.tip_hash}</code></div>
                    </div>
                  ) : (
                    <div className="text-[11px] text-rose-800 dark:text-rose-300 font-semibold">
                      Reason: {chainVerifyResult.reason || "Hash discontinuity detected on ledger block."}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* SECTION 4 & 5: CRYPTOGRAPHIC HASH & INTEGRITY */}
            {activeEvidenceForCustody.original_file_hash && (
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 bg-slate-50/50 dark:bg-slate-950/40 space-y-2">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                  4. CRYPTOGRAPHIC INTEGRITY BASELINE
                </div>
                <div className="space-y-1 text-xs">
                  <div className="flex items-center justify-between text-[11px] text-slate-500">
                    <span>Baseline Digest (SHA-256):</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCopyHash(activeEvidenceForCustody.original_file_hash!)}
                      className="h-6 px-2 text-[10px]"
                    >
                      {copiedHash === activeEvidenceForCustody.original_file_hash ? (
                        <>
                          <Check className="h-3 w-3 text-emerald-600 mr-1" /> Copied
                        </>
                      ) : (
                        <>
                          <Copy className="h-3 w-3 mr-1" /> Copy Checksum
                        </>
                      )}
                    </Button>
                  </div>
                  <div className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 font-mono text-[11px] break-all select-all">
                    {activeEvidenceForCustody.original_file_hash}
                  </div>
                </div>
              </div>
            )}

            {/* SECTION 6: AUDIT HISTORY (CHRONOLOGICAL EVENT BLOCKS) */}
            <div className="space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
                5. CHRONOLOGICAL CUSTODY BLOCK LEDGER ({custodyEvents.length} BLOCKS)
              </div>

              {loadingCustody ? (
                <div className="flex h-32 items-center justify-center">
                  <LoadingSpinner className="h-6 w-6 text-blue-600" />
                </div>
              ) : custodyEvents.length === 0 ? (
                <p className="text-xs text-slate-500 py-4 text-center">No custody events recorded.</p>
              ) : (
                <div className="relative pl-6 border-l-2 border-slate-200 dark:border-slate-800 space-y-4 my-2">
                  {custodyEvents.map((evt, idx) => (
                    <div key={evt.id} className="relative group">
                      {/* Timeline Node Dot */}
                      <div className="absolute -left-[31px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-blue-600 bg-white dark:bg-slate-900" />

                      <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-xs space-y-2 text-xs">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[10px] text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/80 px-2 py-0.5 rounded font-bold">
                              Block #{idx}
                            </span>
                            <span className="font-bold text-slate-900 dark:text-slate-100 capitalize">
                              {evt.event_type.replace("_", " ")}
                            </span>
                            <Badge
                              variant={evt.acknowledgement_status === "acknowledged" ? "outline" : "destructive"}
                              className="text-[10px] capitalize h-4"
                            >
                              {evt.acknowledgement_status}
                            </Badge>
                          </div>
                          <span className="text-[11px] text-slate-400 font-mono">
                            {new Date(evt.created_at).toLocaleString()}
                          </span>
                        </div>

                        <div className="text-slate-700 dark:text-slate-300 leading-relaxed">
                          {evt.reason}
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-slate-500 border-t border-slate-100 dark:border-slate-800/80 pt-1.5">
                          <div>
                            From: <strong className="font-medium text-slate-700 dark:text-slate-300">{evt.from_user_name || "Genesis Intake"}</strong>
                          </div>
                          <div>
                            To Custodian: <strong className="font-medium text-slate-700 dark:text-slate-300">{evt.to_user_name || "Officer"}</strong>
                          </div>
                          {evt.location && (
                            <div className="col-span-full">
                              Location: <span className="text-slate-700 dark:text-slate-300">{evt.location}</span>
                            </div>
                          )}
                        </div>

                        {/* Cryptographic Event Hash & Previous Hash */}
                        <div className="space-y-1 pt-1 font-mono text-[10px] bg-slate-50 dark:bg-slate-900 p-2 rounded border border-slate-200/50 dark:border-slate-800/50">
                          <div className="flex items-center justify-between gap-1 text-slate-500">
                            <span className="shrink-0 text-slate-400 font-sans uppercase font-bold text-[9px]">Event Hash (H_{idx}):</span>
                            <span className="truncate text-slate-700 dark:text-slate-300 select-all">{evt.event_hash}</span>
                            <button
                              onClick={() => handleCopyHash(evt.event_hash)}
                              className="p-0.5 text-slate-400 hover:text-slate-600"
                              title="Copy event hash"
                            >
                              {copiedHash === evt.event_hash ? (
                                <Check className="h-2.5 w-2.5 text-emerald-600" />
                              ) : (
                                <Copy className="h-2.5 w-2.5" />
                              )}
                            </button>
                          </div>
                          <div className="flex items-center justify-between gap-1 text-slate-400 text-[9px]">
                            <span className="shrink-0 font-sans uppercase font-bold">Prev Hash (H_{idx - 1}):</span>
                            <span className="truncate">{evt.previous_event_hash}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveEvidenceForCustody(null)}
                className="h-8 text-xs"
              >
                Close Ledger
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
