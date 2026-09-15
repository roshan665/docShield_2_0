export type AppRole = "Admin" | "Officer" | "Advocate";

export type UserRole =
  | "investigator"
  | "forensic_expert"
  | "legal_officer"
  | "supervisor"
  | "system_admin"
  | "admin"
  | "officer"
  | "advocate"
  | AppRole;

export interface User {
  id: string;
  employee_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  app_role?: AppRole;
  role_display_name?: string;
  department?: string | null;
  designation?: string | null;
  phone?: string | null;
  is_active: boolean;
  is_locked: boolean;
  last_login?: string | null;
  created_at?: string;
  permissions?: string[];
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface UserCreateRequest {
  employee_id: string;
  email: string;
  full_name: string;
  password: string;
  role_name?: UserRole;
  role_id?: string;
  phone?: string;
  department?: string;
  designation?: string;
  is_active?: boolean;
}

export interface UserUpdateRequest {
  full_name?: string;
  phone?: string;
  department?: string;
  designation?: string;
  role_name?: UserRole;
}

export interface RoleResponse {
  id: string;
  name: string;
  display_name: string;
  description: string;
  is_system_role: boolean;
  permissions: string[];
}

export interface PermissionResponse {
  id: string;
  resource: string;
  action: string;
  description: string;
}

export interface ApiResponse<T> {
  data?: T;
  detail?: string;
  error_code?: string;
  timestamp?: string;
}

export interface SystemHealth {
  status: string;
  timestamp: string;
  environment: string;
  version: string;
}

// ==========================================
// Phase 3: Case Management & Audit Types
// ==========================================

export type CaseStatus =
  | "open"
  | "under_investigation"
  | "pending_review"
  | "pending_legal"
  | "closed"
  | "archived";

export type CasePriority = "critical" | "high" | "medium" | "low";

export type CaseMemberRole =
  | "lead_investigator"
  | "investigator"
  | "forensic_analyst"
  | "legal_counsel"
  | "supervisor";

export interface CaseMember {
  id: string;
  user_id: string;
  case_id: string;
  role_in_case: CaseMemberRole;
  full_name?: string;
  email?: string;
  system_role?: string;
  is_active: boolean;
  assigned_at: string;
}

export interface Case {
  id: string;
  case_number: string;
  title: string;
  description?: string | null;
  status: CaseStatus;
  priority: CasePriority;
  incident_date?: string | null;
  fir_number?: string | null;
  police_station?: string | null;
  created_by: string;
  investigating_officer_id?: string | null;
  lead_officer_id?: string | null;
  creator_name?: string;
  investigating_officer_name?: string | null;
  user_role_in_case?: string | null;
  members_count?: number;
  members?: CaseMember[];
  created_at: string;
  updated_at?: string | null;
  closed_at?: string | null;
}

export interface CaseCreateRequest {
  case_number?: string;
  title: string;
  description?: string;
  priority?: CasePriority;
  incident_date?: string;
  fir_number?: string;
  police_station?: string;
  investigating_officer_id?: string;
}

export interface CaseUpdateRequest {
  title?: string;
  description?: string;
  status?: CaseStatus;
  priority?: CasePriority;
  incident_date?: string;
  fir_number?: string;
  police_station?: string;
  investigating_officer_id?: string;
}

export interface CaseMemberAddRequest {
  user_id: string;
  role_in_case: CaseMemberRole;
}

export interface CaseTimelineEvent {
  id: string;
  action: string;
  actor_name: string;
  actor_id?: string | null;
  details: Record<string, unknown>;
  result: string;
  timestamp: string;
  event_hash: string;
}

export interface AuditEvent {
  id: string;
  actor_id?: string | null;
  actor_name: string;
  actor_email?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  case_id?: string | null;
  details: Record<string, unknown>;
  result: string;
  ip_address?: string | null;
  previous_event_hash: string;
  event_hash: string;
  timestamp: string;
}

export interface AuditVerificationResult {
  is_valid: boolean;
  total_events_checked: number;
  genesis_hash?: string | null;
  latest_hash?: string | null;
  tampered_event_id?: string | null;
  detail: string;
  verified_at: string;
}

// ==========================================
// Phase 4: Secure Document Management Types
// ==========================================

export type DocumentType =
  | "fir"
  | "police_report"
  | "witness_statement"
  | "forensic_report"
  | "court_filing"
  | "seizure_memo"
  | "charge_sheet"
  | "medical_report"
  | "identification_doc"
  | "supporting_document"
  | "other";

export type DocumentClassification =
  | "unclassified"
  | "confidential"
  | "restricted"
  | "secret"
  | "top_secret";

export type DocumentStatus = "active" | "archived" | "restricted";

export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  file_name: string;
  storage_path: string;
  file_hash_sha256: string;
  file_size_bytes: number;
  mime_type: string;
  change_reason?: string | null;
  uploaded_by_id: string;
  uploader_name?: string | null;
  created_at: string;
}

