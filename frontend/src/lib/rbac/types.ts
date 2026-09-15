/**
 * DocShield Centralized Role-Based Access Control (RBAC) Types
 * Standard roles, granular permission definitions, and resource context types.
 */

import { Case, Evidence, Document, CaseMember } from "@/types";

/**
 * The 3 canonical application roles defined in the DocShield security architecture:
 * 1. Admin: System administrators, compliance supervisors with complete oversight.
 * 2. Officer: Investigating officers, forensic experts, field personnel.
 * 3. Advocate: Public prosecutors, legal counsels, court officers.
 */
export type AppRole = "Admin" | "Officer" | "Advocate";

/**
 * Granular application permissions representing system actions.
 */
export enum Permission {
  // Case Governance
  CASE_VIEW = "CASE_VIEW",
  CASE_CREATE = "CASE_CREATE",
  CASE_UPDATE = "CASE_UPDATE",
  CASE_ASSIGN = "CASE_ASSIGN",
  CASE_STATUS_UPDATE = "CASE_STATUS_UPDATE",
  CASE_CLOSE = "CASE_CLOSE",

  // Evidence Operations
  EVIDENCE_VIEW = "EVIDENCE_VIEW",
  EVIDENCE_UPLOAD = "EVIDENCE_UPLOAD",
  EVIDENCE_DOWNLOAD = "EVIDENCE_DOWNLOAD",
  EVIDENCE_VERIFY = "EVIDENCE_VERIFY",

  // Legal & Investigation Documents
  LEGAL_DOCUMENT_VIEW = "LEGAL_DOCUMENT_VIEW",
  LEGAL_DOCUMENT_UPLOAD = "LEGAL_DOCUMENT_UPLOAD",
  CASE_NOTES_CREATE = "CASE_NOTES_CREATE",

  // Legal Intelligence & Reports
  REPORT_GENERATE = "REPORT_GENERATE",

  // System & Administration
  USER_MANAGE = "USER_MANAGE",
  ROLE_MANAGE = "ROLE_MANAGE",
  AUDIT_VIEW = "AUDIT_VIEW",
  SYSTEM_SETTINGS = "SYSTEM_SETTINGS",
}

/**
 * Resource context passed to action-level and data-level authorization checks.
 */
export interface ResourceContext {
  caseItem?: Case | null;
  evidenceItem?: Evidence | null;
  documentItem?: Document | null;
  caseMembers?: CaseMember[] | null;
}

