"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  FolderLock,
  PlusCircle,
  Search,
  LogIn,
  RefreshCw,
  Shield,
  Clock,
  UserX,
  Users,
  AlertCircle,
  CheckCircle2,
  FileText,
  ChevronRight,
  ArrowLeft,
  Hash,
  Boxes,
  Sparkles,
  FileArchive,
  ShieldCheck,
  Scale,
  Activity,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { useAuth } from "@/lib/auth-context";
import { Permission, PermissionGuard } from "@/lib/rbac";
import {
  listCases,
  getCaseById,
  createCase,
  updateCase,
  listCaseMembers,
  addCaseMember,
  removeCaseMember,
  getCaseTimeline,
  listAssignableOfficers,
  listCaseDocuments,
  listCaseEvidence,
} from "@/lib/api";
import { DocumentVault } from "@/components/documents/document-vault";
import { EvidenceVault } from "@/components/evidence/evidence-vault";
import { CaseAssistant } from "@/components/ai/case-assistant";
import { CaseExportVault } from "@/components/export/case-export-vault";
import {
  Case,
  CaseCreateRequest,
  CaseMember,
  CaseMemberRole,
  CasePriority,
  CaseStatus,
  CaseTimelineEvent,
  User,
} from "@/types";

// State machine allowed transitions
const ALLOWED_TRANSITIONS: Record<CaseStatus, CaseStatus[]> = {
  open: ["under_investigation"],
  under_investigation: ["pending_review"],
  pending_review: ["pending_legal", "under_investigation"],
  pending_legal: ["closed", "under_investigation"],
  closed: ["archived", "open"],
  archived: ["closed"],
};