export interface Document {
  id: string;
  case_id: string;
  title: string;
  description?: string | null;
  document_type: DocumentType;
  classification: DocumentClassification;
  status: DocumentStatus;
  current_version_id?: string | null;
  file_hash_sha256?: string | null;
  file_size_bytes?: number | null;
  file_name?: string | null;
  mime_type?: string | null;
  uploaded_by_id: string;
  uploader_name?: string | null;
  current_version?: DocumentVersion | null;
  version_count?: number;
  created_at: string;
  updated_at?: string;
  ai_processed?: boolean;
  ai_classification?: string | null;
  ai_confidence?: number | null;
  ocr_text?: string | null;
  summary?: string | null;
  ai_processing_error?: string | null;
}

export interface DocumentIntegrityCheckResult {
  document_id: string;
  version_id: string;
  version_number: number;
  stored_hash: string;
  calculated_hash: string;
  match: boolean;
  integrity_status: "verified" | "compromised";
  checked_at: string;
  file_size_bytes: number;
}

// ----------------------------------------------------
// Phase 5: Evidence & Chain of Custody Types
// ----------------------------------------------------

export type EvidenceType =
  | "digital_document"
  | "image"
  | "video"
  | "audio"
  | "device"
  | "forensic_artifact"
  | "physical_evidence"
  | "other";

export type EvidenceStatus =
  | "registered"
  | "in_custody"
  | "in_analysis"
  | "analyzed"
  | "submitted_to_court"
  | "archived";

export type EvidenceSensitivity =
  | "standard"
  | "sensitive"
  | "highly_sensitive"
  | "confidential"
  | "secret"
  | "classified";

export type EvidenceIntegrityStatus = "verified" | "compromised" | "pending";

export type CustodyEventType =
  | "registered"
  | "transfer_initiated"
  | "transfer_acknowledged"
  | "transfer_cancelled"
  | "in_analysis"
  | "analysis_completed"
  | "analyzed"
  | "submitted_to_court"
  | "archived"
  | "integrity_verified";

export interface EvidenceCustodyEvent {
  id: string;
  evidence_id: string;
  case_id: string;
  event_type: CustodyEventType;
  from_user_id?: string | null;
  to_user_id: string;
  from_user_name?: string | null;
  to_user_name?: string | null;
  reason: string;
  location?: string | null;
  notes?: string | null;
  file_hash_at_event?: string | null;
  previous_event_hash: string;
  event_hash: string;
  acknowledgement_status: "acknowledged" | "pending" | "cancelled";
  acknowledged_at?: string | null;
  event_metadata?: Record<string, unknown>;
  created_at: string;
}

export interface Evidence {
  id: string;
  case_id: string;
  document_id?: string | null;
  evidence_number: string;
  title: string;
  description?: string | null;
  evidence_type: EvidenceType;
  status: EvidenceStatus;
  sensitivity_level: EvidenceSensitivity;
  original_file_hash?: string | null;
  current_file_hash?: string | null;
  integrity_status: EvidenceIntegrityStatus;
  current_custodian_id: string;
  current_custodian_name?: string | null;
  pending_custodian_id?: string | null;
  pending_custodian_name?: string | null;
  transfer_pending: boolean;
  transfer_reason?: string | null;
  storage_key?: string | null;
  storage_bucket?: string | null;
  mime_type?: string | null;
  file_size_bytes?: number | null;
  collection_date?: string | null;
  collection_location?: string | null;
  source?: string | null;
  registered_by_id: string;
  registered_by_name?: string | null;
  custody_events_count?: number;
  created_at: string;
  updated_at?: string | null;
  archived_at?: string | null;
}

export interface EvidenceRegisterRequest {
  title: string;
  description?: string;
  evidence_type: EvidenceType;
  document_id?: string;
  sensitivity_level?: EvidenceSensitivity;
  collection_date?: string;
  collection_location?: string;
  source?: string;
  notes?: string;
}

export interface EvidenceUpdateRequest {
  title?: string;
  description?: string;
  sensitivity_level?: EvidenceSensitivity;
  collection_location?: string;
  source?: string;
}

export interface EvidenceCustodyTransferRequest {
  to_user_id: string;
  reason: string;
  location?: string;
}

export interface EvidenceCustodyAcknowledgeRequest {
  notes?: string;
  location?: string;
}

export interface EvidenceStatusTransitionRequest {
  target_status: EvidenceStatus;
  reason: string;
  location?: string;
  notes?: string;
}

export interface CustodyChainVerificationResult {
  evidence_id: string;
  valid: boolean;
  events_checked: number;
  first_invalid_event?: number | null;
  reason?: string | null;
  genesis_hash?: string | null;
  tip_hash?: string | null;
}

export interface EvidenceIntegrityResult {
  evidence_id: string;
  original_hash?: string | null;
  current_hash?: string | null;
  match: boolean;
  integrity_status: EvidenceIntegrityStatus;
  checked_at: string;
}

// ==========================================
// Phase 6: AI Document Intelligence & RAG
// ==========================================

