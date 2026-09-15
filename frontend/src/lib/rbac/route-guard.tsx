"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Permission } from "./types";
import { AccessDenied } from "./guards";
import { LoadingSpinner } from "@/components/ui/loading-spinner";

interface RouteGuardProps {
  children: React.ReactNode;
}

/**
 * RouteGuard intercepts client-side navigation to protected routes.
 * Enforces strict default-deny authorization on /settings and /security.
 * Prevents unauthorized rendering or flashing of confidential components.
 */
export function RouteGuard({ children }: RouteGuardProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isLoading, isAuthenticated, hasRole, hasPermission } = useAuth();

  // If loading auth state, show a clean loader
  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <LoadingSpinner size="lg" />
        <p className="text-xs text-slate-500 font-mono">Verifying Zero-Trust Session Clearance...</p>
      </div>
    );
  }

  // Not authenticated
  if (!isAuthenticated || !user) {
    return (
      <AccessDenied
        title="Session Authentication Required"
        message="Your security session has expired or is unauthenticated. Please sign in with valid government credentials to proceed."
        returnUrl="/login"
      />
    );
  }

  // /settings route protection: Admin only
  if (pathname === "/settings" || pathname.startsWith("/settings/")) {
    const isAllowed = hasRole("Admin") || hasPermission(Permission.SYSTEM_SETTINGS);
    if (!isAllowed) {
      return (
        <AccessDenied
          title="System Settings Restricted • 403 Forbidden"
          message="User administration, cryptographic ledger management, and system settings are strictly restricted to System Administrators."
          requiredRole="Admin"
        />
      );
    }
  }

  // /security route protection: Admin only
  if (pathname === "/security" || pathname.startsWith("/security/")) {
    const isAllowed = hasRole("Admin") || hasPermission(Permission.AUDIT_VIEW);
    if (!isAllowed) {
      return (
        <AccessDenied
          title="Security Center Restricted • 403 Forbidden"
          message="National security event logs and system threat telemetry are restricted strictly to System Administrators."
          requiredRole="Admin"
        />
      );
    }
  }

  return <>{children}</>;
}
