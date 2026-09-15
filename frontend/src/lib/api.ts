import {
  AuditEvent,
  AuditVerificationResult,
  Case,
  CaseCreateRequest,
  CaseExport,
  CaseMember,
  CaseMemberAddRequest,
  CaseTimelineEvent,
  CaseUpdateRequest,
  ChangePasswordRequest,
  CustodyChainVerificationResult,
  Document,
  DocumentAIInsights,
  DocumentIntegrityCheckResult,
  DocumentVersion,
  Evidence,
  EvidenceCustodyAcknowledgeRequest,
  EvidenceCustodyEvent,
  EvidenceCustodyTransferRequest,
  EvidenceIntegrityResult,
  EvidenceRegisterRequest,
  EvidenceStatusTransitionRequest,
  EvidenceUpdateRequest,
  ExportCreateRequest,
  ExportListResponse,
  ExtractedEntity,
  LoginRequest,
  PermissionResponse,
  RAGAnswerResponse,
  RoleResponse,
  SearchAskResponse,
  SearchResponse,
  SearchStatusResponse,
  SecurityEvent,
  SecurityEventsListResponse,
  SecurityMetrics,
  SemanticSearchResponse,
  SystemHealth,
  TamperSimulationRequest,
  TamperSimulationResponse,
  TokenResponse,
  User,
  UserCreateRequest,
  UserUpdateRequest,
} from "@/types";
import { isSupabaseConfigured } from "./supabase/client";
import {
  supabaseListCases,
  supabaseGetCaseById,
  supabaseCreateCase,
  supabaseUpdateCase,
  supabaseListCaseMembers,
  supabaseAddCaseMember,
  supabaseRemoveCaseMember,
  supabaseGetCaseTimeline,
  supabaseListAssignableOfficers,
  supabaseLogin,
  supabaseGetCurrentUser,
  supabaseLogout,
  supabaseListAuditEvents,
  supabaseGetSecurityMetrics,
  supabaseListCaseDocuments,
  supabaseUploadDocument,
  supabaseListAllAccessibleDocuments,
  supabaseGetDocument,
  supabaseListCaseEvidence,
  supabaseListAllAccessibleEvidence,
  supabaseGetEvidenceById,
  supabaseRegisterEvidence,
  supabaseUpdateEvidence,
  supabaseInitiateCustodyTransfer,
  supabaseAcknowledgeCustodyTransfer,
  supabaseCancelCustodyTransfer,
  supabaseTransitionEvidenceStatus,
  supabaseListEvidenceCustodyHistory,
  supabaseVerifyCustodyChain,
  supabaseVerifyEvidenceDigitalIntegrity,
} from "./supabase/service";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const TOKEN_STORAGE_KEY = "docshield_access_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function removeStoredToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(!isFormData ? { "Content-Type": "application/json" } : {}),
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401) {
      if (isSupabaseConfigured()) {
        throw new Error("Local backend authentication unavailable in Supabase mode.");
      }
      throw new Error("Session required. Please sign in to access protected records.");
    }
    let errorDetail = "An unexpected error occurred.";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      errorDetail = `Request failed with status ${response.status}: ${response.statusText}`;
    }
    throw new Error(errorDetail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// ==========================================
// Authentication APIs
// ==========================================

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  if (isSupabaseConfigured()) {
    const res = await supabaseLogin(credentials);
    if (res.access_token) {
      setStoredToken(res.access_token);
    }
    return res;
  }
  const res = await request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
  if (res.access_token) {
    setStoredToken(res.access_token);
  }
  return res;
}

export async function getCurrentUser(): Promise<User> {
  if (isSupabaseConfigured()) {
    return supabaseGetCurrentUser();
  }
  return request<User>("/auth/me", {
    method: "GET",
  });
}

export async function refreshToken(): Promise<TokenResponse> {
  const res = await request<TokenResponse>("/auth/refresh", {
    method: "POST",
  });
  if (res.access_token) {
    setStoredToken(res.access_token);
  }
  return res;
}