export interface ExtractedEntity {
  id: string;
  document_id: string;
  entity_type: string;
  entity_value: string;
  confidence?: number | null;
  start_offset?: number | null;
  end_offset?: number | null;
  source: string;
  verified: boolean;
  created_at: string;
}

export interface DocumentMetadataItem {
  id: string;
  document_id: string;
  key: string;
  value: string;
  source: string;
  confidence?: number | null;
  verified_by?: string | null;
  verified_at?: string | null;
  created_at: string;
}

export interface DocumentAIInsights {
  document_id: string;
  ai_processed: boolean;
  ai_classification?: string | null;
  ai_confidence?: number | null;
  summary?: string | null;
  ocr_text?: string | null;
  entities: ExtractedEntity[];
  metadata_entries: DocumentMetadataItem[];
  chunk_count: number;
  ai_processing_error?: string | null;
}

export interface SemanticSearchResultItem {
  document_id: string;
  document_title: string;
  document_type: string;
  chunk_index: number;
  chunk_text: string;
  similarity: number;
}

export interface SemanticSearchResponse {
  case_id: string;
  query: string;
  results_count: number;
  results: SemanticSearchResultItem[];
}

export interface RAGSourceReference {
  document_id: string;
  document_title: string;
  document_type: string;
  chunk_index: number;
  snippet: string;
}

export interface RAGAnswerResponse {
  case_id: string;
  question: string;
  answer: string;
  sources: RAGSourceReference[];
  ai_generated: boolean;
  disclaimer: string;
}
// ==========================================
// Phase 7: Semantic Search, pgvector & RAG
// ==========================================

export type SearchMode = "semantic" | "hybrid" | "keyword";

export interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  case_id: string;
  version_id?: string | null;
  version_number?: number;
  document_title: string;
  document_type: string;
  chunk_index: number;
  chunk_text: string;
  similarity: number;
  rrf_score?: number | null;
  search_type?: string;
  score?: number;
  citation_label?: string;
}

export interface SearchResponse {
  query: string;
  case_id?: string | null;
  search_type: string;
  total_results: number;
  results: SearchResultItem[];
}

export interface CitationItem {
  chunk_id: string;
  document_id: string;
  document_title: string;
  document_type: string;
  version_number: number;
  snippet: string;
}

export interface SearchAskResponse {
  question: string;
  case_id?: string | null;
  answer: string;
  citations: CitationItem[];
  unverified_citations_removed?: number;
  ai_generated?: boolean;
  disclaimer: string;
}

export interface SearchStatusResponse {
  total_embeddings: number;
  searchable_embeddings: number;
  indexed_documents_count: number;
  model_name: string;
  vector_dimensions: number;
}

// ==========================================
// Phase 8: Court Export & Security Monitoring
// ==========================================

export interface ExportManifestFile {
  path: string;
  sha256: string;
  size: number;
}

export interface ExportManifest {
  case_id: string;
  case_number: string;
  export_id: string;
  generated_at: string;
  generated_by: string;
  generated_by_name: string;
  integrity_status: "verified" | "compromised" | "unverified";
  manifest_hash?: string;
  files: ExportManifestFile[];
}

export interface CaseExport {
  id: string;
  case_id: string;
  requested_by_id: string;
  file_name: string;
  file_size_bytes: number;
  file_hash_sha256: string;
  manifest_hash_sha256: string;
  integrity_status: "verified" | "compromised" | "unverified";
  export_status: "pending" | "completed" | "failed";
  verification_summary: Record<string, any>;
  manifest_data?: ExportManifest | null;
  created_at: string;
  updated_at?: string;
}

export interface ExportListResponse {
  items: CaseExport[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ExportCreateRequest {
  include_files?: boolean;
  reason?: string;
}

export type SecurityEventSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type SecurityEventCategory = "AUTHENTICATION" | "AUTHORIZATION" | "INTEGRITY" | "SYSTEM" | "RATE_LIMIT";

export interface SecurityEvent {
  id: string;
  event_type: string;
  severity: SecurityEventSeverity;
  category: SecurityEventCategory;
  actor_id?: string | null;
  case_id?: string | null;
  resource_type?: string | null;
  resource_id?: string | null;
  ip_address?: string | null;
  details?: Record<string, any> | null;
  resolved: boolean;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolution_notes?: string | null;
  timestamp: string;
}

export interface SecurityMetrics {
  total_events: number;
  critical_events: number;
  high_events: number;
  medium_events: number;
  low_events: number;
  unresolved_count: number;
  integrity_compromises: number;
  events_by_category: Record<string, number>;
  recent_threat_detected: boolean;
}

export interface SecurityEventsListResponse {
  items: SecurityEvent[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface SecurityEventResolveRequest {
  resolution_notes: string;
}

export interface TamperSimulationRequest {
  document_version_id: string;
  reason?: string;
}

export interface TamperSimulationResponse {
  status: string;
  message: string;
  version_id: string;
  original_hash: string;
  corrupted_hash: string;
  tampered_at: string;
  security_event_id?: string;
}
