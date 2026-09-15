/**
 * DocShield Centralized Authorization Engine
 * Enforces a strict default-deny model across roles, permissions, and resource scopes.
 */

import { User, Case, Evidence, CaseMember } from "@/types";
import { AppRole, Permission, ResourceContext } from "./types";
import { ROLE_PERMISSIONS } from "./matrix";

/**
 * Normalizes any database/token role string into one of the 3 canonical AppRole values.
 * Returns null if the role is missing, inactive, or unknown (default-deny).
 */
export function normalizeRole(role?: string | null): AppRole | null {
  if (!role) return null;
  const cleaned = role.toLowerCase().trim();

  // Admin mapping
  if (cleaned === "admin" || cleaned === "system_admin") {
    return "Admin";
  }

  // Officer mapping
  if (
    cleaned === "officer" ||
    cleaned === "investigator" ||
    cleaned === "supervisor" ||
    cleaned === "forensic_expert"
  ) {
    return "Officer";
  }

  // Advocate mapping
  if (
    cleaned === "advocate" ||
    cleaned === "legal_officer" ||
    cleaned === "judge_viewer"
  ) {
    return "Advocate";
  }

  return null;
}

/**
 * Check if the user possesses one of the specified canonical roles.
 * Always returns false if the user is unauthenticated or has an unknown role.
 */
export function hasRole(
  user: User | null | undefined,
  roles: AppRole | AppRole[]
): boolean {
  if (!user || !user.is_active || user.is_locked) return false;
  const currentAppRole = normalizeRole(user.role);
  if (!currentAppRole) return false;

  const allowedRoles = Array.isArray(roles) ? roles : [roles];
  return allowedRoles.includes(currentAppRole);
}

/**
 * Check if the user possesses a specific permission based on the central permission matrix.
 * Enforces a strict default-deny model.
 */
export function hasPermission(
  user: User | null | undefined,
  permission: Permission | string
): boolean {
  if (!user || !user.is_active || user.is_locked) return false;
  const currentAppRole = normalizeRole(user.role);
  if (!currentAppRole) return false;

  const allowedPermissions = ROLE_PERMISSIONS[currentAppRole];
  if (!allowedPermissions) return false;

  return allowedPermissions.has(permission as Permission);
}

/**
 * Resource-Level Check: Can the user access a specific Case?
 *
 * Rules:
 * - Admin: Full access to all cases.
 * - Officer: Access if lead officer, investigating officer, created by user, or listed in case_members.
 * - Advocate: Access ONLY if explicitly listed as an active case member (e.g. legal_counsel).
 * - Default: Deny.
 */
export function canAccessCase(
  user: User | null | undefined,
  caseItem: Case | null | undefined,
  members?: CaseMember[] | null
): boolean {
  if (!user || !caseItem || !user.is_active || user.is_locked) return false;
  const currentAppRole = normalizeRole(user.role);
  if (!currentAppRole) return false;

  // Admin has global case access
  if (currentAppRole === "Admin") {
    return true;
  }

  // Check direct lead/investigating officer ownership
  const isLead =
    caseItem.investigating_officer_id === user.id ||
    caseItem.created_by === user.id ||
    caseItem.lead_officer_id === user.id;

  if (currentAppRole === "Officer" && isLead) {
    return true;
  }

  // Check explicit case membership
  const memberList = members || caseItem.members;
  if (memberList && memberList.length > 0) {
    const isMember = memberList.some(
      (m) => (m.user_id === user.id || m.email === user.email) && m.is_active !== false
    );
    if (isMember) return true;
  }

  // If case was returned from user-scoped backend query (where case.user_role_in_case is populated)
  if (caseItem.user_role_in_case) {
    return true;
  }

  return false;
}

/**
 * Resource-Level Check: Can the user access a specific Evidence item?
 * Follows case boundaries and sensitivity constraints.
 */
export function canAccessEvidence(
  user: User | null | undefined,
  caseItem?: Case | null,
  evidenceItem?: Evidence | null
): boolean {
  if (!user || !user.is_active || user.is_locked) return false;
  const currentAppRole = normalizeRole(user.role);
  if (!currentAppRole) return false;

  // Must have EVIDENCE_VIEW permission
  if (!hasPermission(user, Permission.EVIDENCE_VIEW)) return false;

  // If a case context is provided, user must have access to the parent case
  if (caseItem && !canAccessCase(user, caseItem)) {
    return false;
  }

  // Advocate restrictions on classified evidence
  if (currentAppRole === "Advocate" && evidenceItem) {
    // If evidence is marked confidential, secret, or classified without court clearance
    if (
      (evidenceItem.sensitivity_level === "confidential" ||
        evidenceItem.sensitivity_level === "secret" ||
        evidenceItem.sensitivity_level === "classified") &&
      !caseItem?.user_role_in_case
    ) {
      return false;
    }
  }

  return true;
}

/**
 * Action-Level Enforcement: Checks whether an action can be performed by the user,
 * validating both permission matrix and contextual resource boundaries.
 * Throws or returns boolean for programmatic safety.
 */
export function canPerformAction(
  user: User | null | undefined,
  action: Permission,
  context?: ResourceContext
): boolean {
  // 1. Base permission check
  if (!hasPermission(user, action)) {
    return false;
  }

  const currentAppRole = normalizeRole(user?.role);
  if (!currentAppRole) return false;

  // 2. Resource-specific checks
  switch (action) {
    case Permission.CASE_CREATE:
      // Advocate cannot register new cases
      return currentAppRole === "Admin" || currentAppRole === "Officer";

    case Permission.CASE_ASSIGN:
      // Advocate cannot assign officers
      if (currentAppRole === "Advocate") return false;
      if (context?.caseItem && !canAccessCase(user, context.caseItem, context.caseMembers)) {
        return false;
      }
      return true;

    case Permission.CASE_STATUS_UPDATE:
    case Permission.CASE_UPDATE:
      // Advocate cannot modify investigation status or investigation data
      if (currentAppRole === "Advocate") return false;
      if (context?.caseItem && !canAccessCase(user, context.caseItem, context.caseMembers)) {
        return false;
      }
      return true;

    case Permission.EVIDENCE_UPLOAD:
    case Permission.EVIDENCE_VERIFY:
      // Advocate cannot upload or verify evidence
      if (currentAppRole === "Advocate") return false;
      if (context?.caseItem && !canAccessCase(user, context.caseItem, context.caseMembers)) {
        return false;
      }
      return true;

    case Permission.LEGAL_DOCUMENT_UPLOAD:
      // Advocate and Admin and Officer can upload legal documents
      if (context?.caseItem && !canAccessCase(user, context.caseItem, context.caseMembers)) {
        return false;
      }
      return true;

    case Permission.USER_MANAGE:
    case Permission.ROLE_MANAGE:
    case Permission.AUDIT_VIEW:
    case Permission.SYSTEM_SETTINGS:
      // Only Admin can perform system management
      return currentAppRole === "Admin";

    default:
      return true;
  }
}