export async function logout(): Promise<void> {
  if (isSupabaseConfigured()) {
    await supabaseLogout();
    removeStoredToken();
    return;
  }
  try {
    await request<void>("/auth/logout", {
      method: "POST",
    });
  } finally {
    removeStoredToken();
  }
}

export async function changePassword(data: ChangePasswordRequest): Promise<void> {
  await request<void>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ==========================================
// User Management APIs (System Admin)
// ==========================================

export async function listUsers(params?: {
  role_id?: string;
  is_active?: boolean;
  skip?: number;
  limit?: number;
}): Promise<User[]> {
  const query = new URLSearchParams();
  if (params?.role_id) query.set("role_id", params.role_id);
  if (params?.is_active !== undefined) query.set("is_active", String(params.is_active));
  if (params?.skip !== undefined) query.set("skip", String(params.skip));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));

  const endpoint = `/users${query.toString() ? `?${query.toString()}` : ""}`;
  return request<User[]>(endpoint, { method: "GET" });
}

export async function getUserById(id: string): Promise<User> {
  return request<User>(`/users/${id}`, { method: "GET" });
}

export async function createUser(data: UserCreateRequest): Promise<User> {
  return request<User>("/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUser(id: string, data: UserUpdateRequest): Promise<User> {
  return request<User>(`/users/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function updateUserStatus(
  id: string,
  is_active?: boolean,
  is_locked?: boolean
): Promise<User> {
  return request<User>(`/users/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active, is_locked }),
  });
}

export async function adminResetPassword(
  id: string,
  newPassword?: string
): Promise<{ user_id: string; employee_id: string; temporary_password?: string; message: string }> {
  return request(`/admin/users/${id}/reset-password`, {
    method: "POST",
    body: JSON.stringify(newPassword ? { new_password: newPassword } : {}),
  });
}

// ==========================================
// Roles & Permissions APIs
// ==========================================

export async function listRoles(): Promise<RoleResponse[]> {
  return request<RoleResponse[]>("/roles", { method: "GET" });
}

export async function listPermissions(): Promise<PermissionResponse[]> {
  return request<PermissionResponse[]>("/permissions", { method: "GET" });
}

// ==========================================
// System Health
// ==========================================

export async function fetchHealth(): Promise<SystemHealth> {
  return request<SystemHealth>("/health", { method: "GET" });
}

// ==========================================
// Phase 3: Case Management APIs
// ==========================================

