"use client";

import React from "react";
import Link from "next/link";
import { ShieldAlert, Lock, ArrowLeft, AlertCircle } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { AppRole, Permission, ResourceContext } from "./types";
import { hasRole, hasPermission, canPerformAction } from "./authorization";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface PermissionGuardProps {
  permission: Permission | string;
  context?: ResourceContext;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Conditionally renders children only if the authenticated user has the required permission.
 * Completely removes unauthorized elements from the DOM if unauthorized.
 */
export function PermissionGuard({
  permission,
  context,
  fallback = null,
  children,
}: PermissionGuardProps) {
  const { user } = useAuth();

  const isAllowed = context
    ? canPerformAction(user, permission as Permission, context)
    : hasPermission(user, permission);

  if (!isAllowed) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

interface RoleGuardProps {
  roles: AppRole | AppRole[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Conditionally renders children only if the user matches one of the specified canonical AppRoles.
 */
export function RoleGuard({
  roles,
  fallback = <AccessDenied />,
  children,
}: RoleGuardProps) {
  const { user } = useAuth();

  if (!hasRole(user, roles)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

interface AccessDeniedProps {
  title?: string;
  message?: string;
  requiredRole?: string;
  returnUrl?: string;
}

/**
 * Government-Grade 403 Forbidden Screen for unauthorized routes and access attempts.
 */
export function AccessDenied({
  title = "Access Restricted • 403 Forbidden",
  message = "You do not possess the required official role or authorization level to access this secure resource.",
  requiredRole,
  returnUrl = "/dashboard",
}: AccessDeniedProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400 border border-rose-200 dark:border-rose-900/50 shadow-lg">
        <ShieldAlert className="h-8 w-8" />
      </div>

      <div className="mt-4 flex items-center justify-center">
        <Badge
          variant="outline"
          className="gap-1.5 border-rose-300 bg-rose-50/80 text-rose-900 font-mono text-[10px] uppercase font-semibold dark:border-rose-900/60 dark:bg-rose-950/60 dark:text-rose-200"
        >
          <Lock className="h-2.5 w-2.5" /> ZERO-TRUST ACCESS VIOLATION
        </Badge>
      </div>

      <h2 className="mt-3 text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 font-sans">
        {title}
      </h2>

      <p className="mt-2 max-w-md text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
        {message}
      </p>

      {requiredRole && (
        <div className="mt-3 flex items-center gap-1.5 text-[11px] text-amber-700 dark:text-amber-400 font-medium">
          <AlertCircle className="h-3.5 w-3.5" />
          <span>Requires: <strong className="font-mono">{requiredRole}</strong> clearance</span>
        </div>
      )}

      <div className="mt-6 flex items-center gap-3">
        <Link href={returnUrl}>
          <Button
            size="sm"
            className="h-9 gap-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-sm"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Return to Authorized Dashboard
          </Button>
        </Link>
      </div>

      <div className="mt-8 border-t border-slate-200 dark:border-slate-800/80 pt-3 text-[10px] font-mono text-slate-400">
        NCRB &bull; MHA INDIA &bull; SEC-65B BSA &bull; AUDIT REF: 403-RBAC-DENIED
      </div>
    </div>
  );
}

