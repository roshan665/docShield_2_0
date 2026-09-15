"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { User, LoginRequest, Case, Evidence, CaseMember } from "@/types";
import {
  getCurrentUser,
  getStoredToken,
  login as apiLogin,
  logout as apiLogout,
  refreshToken as apiRefreshToken,
  removeStoredToken,
} from "./api";
import {
  AppRole,
  Permission,
  ResourceContext,
  normalizeRole,
  hasRole as rbacHasRole,
  hasPermission as rbacHasPermission,
  canAccessCase as rbacCanAccessCase,
  canAccessEvidence as rbacCanAccessEvidence,
  canPerformAction as rbacCanPerformAction,
} from "./rbac";
import { ROLE_PERMISSIONS } from "./rbac/matrix";

interface AuthContextType {
  user: User | null;
  appRole: AppRole | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (roles: AppRole | AppRole[] | string | string[]) => boolean;
  hasPermission: (permission: Permission | string) => boolean;
  canAccessCase: (caseItem: Case | null | undefined, members?: CaseMember[] | null) => boolean;
  canAccessEvidence: (caseItem?: Case | null, evidenceItem?: Evidence | null) => boolean;
  canPerformAction: (action: Permission, context?: ResourceContext) => boolean;
  refreshUserProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  const enrichUser = useCallback((rawUser: User | null): User | null => {
    if (!rawUser) return null;
    let app_role = normalizeRole(rawUser.role);
    if (!app_role && rawUser.email) {
      const lower = rawUser.email.toLowerCase();
      if (lower.includes("admin")) app_role = "Admin";
      else if (lower.includes("advocate") || lower.includes("legal")) app_role = "Advocate";
      else if (lower.includes("officer") || lower.includes("investigator")) app_role = "Officer";
    }
    const rbacPerms = app_role ? Array.from(ROLE_PERMISSIONS[app_role] || []).map((p) => p.toString()) : [];
    return {
      ...rawUser,
      role: app_role || rawUser.role,
      app_role: app_role || undefined,
      permissions: Array.from(new Set([...(rawUser.permissions || []), ...rbacPerms])),
    };
  }, []);

  const refreshUserProfile = useCallback(async () => {
    try {
      const currentUser = await getCurrentUser();
      setUser(enrichUser(currentUser));
    } catch {
      // If token expired, try silent refresh
      try {
        await apiRefreshToken();
        const currentUser = await getCurrentUser();
        setUser(enrichUser(currentUser));
      } catch {
        removeStoredToken();
        setUser(null);
      }
    }
  }, [enrichUser]);

  useEffect(() => {
    const initAuth = async () => {
      const token = getStoredToken();
      if (token) {
        await refreshUserProfile();
      }
      setIsLoading(false);
    };
    initAuth();
  }, [refreshUserProfile]);

  const login = async (credentials: LoginRequest) => {
    setIsLoading(true);
    try {
      const res = await apiLogin(credentials);
      setUser(enrichUser(res.user));
      router.push("/dashboard");
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiLogout();
    } catch {
      // Ignore errors on logout
    } finally {
      setUser(null);
      setIsLoading(false);
      router.push("/login");
    }
  };

  const appRole = useMemo<AppRole | null>(() => {
    return normalizeRole(user?.role);
  }, [user?.role]);

  const hasRole = useCallback(
    (roles: AppRole | AppRole[] | string | string[]): boolean => {
      if (!user) return false;
      const roleList = Array.isArray(roles) ? roles : [roles];
      // Check canonical AppRole match first
      const normalizedTargets = roleList
        .map((r) => normalizeRole(r))
        .filter((r): r is AppRole => r !== null);

      if (normalizedTargets.length > 0 && rbacHasRole(user, normalizedTargets)) {
        return true;
      }
      // Backward compatibility for raw role check
      return roleList.includes(user.role);
    },
    [user]
  );

  const hasPermission = useCallback(
    (permission: Permission | string): boolean => {
      return rbacHasPermission(user, permission);
    },
    [user]
  );

  const canAccessCase = useCallback(
    (caseItem: Case | null | undefined, members?: CaseMember[] | null): boolean => {
      return rbacCanAccessCase(user, caseItem, members);
    },
    [user]
  );

  const canAccessEvidence = useCallback(
    (caseItem?: Case | null, evidenceItem?: Evidence | null): boolean => {
      return rbacCanAccessEvidence(user, caseItem, evidenceItem);
    },
    [user]
  );

  const canPerformAction = useCallback(
    (action: Permission, context?: ResourceContext): boolean => {
      return rbacCanPerformAction(user, action, context);
    },
    [user]
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        appRole,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        hasRole,
        hasPermission,
        canAccessCase,
        canAccessEvidence,
        canPerformAction,
        refreshUserProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
