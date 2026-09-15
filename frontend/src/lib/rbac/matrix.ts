/**
 * DocShield Role Permission Matrix
 * Maps canonical application roles to their allowed granular permissions.
 */

import { AppRole, Permission } from "./types";

/**
 * Complete Permission Matrix:
 *
 * ADMIN:
 * - Full dashboard access, view all cases, register new cases, view/edit all case details
 * - Assign/reassign officers, update case status, upload/view/download/verify evidence
 * - Add case notes, view/manage legal documents, generate reports, close/reopen cases
 * - Manage users, create users, change user roles, disable/enable users, view audit logs, system settings
 *
 * OFFICER:
 * - View officer dashboard, view assigned/authorized cases, register new cases
 * - View case details, edit case details only where authorized, assign/reassign cases if authorized
 * - Update investigation/case status, upload evidence, view/download authorized evidence
 * - Verify evidence, add investigation notes, generate case reports, view authorized legal documents
 * - Cannot manage users, cannot change roles, cannot access system settings, cannot access unauthorized cases
 *
 * ADVOCATE:
 * - View advocate dashboard, view only authorized cases, view permitted case details
 * - View permitted evidence, download permitted evidence, view legal documents, upload legal documents
 * - Add legal notes
 * - Cannot register new cases, cannot assign/reassign officers, cannot modify investigation status
 * - Cannot modify investigation data, cannot verify evidence, cannot manage users, cannot change roles
 * - Cannot access system settings, cannot access unauthorized cases/evidence/documents
 */
export const ROLE_PERMISSIONS: Record<AppRole, Set<Permission>> = {
  Admin: new Set<Permission>([
    // Case Management
    Permission.CASE_VIEW,
    Permission.CASE_CREATE,
    Permission.CASE_UPDATE,
    Permission.CASE_ASSIGN,
    Permission.CASE_STATUS_UPDATE,
    Permission.CASE_CLOSE,

    // Evidence Management
    Permission.EVIDENCE_VIEW,
    Permission.EVIDENCE_UPLOAD,
    Permission.EVIDENCE_DOWNLOAD,
    Permission.EVIDENCE_VERIFY,

    // Legal Documents & Notes
    Permission.LEGAL_DOCUMENT_VIEW,
    Permission.LEGAL_DOCUMENT_UPLOAD,
    Permission.CASE_NOTES_CREATE,

    // Reports
    Permission.REPORT_GENERATE,

    // Administration
    Permission.USER_MANAGE,
    Permission.ROLE_MANAGE,
    Permission.AUDIT_VIEW,
    Permission.SYSTEM_SETTINGS,
  ]),

  Officer: new Set<Permission>([
    // Case Management
    Permission.CASE_VIEW,
    Permission.CASE_CREATE,
    Permission.CASE_UPDATE,
    Permission.CASE_ASSIGN,
    Permission.CASE_STATUS_UPDATE,

    // Evidence Management
    Permission.EVIDENCE_VIEW,
    Permission.EVIDENCE_UPLOAD,
    Permission.EVIDENCE_DOWNLOAD,
    Permission.EVIDENCE_VERIFY,

    // Legal Documents & Notes
    Permission.LEGAL_DOCUMENT_VIEW,
    Permission.CASE_NOTES_CREATE,

    // Reports
    Permission.REPORT_GENERATE,
  ]),

  Advocate: new Set<Permission>([
    // Permitted Cases (view only for authorized cases)
    Permission.CASE_VIEW,

    // Permitted Evidence (view and download only)
    Permission.EVIDENCE_VIEW,
    Permission.EVIDENCE_DOWNLOAD,

    // Legal Documents (view, upload legal docs, add legal notes)
    Permission.LEGAL_DOCUMENT_VIEW,
    Permission.LEGAL_DOCUMENT_UPLOAD,
    Permission.CASE_NOTES_CREATE,
  ]),
};

/**
 * Helper to test if a given role has a specific permission in the matrix.
 */
export function roleHasPermission(role: AppRole, permission: Permission): boolean {
  const permissions = ROLE_PERMISSIONS[role];
  if (!permissions) return false;
  return permissions.has(permission);
}