export async function listCases(params?: {
  status?: string;
  priority?: string;
  search?: string;
  skip?: number;
  limit?: number;
}): Promise<Case[]> {
  if (isSupabaseConfigured()) {
    return supabaseListCases(params);
  }
  const query = new URLSearchParams();
  if (params?.status) query.append("status", params.status);
  if (params?.priority) query.append("priority", params.priority);
  if (params?.search) query.append("search", params.search);
  if (params?.skip !== undefined) query.append("skip", params.skip.toString());
  if (params?.limit !== undefined) query.append("limit", params.limit.toString());

  const qs = query.toString();
  return request<Case[]>(`/cases${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export async function getCaseById(id: string): Promise<Case> {
  if (isSupabaseConfigured()) {
    return supabaseGetCaseById(id);
  }
  return request<Case>(`/cases/${id}`, { method: "GET" });
}

export async function createCase(data: CaseCreateRequest): Promise<Case> {
  if (isSupabaseConfigured()) {
    return supabaseCreateCase(data);
  }
  const payload = {
    ...data,
    case_number: data.case_number || `CR-${new Date().getFullYear()}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
  };
  return request<Case>("/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateCase(id: string, data: CaseUpdateRequest): Promise<Case> {
  if (isSupabaseConfigured()) {
    return supabaseUpdateCase(id, data);
  }
  return request<Case>(`/cases/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteCase(id: string): Promise<void> {
  return request<void>(`/cases/${id}`, { method: "DELETE" });
}

export async function listAssignableOfficers(): Promise<User[]> {
  if (isSupabaseConfigured()) {
    return supabaseListAssignableOfficers();
  }
  return request<User[]>("/cases/assignable-officers", { method: "GET" });
}

export async function listCaseMembers(caseId: string): Promise<CaseMember[]> {
  if (isSupabaseConfigured()) {
    return supabaseListCaseMembers(caseId);
  }
  return request<CaseMember[]>(`/cases/${caseId}/members`, { method: "GET" });
}

export async function addCaseMember(
  caseId: string,
  data: CaseMemberAddRequest
): Promise<CaseMember> {
  if (isSupabaseConfigured()) {
    return supabaseAddCaseMember(caseId, data.user_id, data.role_in_case);
  }
  return request<CaseMember>(`/cases/${caseId}/members`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function removeCaseMember(caseId: string, userId: string): Promise<void> {
  if (isSupabaseConfigured()) {
    return supabaseRemoveCaseMember(caseId, userId);
  }
  return request<void>(`/cases/${caseId}/members/${userId}`, { method: "DELETE" });
}

export async function getCaseTimeline(
  caseId: string,
  limit?: number
): Promise<CaseTimelineEvent[]> {
  if (isSupabaseConfigured()) {
    return supabaseGetCaseTimeline(caseId);
  }
  const query = limit ? `?limit=${limit}` : "";
  return request<CaseTimelineEvent[]>(`/cases/${caseId}/timeline${query}`, { method: "GET" });
}

// ==========================================
// Phase 3: Audit Trail & Integrity Verification APIs
// ==========================================

export async function listAuditEvents(params?: {
  case_id?: string;
  actor_id?: string;
  resource_type?: string;
  action?: string;
  skip?: number;
  limit?: number;
}): Promise<AuditEvent[]> {
  if (isSupabaseConfigured()) {
    return supabaseListAuditEvents(params);
  }
  const query = new URLSearchParams();
  if (params?.case_id) query.append("case_id", params.case_id);
  if (params?.actor_id) query.append("actor_id", params.actor_id);
  if (params?.resource_type) query.append("resource_type", params.resource_type);
  if (params?.action) query.append("action", params.action);
  if (params?.skip !== undefined) query.append("skip", params.skip.toString());
  if (params?.limit !== undefined) query.append("limit", params.limit.toString());

  const qs = query.toString();
  return request<AuditEvent[]>(`/audit/events${qs ? `?${qs}` : ""}`, { method: "GET" });
}

export async function verifyAuditChain(limit?: number): Promise<AuditVerificationResult> {
  const query = limit ? `?limit=${limit}` : "";
  return request<AuditVerificationResult>(`/admin/audit/verify${query}`, { method: "GET" });
}

// ==========================================
// Phase 4: Secure Document Management APIs
// ==========================================

export async function listCaseDocuments(
  caseId: string,
  params?: { document_type?: string; search?: string }
): Promise<Document[]> {
  if (isSupabaseConfigured()) {
    return supabaseListCaseDocuments(caseId, params);
  }
  const query = new URLSearchParams();
  if (params?.document_type) query.append("document_type", params.document_type);
  if (params?.search) query.append("search", params.search);
  const qs = query.toString();
  return request<Document[]>(`/cases/${caseId}/documents${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
}

export async function uploadDocument(
  caseId: string,
  formData: FormData
): Promise<Document> {
  if (isSupabaseConfigured()) {
    return supabaseUploadDocument(caseId, formData);
  }
  return request<Document>(`/cases/${caseId}/documents`, {
    method: "POST",
    body: formData,
  });
}

export async function getDocument(documentId: string): Promise<Document> {
  if (isSupabaseConfigured()) {
    return supabaseGetDocument(documentId);
  }
  return request<Document>(`/documents/${documentId}`, {
    method: "GET",
  });
}

export async function listDocumentVersions(documentId: string): Promise<DocumentVersion[]> {
  return request<DocumentVersion[]>(`/documents/${documentId}/versions`, {
    method: "GET",
  });
}

export async function uploadDocumentVersion(
  documentId: string,
  formData: FormData
): Promise<Document> {
  return request<Document>(`/documents/${documentId}/versions`, {
    method: "POST",
    body: formData,
  });
}

export async function verifyDocumentIntegrity(
  documentId: string
): Promise<DocumentIntegrityCheckResult> {
  return request<DocumentIntegrityCheckResult>(`/documents/${documentId}/verify`, {
    method: "GET",
  });
}

export async function listAllAccessibleDocuments(params?: {
  case_id?: string;
  document_type?: string;
  search?: string;
  limit?: number;
  skip?: number;
}): Promise<Document[]> {
  if (isSupabaseConfigured()) {
    return supabaseListAllAccessibleDocuments(params);
  }
  const query = new URLSearchParams();
  if (params?.case_id) query.append("case_id", params.case_id);
  if (params?.document_type) query.append("document_type", params.document_type);
  if (params?.search) query.append("search", params.search);
  if (params?.limit !== undefined) query.append("limit", params.limit.toString());
  if (params?.skip !== undefined) query.append("skip", params.skip.toString());
  const qs = query.toString();
  return request<Document[]>(`/documents${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
}

export async function downloadDocument(
  documentId: string,
  versionId?: string
): Promise<{ blob: Blob; filename: string }> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const endpoint = versionId
    ? `/documents/${documentId}/versions/${versionId}/download`
    : `/documents/${documentId}/download`;

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "GET",
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Session required. Please sign in to access protected records.");
    }
    let errorDetail = "Failed to download document";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      errorDetail = `Download failed with status ${response.status}`;
    }
    throw new Error(errorDetail);
  }

  let filename = "document";
  const disposition = response.headers.get("Content-Disposition");
  if (disposition && disposition.includes("filename=")) {
    const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
    if (matches != null && matches[1]) {
      filename = matches[1].replace(/['"]/g, "");
    }
  }

  const blob = await response.blob();
  return { blob, filename };
}

export function saveBlobAsFile(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// ==========================================
// Phase 5: Evidence & Chain of Custody APIs
// ==========================================

export async function listCaseEvidence(
  caseId: string,
  params?: {
    evidence_type?: string;
    status?: string;
    sensitivity_level?: string;
    search?: string;
  }
): Promise<Evidence[]> {
  if (isSupabaseConfigured()) {
    return supabaseListCaseEvidence(caseId, params);
  }
  const query = new URLSearchParams();
  if (params?.evidence_type) query.append("evidence_type", params.evidence_type);
  if (params?.status) query.append("status", params.status);
  if (params?.sensitivity_level) query.append("sensitivity_level", params.sensitivity_level);
  if (params?.search) query.append("search", params.search);

  const qs = query.toString();
  return request<Evidence[]>(`/cases/${caseId}/evidence${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
}

export async function listAllAccessibleEvidence(params?: {
  evidence_type?: string;
  status?: string;
  sensitivity_level?: string;
  search?: string;
}): Promise<Evidence[]> {
  if (isSupabaseConfigured()) {
    return supabaseListAllAccessibleEvidence(params);
  }
  const query = new URLSearchParams();
  if (params?.evidence_type) query.append("evidence_type", params.evidence_type);
  if (params?.status) query.append("status", params.status);
  if (params?.sensitivity_level) query.append("sensitivity_level", params.sensitivity_level);
  if (params?.search) query.append("search", params.search);

  const qs = query.toString();
  return request<Evidence[]>(`/evidence${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
}

export async function getEvidenceById(evidenceId: string): Promise<Evidence> {
  if (isSupabaseConfigured()) {
    return supabaseGetEvidenceById(evidenceId);
  }
  return request<Evidence>(`/evidence/${evidenceId}`, {
    method: "GET",
  });
}

export async function registerEvidence(
  caseId: string,
  data: EvidenceRegisterRequest
): Promise<Evidence> {
  if (isSupabaseConfigured()) {
    return supabaseRegisterEvidence(caseId, data);
  }
  return request<Evidence>(`/cases/${caseId}/evidence`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateEvidence(
  evidenceId: string,
  data: EvidenceUpdateRequest
): Promise<Evidence> {
  if (isSupabaseConfigured()) {
    return supabaseUpdateEvidence(evidenceId, data);
  }
  return request<Evidence>(`/evidence/${evidenceId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function initiateCustodyTransfer(
  evidenceId: string,
  data: EvidenceCustodyTransferRequest
): Promise<Evidence> {
  if (isSupabaseConfigured()) {
    return supabaseInitiateCustodyTransfer(evidenceId, data);
  }
  return request<Evidence>(`/evidence/${evidenceId}/custody/transfer`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function acknowledgeCustodyTransfer(
  evidenceId: string,
  data: EvidenceCustodyAcknowledgeRequest
): Promise<Evidence> {
  if (isSupabaseConfigured()) {
    return supabaseAcknowledgeCustodyTransfer(evidenceId, data);
  }
  return request<Evidence>(`/evidence/${evidenceId}/custody/acknowledge`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function cancelCustodyTransfer(evidenceId: string): Promise<Evidence> {
  if (isSupabaseConfigured()) {
    return supabaseCancelCustodyTransfer(evidenceId);
  }
  return request<Evidence>(`/evidence/${evidenceId}/custody/cancel`, {
    method: "POST",
  });
}

export async function transitionEvidenceStatus(
  evidenceId: string,
  data: EvidenceStatusTransitionRequest
): Promise<Evidence> {
  if (isSupabaseConfigured()) {
    return supabaseTransitionEvidenceStatus(evidenceId, data);
  }
  return request<Evidence>(`/evidence/${evidenceId}/status`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listEvidenceCustodyHistory(
  evidenceId: string
): Promise<EvidenceCustodyEvent[]> {
  if (isSupabaseConfigured()) {
    return supabaseListEvidenceCustodyHistory(evidenceId);
  }
  return request<EvidenceCustodyEvent[]>(`/evidence/${evidenceId}/custody`, {
    method: "GET",
  });
}

export async function verifyEvidenceCustodyChain(
  evidenceId: string
): Promise<CustodyChainVerificationResult> {
  if (isSupabaseConfigured()) {
    return supabaseVerifyCustodyChain(evidenceId);
  }
  return request<CustodyChainVerificationResult>(`/evidence/${evidenceId}/custody/verify`, {
    method: "GET",
  });
}

export async function verifyEvidenceDigitalIntegrity(
  evidenceId: string
): Promise<EvidenceIntegrityResult> {
  if (isSupabaseConfigured()) {
    return supabaseVerifyEvidenceDigitalIntegrity(evidenceId);
  }
  return request<EvidenceIntegrityResult>(`/evidence/${evidenceId}/verify`, {
    method: "GET",
  });
}

// ==========================================
// Phase 6: AI Document Intelligence & RAG
// ==========================================

export async function getDocumentAIInsights(documentId: string): Promise<DocumentAIInsights> {
  return request<DocumentAIInsights>(`/documents/${documentId}/ai`, {
    method: "GET",
  });
}

export async function processDocumentAI(documentId: string): Promise<DocumentAIInsights> {
  return request<DocumentAIInsights>(`/documents/${documentId}/ai/process`, {
    method: "POST",
  });
}

export async function verifyExtractedEntity(
  documentId: string,
  entityId: string,
  verified: boolean
): Promise<ExtractedEntity> {
  return request<ExtractedEntity>(`/documents/${documentId}/entities/${entityId}/verify`, {
    method: "PATCH",
    body: JSON.stringify({ verified }),
  });
}

export async function semanticSearchCase(
  caseId: string,
  query: string,
  topK: number = 10,
  minSimilarity: number = 0.3
): Promise<SemanticSearchResponse> {
  return request<SemanticSearchResponse>(`/cases/${caseId}/ai/search`, {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK, min_similarity: minSimilarity }),
  });
}

export async function askCaseAssistant(
  caseId: string,
  question: string,
  topK: number = 5
): Promise<RAGAnswerResponse> {
  return request<RAGAnswerResponse>(`/cases/${caseId}/ai/ask`, {
    method: "POST",
    body: JSON.stringify({ question, top_k: topK }),
  });
}

// ==========================================
// Phase 7: Semantic Search, pgvector & RAG
// ==========================================

export async function searchSemantic(params: {
  query: string;
  case_id?: string;
  document_type?: string;
  limit?: number;
  threshold?: number;
}): Promise<SearchResponse> {
  return request<SearchResponse>("/search/semantic", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function searchHybrid(params: {
  query: string;
  case_id?: string;
  document_type?: string;
  limit?: number;
  semantic_weight?: number;
  keyword_weight?: number;
}): Promise<SearchResponse> {
  return request<SearchResponse>("/search/hybrid", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function searchKeyword(params: {
  query: string;
  case_id?: string;
  document_type?: string;
  limit?: number;
}): Promise<SearchResponse> {
  return request<SearchResponse>("/search/keyword", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function searchAsk(params: {
  question: string;
  case_id?: string;
  limit?: number;
  temperature?: number;
}): Promise<SearchAskResponse> {
  return request<SearchAskResponse>("/search/ask", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getSearchStatus(): Promise<SearchStatusResponse> {
  return request<SearchStatusResponse>("/search/status", {
    method: "GET",
  });
}

// ==========================================
// Phase 8: Legal Export APIs
// ==========================================

export async function createCaseExport(
  caseId: string,
  data: ExportCreateRequest = {}
): Promise<CaseExport> {
  return request<CaseExport>(`/cases/${caseId}/exports`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listCaseExports(
  caseId: string,
  page: number = 1,
  size: number = 20
): Promise<ExportListResponse> {
  return request<ExportListResponse>(`/cases/${caseId}/exports?page=${page}&size=${size}`, {
    method: "GET",
  });
}

export async function getCaseExport(
  caseId: string,
  exportId: string
): Promise<CaseExport> {
  return request<CaseExport>(`/cases/${caseId}/exports/${exportId}`, {
    method: "GET",
  });
}

export async function downloadCaseExport(
  caseId: string,
  exportId: string,
  customFilename?: string
): Promise<{ blob: Blob; filename: string }> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/exports/${exportId}/download`, {
    method: "GET",
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Session required. Please sign in to access protected records.");
    }
    let errorDetail = "Failed to download case export package";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      errorDetail = `Download failed with status ${response.status}`;
    }
    throw new Error(errorDetail);
  }

  let filename = customFilename || `DOCSHIELD_EXPORT_${exportId}.zip`;
  const disposition = response.headers.get("Content-Disposition");
  if (disposition && disposition.includes("filename=")) {
    const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
    if (matches != null && matches[1]) {
      filename = matches[1].replace(/['"]/g, "");
    }
  }

  const blob = await response.blob();
  return { blob, filename };
}

// ==========================================
// Phase 8: Security Monitoring & Incident APIs
// ==========================================

export async function getSecurityMetrics(): Promise<SecurityMetrics> {
  if (isSupabaseConfigured()) {
    return supabaseGetSecurityMetrics();
  }
  return request<SecurityMetrics>("/security/metrics", {
    method: "GET",
  });
}

export async function listSecurityEvents(params: {
  category?: string;
  severity?: string;
  resolved?: boolean;
  page?: number;
  size?: number;
} = {}): Promise<SecurityEventsListResponse> {
  const query = new URLSearchParams();
  if (params.category) query.append("category", params.category);
  if (params.severity) query.append("severity", params.severity);
  if (params.resolved !== undefined) query.append("resolved", String(params.resolved));
  if (params.page) query.append("page", String(params.page));
  if (params.size) query.append("size", String(params.size));

  const qs = query.toString();
  return request<SecurityEventsListResponse>(`/security/events${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
}

export async function resolveSecurityEvent(
  eventId: string,
  resolutionNotes: string
): Promise<SecurityEvent> {
  return request<SecurityEvent>(`/security/events/${eventId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution_notes: resolutionNotes }),
  });
}

export async function simulateTamper(
  data: TamperSimulationRequest
): Promise<TamperSimulationResponse> {
  return request<TamperSimulationResponse>("/security/tamper-simulate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}