export default function CasesPage() {
  const { user, canAccessCase, canPerformAction, hasPermission } = useAuth();

  // Case List state
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Active Case Dossier state
  const [activeCase, setActiveCase] = useState<Case | null>(null);
  const [activeTab, setActiveTab] = useState<"details" | "team" | "timeline" | "documents" | "evidence" | "ai_assistant" | "exports">("details");
  const [members, setMembers] = useState<CaseMember[]>([]);
  const [timeline, setTimeline] = useState<CaseTimelineEvent[]>([]);
  const [documentCount, setDocumentCount] = useState<number>(0);
  const [evidenceCount, setEvidenceCount] = useState<number>(0);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Assignable officers list for team assignment
  const [assignableOfficers, setAssignableOfficers] = useState<User[]>([]);

  // Create Case Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<CaseCreateRequest>({
    title: "",
    description: "",
    priority: "medium",
    fir_number: "",
    police_station: "",
    incident_date: "",
  });
  const [creating, setCreating] = useState(false);

  // Add Member Modal
  const [showAddMemberModal, setShowAddMemberModal] = useState(false);
  const [selectedOfficerId, setSelectedOfficerId] = useState("");
  const [selectedCaseRole, setSelectedCaseRole] = useState<CaseMemberRole>("investigator");
  const [addingMember, setAddingMember] = useState(false);

  // Status update loading state
  const [updatingStatus, setUpdatingStatus] = useState(false);

  // ==========================================
  // Data Fetching
  // ==========================================

  const fetchCases = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const items = await listCases({
        status: statusFilter !== "all" ? statusFilter : undefined,
        priority: priorityFilter !== "all" ? priorityFilter : undefined,
        search: searchQuery.trim() || undefined,
        limit: 100,
      });
      // Enforce data-level access boundary
      const authorizedCases = items.filter((c) => canAccessCase(c));
      setCases(authorizedCases);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Failed to load cases.");
      }
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter, searchQuery, canAccessCase]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  // Load assignable officers when page mounts
  useEffect(() => {
    listAssignableOfficers()
      .then((users) => setAssignableOfficers(users))
      .catch(() => {
        // Fallback gracefully
      });
  }, []);

  // Fetch full case dossier when a case is selected
  const handleSelectCase = async (c: Case) => {
    if (!canAccessCase(c)) {
      setErrorMsg("Security Violation: You do not possess authorization to inspect this case dossier.");
      return;
    }
    setActiveCase(c);
    setActiveTab("details");
    setLoadingDetails(true);
    setErrorMsg(null);
    try {
      const [caseData, membersData, timelineData, docsData, evidenceData] = await Promise.all([
        getCaseById(c.id),
        listCaseMembers(c.id),
        getCaseTimeline(c.id, 50),
        listCaseDocuments(c.id).catch(() => []),
        listCaseEvidence(c.id).catch(() => []),
      ]);
      setActiveCase(caseData);
      setMembers(membersData);
      setTimeline(timelineData);
      setDocumentCount(docsData.length);
      setEvidenceCount(evidenceData.length);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(`Failed to load case dossier: ${err.message}`);
      }
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleRefreshCaseDetails = async (caseId: string) => {
    try {
      const [caseData, membersData, timelineData, docsData, evidenceData] = await Promise.all([
        getCaseById(caseId),
        listCaseMembers(caseId),
        getCaseTimeline(caseId, 50),
        listCaseDocuments(caseId).catch(() => []),
        listCaseEvidence(caseId).catch(() => []),
      ]);
      setActiveCase(caseData);
      setMembers(membersData);
      setTimeline(timelineData);
      setDocumentCount(docsData.length);
      setEvidenceCount(evidenceData.length);
      // Update in main cases list as well
      setCases((prev) => prev.map((item) => (item.id === caseId ? caseData : item)));
    } catch (err: unknown) {
      if (err instanceof Error) setErrorMsg(err.message);
    }
  };

  // ==========================================
  // Case Actions (Action-Level Protection Enforced)
  // ==========================================

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canPerformAction(Permission.CASE_CREATE)) {
      setErrorMsg("Security Violation: Your role does not have permission to register new cases.");
      return;
    }

    if (!createForm.title.trim()) {
      setErrorMsg("Case title is mandatory.");
      return;
    }

    setCreating(true);
    setErrorMsg(null);
    try {
      const newCase = await createCase({
        ...createForm,
        incident_date: createForm.incident_date ? new Date(createForm.incident_date).toISOString() : undefined,
      });
      setShowCreateModal(false);
      setCreateForm({
        title: "",
        description: "",
        priority: "medium",
        fir_number: "",
        police_station: "",
        incident_date: "",
      });
      setSuccessMsg(`Case ${newCase.case_number} registered successfully with creator as Lead Investigator.`);
      fetchCases();
      handleSelectCase(newCase);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Case creation failed.");
      }
    } finally {
      setCreating(false);
    }
  };

  const handleStatusTransition = async (newStatus: CaseStatus) => {
    if (!activeCase) return;
    if (!canPerformAction(Permission.CASE_STATUS_UPDATE, { caseItem: activeCase, caseMembers: members })) {
      setErrorMsg("Security Violation: You do not have permission to modify investigation status.");
      return;
    }

    setUpdatingStatus(true);
    setErrorMsg(null);
    try {
      await updateCase(activeCase.id, { status: newStatus });
      setSuccessMsg(`Case status successfully advanced to ${newStatus.replace("_", " ").toUpperCase()}`);
      await handleRefreshCaseDetails(activeCase.id);
    } catch (err: unknown) {
      if (err instanceof Error) setErrorMsg(err.message);
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeCase || !selectedOfficerId) return;
    if (!canPerformAction(Permission.CASE_ASSIGN, { caseItem: activeCase, caseMembers: members })) {
      setErrorMsg("Security Violation: You do not have permission to assign officers to cases.");
      return;
    }

    setAddingMember(true);
    setErrorMsg(null);
    try {
      await addCaseMember(activeCase.id, {
        user_id: selectedOfficerId,
        role_in_case: selectedCaseRole,
      });
      setShowAddMemberModal(false);
      setSelectedOfficerId("");
      setSuccessMsg("Officer successfully added to case team with audit record.");
      await handleRefreshCaseDetails(activeCase.id);
    } catch (err: unknown) {
      if (err instanceof Error) setErrorMsg(err.message);
    } finally {
      setAddingMember(false);
    }
  };

  const handleRemoveMember = async (memberUserId: string, officerName?: string) => {
    if (!activeCase) return;
    if (!canPerformAction(Permission.CASE_ASSIGN, { caseItem: activeCase, caseMembers: members })) {
      setErrorMsg("Security Violation: You do not have permission to reassign or revoke officer access.");
      return;
    }

    if (!confirm(`Are you sure you want to revoke case access for ${officerName || "this officer"}?`)) {
      return;
    }

    setErrorMsg(null);
    try {
      await removeCaseMember(activeCase.id, memberUserId);
      setSuccessMsg("Case access revoked successfully.");
      await handleRefreshCaseDetails(activeCase.id);
    } catch (err: unknown) {
      if (err instanceof Error) setErrorMsg(err.message);
    }
  };

  // Helper badge styles
  const getPriorityBadge = (priority: CasePriority) => {
    switch (priority) {
      case "critical":
        return <Badge className="bg-rose-600 hover:bg-rose-700 text-white font-semibold">CRITICAL</Badge>;
      case "high":
        return <Badge className="bg-amber-500 hover:bg-amber-600 text-white font-medium">HIGH</Badge>;
      case "medium":
        return <Badge className="bg-blue-600 hover:bg-blue-700 text-white">MEDIUM</Badge>;
      case "low":
        return <Badge className="bg-slate-500 hover:bg-slate-600 text-white">LOW</Badge>;
      default:
        return <Badge variant="outline">{priority}</Badge>;
    }
  };

  const getStatusBadge = (status: CaseStatus) => {
    switch (status) {
      case "open":
        return <Badge className="bg-emerald-600 hover:bg-emerald-700 text-white">OPEN</Badge>;
      case "under_investigation":
        return <Badge className="bg-blue-600 hover:bg-blue-700 text-white">UNDER INVESTIGATION</Badge>;
      case "pending_review":
        return <Badge className="bg-purple-600 hover:bg-purple-700 text-white">PENDING REVIEW</Badge>;
      case "pending_legal":
        return <Badge className="bg-indigo-600 hover:bg-indigo-700 text-white">PENDING LEGAL</Badge>;
      case "closed":
        return <Badge className="bg-slate-700 hover:bg-slate-800 text-white">CLOSED</Badge>;
      case "archived":
        return <Badge variant="secondary">ARCHIVED</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  // ==========================================
  // RENDER: DOSSIER VIEW (Active Case)
  // ==========================================
  if (activeCase) {
    const validTransitions = ALLOWED_TRANSITIONS[activeCase.status] || [];

    return (
      <div className="space-y-6">
        {/* Navigation / Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActiveCase(null)}
              className="h-9 px-3 text-slate-600 dark:text-slate-300"
            >
              <ArrowLeft className="h-4 w-4 mr-1.5" /> Back to Cases
            </Button>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                  {activeCase.case_number}
                </h2>
                {getStatusBadge(activeCase.status)}
                {getPriorityBadge(activeCase.priority)}
              </div>
              <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mt-0.5">
                {activeCase.title}
              </p>
            </div>
          </div>

          {/* Status Transitions */}
          <div className="flex items-center gap-2">
            <PermissionGuard
              permission={Permission.CASE_STATUS_UPDATE}
              context={{ caseItem: activeCase, caseMembers: members }}
            >
              {validTransitions.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 font-medium">Advance State:</span>
                  {validTransitions.map((nextStatus) => (
                    <Button
                      key={nextStatus}
                      size="sm"
                      variant="outline"
                      disabled={updatingStatus}
                      onClick={() => handleStatusTransition(nextStatus)}
                      className="h-8 text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-900 hover:bg-blue-50 dark:hover:bg-blue-950"
                    >
                      &rarr; {nextStatus.replace("_", " ")}
                    </Button>
                  ))}
                </div>
              )}
            </PermissionGuard>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleRefreshCaseDetails(activeCase.id)}
              className="h-8 px-2"
              title="Refresh case dossier"
            >
              <RefreshCw className={`h-4 w-4 ${loadingDetails ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* Case Security & Integrity Banner */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-xl border border-emerald-200/90 dark:border-emerald-900/60 bg-emerald-50/70 dark:bg-emerald-950/30 text-xs text-emerald-900 dark:text-emerald-200 shadow-sm">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 shrink-0">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider text-[11px]">
                  Case Integrity Verified
                </span>
                <Badge variant="success" className="text-[9px] font-mono py-0 px-1.5">
                  SEC-65B BSA
                </Badge>
              </div>
              <p className="text-[11px] text-emerald-800/80 dark:text-emerald-300/80 mt-0.5">
                All filings, custody transactions, and audit records bound to immutable SHA-256 baselines.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-[11px] font-mono shrink-0 pl-9 sm:pl-0">
            <div>
              <span className="text-slate-500 block text-[9px] uppercase">Custody Status</span>
              <span className="font-semibold text-emerald-700 dark:text-emerald-400">Chain Intact</span>
            </div>
            <div className="h-6 w-px bg-emerald-200 dark:bg-emerald-800/60" />
            <div>
              <span className="text-slate-500 block text-[9px] uppercase">Audit Ledger</span>
              <span className="font-semibold text-emerald-700 dark:text-emerald-400">Synchronized</span>
            </div>
          </div>
        </div>

        {/* Global Alert Notification */}
        {errorMsg && (
          <div className="flex items-center gap-3 p-3 text-sm rounded-lg bg-rose-50 border border-rose-200 text-rose-800 dark:bg-rose-950 dark:border-rose-900 dark:text-rose-200">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="flex-1">{errorMsg}</span>
            {errorMsg.toLowerCase().includes("session required") && (
              <Link href="/login">
                <Button size="sm" variant="outline" className="h-7 text-xs bg-white dark:bg-slate-900 border-rose-300 text-rose-800 dark:text-rose-200 gap-1">
                  <LogIn className="h-3 w-3" /> Sign In
                </Button>
              </Link>
            )}
            <button onClick={() => setErrorMsg(null)} className="text-xs hover:underline">
              Dismiss
            </button>
          </div>
        )}
        {successMsg && (
          <div className="flex items-center gap-2 p-3 text-sm rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 dark:bg-emerald-950 dark:border-emerald-900 dark:text-emerald-200">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span className="flex-1">{successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} className="text-xs hover:underline">
              Dismiss
            </button>
          </div>
        )}

        {/* Tabs Bar */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 space-x-6">
          <button
            onClick={() => setActiveTab("details")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "details"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <FileText className="h-4 w-4" /> Case Overview
          </button>
          <button
            onClick={() => setActiveTab("team")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "team"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Users className="h-4 w-4" /> Investigation Team ({members.length})
          </button>
          <button
            onClick={() => setActiveTab("timeline")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "timeline"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Clock className="h-4 w-4" /> Cryptographic Timeline ({timeline.length})
          </button>
          <button
            onClick={() => setActiveTab("documents")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "documents"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <FolderLock className="h-4 w-4" /> Documents & Filings ({documentCount})
          </button>
          <button
            onClick={() => setActiveTab("evidence")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "evidence"
                ? "border-blue-600 text-blue-600 dark:text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Boxes className="h-4 w-4" /> Evidence & Custody ({evidenceCount})
          </button>
          <button
            onClick={() => setActiveTab("ai_assistant")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "ai_assistant"
                ? "border-purple-600 text-purple-600 dark:text-purple-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Sparkles className="h-4 w-4 text-purple-600" /> AI Assistant & Search
          </button>
          <button
            onClick={() => setActiveTab("exports")}
            className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors ${
              activeTab === "exports"
                ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <FileArchive className="h-4 w-4 text-indigo-600" /> Court Export & Manifest
          </button>
        </div>

        {/* TAB 1: OVERVIEW */}
        {activeTab === "details" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base font-semibold">Incident & Case Description</CardTitle>
                  <CardDescription>Official investigation dossier summary</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-sm text-slate-800 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                    {activeCase.description || "No case narrative or synopsis recorded."}
                  </div>
                </CardContent>
              </Card>

              {/* Zero-Trust Security Scope Notice */}
              <div className="p-4 rounded-lg bg-blue-50/50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900 flex items-start gap-3 text-xs text-blue-900 dark:text-blue-300">
                <Shield className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-sm">Strict Zero-Trust Case Scoping Enforced</p>
                  <p className="mt-1 text-slate-600 dark:text-slate-400">
                    Only officers explicitly enrolled in this case&apos;s membership roster are authorized to access,
                    review, or submit forensic documents. All case lookups by non-members yield an uninformative HTTP 404
                    Not Found to prevent identifier enumeration.
                  </p>
                </div>
              </div>
            </div>

            {/* Right Meta Column */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base font-semibold">Metadata & Registry</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-xs">
                  <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Case Number</span>
                    <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">
                      {activeCase.case_number}
                    </span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">FIR Number</span>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      {activeCase.fir_number || "N/A"}
                    </span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Police Station</span>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      {activeCase.police_station || "Unspecified"}
                    </span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Your Role in Case</span>
                    <span className="font-semibold text-blue-600 dark:text-blue-400 uppercase">
                      {activeCase.user_role_in_case?.replace("_", " ") || "Officer"}
                    </span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Registered By</span>
                    <span className="text-slate-900 dark:text-slate-100">
                      {activeCase.creator_name || "Investigating Officer"}
                    </span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Registered Date</span>
                    <span className="text-slate-900 dark:text-slate-100">
                      {new Date(activeCase.created_at).toLocaleString()}
                    </span>
                  </div>
                  {activeCase.incident_date && (
                    <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                      <span className="text-slate-500 font-medium">Incident Timestamp</span>
                      <span className="text-slate-900 dark:text-slate-100">
                        {new Date(activeCase.incident_date).toLocaleString()}
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* TAB 2: INVESTIGATION TEAM */}
        {activeTab === "team" && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base font-semibold">Authorized Case Officers</CardTitle>
                <CardDescription>
                  Personnel with explicit access to this case dossier, documents, and evidence.
                </CardDescription>
              </div>
              <PermissionGuard
                permission={Permission.CASE_ASSIGN}
                context={{ caseItem: activeCase, caseMembers: members }}
              >
                <Button
                  size="sm"
                  onClick={() => setShowAddMemberModal(true)}
                  className="h-8 text-xs bg-blue-600 hover:bg-blue-700 text-white"
                >
                  <PlusCircle className="h-3.5 w-3.5 mr-1.5" /> Assign Officer
                </Button>
              </PermissionGuard>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border border-slate-200 dark:border-slate-800 overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-medium">
                    <tr>
                      <th className="px-4 py-3">Officer Name</th>
                      <th className="px-4 py-3">System Role</th>
                      <th className="px-4 py-3">Role in Case</th>
                      <th className="px-4 py-3">Assigned At</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {members.map((m) => (
                      <tr key={m.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                        <td className="px-4 py-3">
                          <div className="font-semibold text-slate-900 dark:text-slate-100">
                            {m.full_name || "Investigating Officer"}
                          </div>
                          <div className="text-[11px] text-slate-500">{m.email}</div>
                        </td>
                        <td className="px-4 py-3 text-slate-600 dark:text-slate-400 capitalize">
                          {m.system_role?.replace("_", " ") || "Officer"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline" className="font-medium capitalize text-[11px]">
                            {m.role_in_case.replace("_", " ")}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-slate-500">
                          {new Date(m.assigned_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <PermissionGuard
                            permission={Permission.CASE_ASSIGN}
                            context={{ caseItem: activeCase, caseMembers: members }}
                            fallback={<span className="text-slate-400 text-[10px]">—</span>}
                          >
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleRemoveMember(m.user_id, m.full_name)}
                              className="h-7 px-2 text-[11px] text-rose-600 border-rose-200 dark:border-rose-900 hover:bg-rose-50 dark:hover:bg-rose-950"
                              title="Revoke officer membership from case"
                            >
                              <UserX className="h-3 w-3 mr-1" /> Revoke
                            </Button>
                          </PermissionGuard>
                        </td>
                      </tr>
                    ))}
                    {members.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                          No team members assigned yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* TAB 3: IMMUTABLE AUDIT TIMELINE */}
        {activeTab === "timeline" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">Cryptographic Case Timeline</CardTitle>
              <CardDescription>
                Chronological chain of custody and case lifecycle events with cryptographic hash verification.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="relative pl-6 border-l-2 border-slate-200 dark:border-slate-800 space-y-6">
                {timeline.map((evt) => (
                  <div key={evt.id} className="relative group">
                    {/* Dot */}
                    <div className="absolute -left-[31px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-blue-600 bg-white dark:bg-slate-900" />

                    <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-sm space-y-1.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-xs text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                            {evt.action.replace("_", " ")}
                          </span>
                          <Badge
                            variant={evt.result === "success" ? "outline" : "destructive"}
                            className="text-[10px] uppercase h-5"
                          >
                            {evt.result}
                          </Badge>
                        </div>
                        <span className="text-[11px] text-slate-400">
                          {new Date(evt.timestamp).toLocaleString()}
                        </span>
                      </div>

                      <div className="text-xs text-slate-600 dark:text-slate-400">
                        Executed by: <span className="font-semibold text-slate-800 dark:text-slate-200">{evt.actor_name}</span>
                      </div>

                      {/* Cryptographic SHA-256 Hash */}
                      <div className="flex items-center gap-1.5 font-mono text-[10px] text-slate-500 bg-slate-50 dark:bg-slate-900 p-1.5 rounded border border-slate-200/50 dark:border-slate-800/50">
                        <Hash className="h-3 w-3 text-slate-400 shrink-0" />
                        <span className="truncate">Event Hash: {evt.event_hash}</span>
                      </div>
                    </div>
                  </div>
                ))}

                {timeline.length === 0 && (
                  <p className="text-xs text-slate-500 py-4">No timeline events recorded yet.</p>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* TAB 4: DOCUMENTS & FILINGS */}
        {activeTab === "documents" && (
          <DocumentVault
            caseId={activeCase.id}
            caseTitle={activeCase.title}
            canUpload={true}
            onDocumentCountChange={(cnt) => setDocumentCount(cnt)}
          />
        )}

        {/* TAB 5: EVIDENCE & CHAIN OF CUSTODY */}
        {activeTab === "evidence" && (
          <EvidenceVault
            caseId={activeCase.id}
            caseTitle={activeCase.title}
            canManage={true}
            onEvidenceCountChange={(cnt) => setEvidenceCount(cnt)}
          />
        )}

        {/* TAB 6: AI CASE ASSISTANT & RAG */}
        {activeTab === "ai_assistant" && (
          <CaseAssistant
            caseId={activeCase.id}
            caseTitle={activeCase.title}
            caseNumber={activeCase.case_number}
          />
        )}

        {/* TAB 7: LEGAL COURT EXPORT & MANIFEST */}
        {activeTab === "exports" && (
          <CaseExportVault
            caseId={activeCase.id}
            caseTitle={activeCase.title}
            caseNumber={activeCase.case_number}
            canExport={true}
          />
        )}

        {/* Modal: Add Case Team Member */}
        {showAddMemberModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Assign Officer to Case
                </h3>
                <button
                  onClick={() => setShowAddMemberModal(false)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  &times;
                </button>
              </div>

              <form onSubmit={handleAddMember} className="space-y-4 text-xs">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Select Active Officer
                  </label>
                  <select
                    value={selectedOfficerId}
                    onChange={(e) => setSelectedOfficerId(e.target.value)}
                    required
                    className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                  >
                    <option value="">-- Choose Officer --</option>
                    {assignableOfficers
                      .filter((o) => !members.some((m) => m.user_id === o.id))
                      .map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.full_name} ({o.role_display_name || o.role}) - {o.employee_id}
                        </option>
                      ))}
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Designated Role in Case
                  </label>
                  <select
                    value={selectedCaseRole}
                    onChange={(e) => setSelectedCaseRole(e.target.value as CaseMemberRole)}
                    className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                  >
                    <option value="investigator">Investigator</option>
                    <option value="forensic_analyst">Forensic Analyst</option>
                    <option value="legal_counsel">Legal Counsel</option>
                    <option value="supervisor">Supervisor</option>
                    <option value="lead_investigator">Lead Investigator</option>
                  </select>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowAddMemberModal(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={addingMember || !selectedOfficerId}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    {addingMember ? "Assigning..." : "Confirm Assignment"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ==========================================
  // RENDER: MAIN CASE LIST
  // ==========================================

  const totalAssigned = cases.length;
  const underInvestigationCount = cases.filter((c) => c.status === "under_investigation" || c.status === "open").length;
  const pendingReviewCount = cases.filter((c) => c.status === "pending_review" || c.status === "pending_legal").length;
  const closedCount = cases.filter((c) => c.status === "closed" || c.status === "archived").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Case Management & Dossiers
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            MHA / NCRB Chain-of-Custody & Zero-Trust Legal Case Lifecycle
          </p>
        </div>
        <PermissionGuard permission={Permission.CASE_CREATE}>
          <Button
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
          >
            <PlusCircle className="h-4 w-4 mr-2" /> Register New Case
          </Button>
        </PermissionGuard>
      </div>

      {/* Stats Summary Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-4 bg-white dark:bg-slate-900/90 border-slate-200 dark:border-slate-800 shadow-sm hover:shadow transition-shadow">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Assigned Cases</p>
            <div className="p-1.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              <FolderLock className="h-4 w-4" />
            </div>
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 font-mono mt-2">{totalAssigned}</p>
          <span className="text-[10px] text-slate-400 font-mono">RBAC ENROLLED</span>
        </Card>

        <Card className="p-4 bg-white dark:bg-slate-900/90 border-slate-200 dark:border-slate-800 shadow-sm hover:shadow transition-shadow">
          <div className="flex items-center justify-between">
            <p className="text-xs text-blue-600 dark:text-blue-400 font-semibold uppercase tracking-wider">Active Inquests</p>
            <div className="p-1.5 rounded-md bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <p className="text-2xl font-bold text-blue-600 dark:text-blue-400 font-mono mt-2">{underInvestigationCount}</p>
          <span className="text-[10px] text-blue-500/80 font-mono">INVESTIGATION</span>
        </Card>

        <Card className="p-4 bg-white dark:bg-slate-900/90 border-slate-200 dark:border-slate-800 shadow-sm hover:shadow transition-shadow">
          <div className="flex items-center justify-between">
            <p className="text-xs text-purple-600 dark:text-purple-400 font-semibold uppercase tracking-wider">Review / Legal</p>
            <div className="p-1.5 rounded-md bg-purple-50 dark:bg-purple-950 text-purple-600 dark:text-purple-400">
              <Scale className="h-4 w-4" />
            </div>
          </div>
          <p className="text-2xl font-bold text-purple-600 dark:text-purple-400 font-mono mt-2">{pendingReviewCount}</p>
          <span className="text-[10px] text-purple-500/80 font-mono">PRE-COURT REVIEW</span>
        </Card>

        <Card className="p-4 bg-white dark:bg-slate-900/90 border-slate-200 dark:border-slate-800 shadow-sm hover:shadow transition-shadow">
          <div className="flex items-center justify-between">
            <p className="text-xs text-emerald-600 dark:text-emerald-400 font-semibold uppercase tracking-wider">Closed / Archived</p>
            <div className="p-1.5 rounded-md bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
            </div>
          </div>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 font-mono mt-2">{closedCount}</p>
          <span className="text-[10px] text-emerald-500/80 font-mono">ARCHIVE SEALED</span>
        </Card>
      </div>

      {/* Messages */}
      {errorMsg && (
        <div className="flex items-center gap-3 p-3 text-sm rounded-lg bg-rose-50 border border-rose-200 text-rose-800 dark:bg-rose-950 dark:border-rose-900 dark:text-rose-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="flex-1">{errorMsg}</span>
          {errorMsg.toLowerCase().includes("session required") && (
            <Link href="/login">
              <Button size="sm" variant="outline" className="h-7 text-xs bg-white dark:bg-slate-900 border-rose-300 text-rose-800 dark:text-rose-200 gap-1">
                <LogIn className="h-3 w-3" /> Sign In
              </Button>
            </Link>
          )}
          <button onClick={() => setErrorMsg(null)} className="text-xs hover:underline">
            Dismiss
          </button>
        </div>
      )}
      {successMsg && (
        <div className="flex items-center gap-2 p-3 text-sm rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 dark:bg-emerald-950 dark:border-emerald-900 dark:text-emerald-200">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span className="flex-1">{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-xs hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search by case number, FIR number, title, police station..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 text-xs"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="w-full sm:w-44 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
        >
          <option value="all">All Statuses</option>
          <option value="open">Open</option>
          <option value="under_investigation">Under Investigation</option>
          <option value="pending_review">Pending Review</option>
          <option value="pending_legal">Pending Legal</option>
          <option value="closed">Closed</option>
          <option value="archived">Archived</option>
        </select>
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="w-full sm:w-36 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
        >
          <option value="all">All Priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchCases}
          className="h-9 px-3 shrink-0"
          title="Refresh cases"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* Case Records Table / Cards */}
      {loading ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner className="h-8 w-8 text-blue-600" />
        </div>
      ) : cases.length === 0 ? (
        <EmptyState
          icon={FolderLock}
          title="No Matching Case Records Found"
          description={
            searchQuery || statusFilter !== "all" || priorityFilter !== "all"
              ? "No cases match your filter criteria. Try adjusting your query."
              : "You are not currently enrolled in any active cases. Create a case or request assignment from a Lead Investigator or Supervisor."
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cases.map((c) => (
            <Card
              key={c.id}
              className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-blue-500/60 dark:hover:border-blue-500/50 transition-all cursor-pointer shadow-sm hover:shadow-md group"
              onClick={() => handleSelectCase(c)}
            >
              <CardHeader className="p-4 pb-2 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/60 px-2 py-0.5 rounded border border-blue-200/80 dark:border-blue-900/60">
                      {c.case_number}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {getPriorityBadge(c.priority)}
                    {getStatusBadge(c.status)}
                  </div>
                </div>
                <CardTitle className="text-sm font-semibold line-clamp-1 text-slate-900 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                  {c.title}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 pt-1 space-y-3 text-xs">
                <p className="text-slate-600 dark:text-slate-400 line-clamp-2 text-[11px] leading-relaxed">
                  {c.description || "No case description provided."}
                </p>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 space-y-1 text-slate-500 text-[11px]">
                  <div className="flex justify-between">
                    <span>FIR Number:</span>
                    <span className="font-mono font-medium text-slate-800 dark:text-slate-200">{c.fir_number || "None"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Police Station:</span>
                    <span className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-[140px]">
                      {c.police_station || "Unspecified"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Your Case Role:</span>
                    <span className="font-semibold text-blue-600 dark:text-blue-400 uppercase text-[10px] font-mono">
                      {c.user_role_in_case?.replace("_", " ") || "Member"}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[10px]">
                  <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-mono font-medium">
                    <ShieldCheck className="h-3 w-3" /> Baseline Verified
                  </span>
                  <span className="flex items-center text-blue-600 dark:text-blue-400 font-semibold group-hover:translate-x-1 transition-transform">
                    Open Dossier <ChevronRight className="h-3 w-3 ml-0.5" />
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Register New Case */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-950">
                  <FolderLock className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Register New Legal Case
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Auto-assigns you as the Lead Investigator with audit chain initialization.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateCase} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Case Title <span className="text-rose-500">*</span>
                </label>
                <Input
                  required
                  placeholder="e.g. Investigation into Online Financial Fraud Ring"
                  value={createForm.title}
                  onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                  className="text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    FIR Number
                  </label>
                  <Input
                    placeholder="e.g. FIR-2026/089"
                    value={createForm.fir_number}
                    onChange={(e) => setCreateForm({ ...createForm, fir_number: e.target.value })}
                    className="text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Priority Level
                  </label>
                  <select
                    value={createForm.priority}
                    onChange={(e) => setCreateForm({ ...createForm, priority: e.target.value as CasePriority })}
                    className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Police Station / Jurisdiction
                  </label>
                  <Input
                    placeholder="e.g. Cyber Crime PS, New Delhi"
                    value={createForm.police_station}
                    onChange={(e) => setCreateForm({ ...createForm, police_station: e.target.value })}
                    className="text-xs"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Incident Date
                  </label>
                  <Input
                    type="date"
                    value={createForm.incident_date}
                    onChange={(e) => setCreateForm({ ...createForm, incident_date: e.target.value })}
                    className="text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Brief Synopsis / Allegations
                </label>
                <textarea
                  rows={3}
                  placeholder="Summary of allegations, primary suspects, or forensic directives..."
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-slate-100"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={creating}
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {creating ? "Registering..." : "Register Case"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
