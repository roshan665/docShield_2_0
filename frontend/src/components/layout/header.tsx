"use client";

import Link from "next/link";
import { Bell, Lock, UserCheck, LogOut, LogIn } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { getRoleLabel } from "./sidebar";

export function Header() {
  const { user, logout, isAuthenticated } = useAuth();

  return (
    <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-6 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 shadow-sm">
      {/* Left Government Identity */}
      <div className="flex items-center gap-3">
        <Badge
          variant="outline"
          className="gap-1.5 border-blue-300 bg-blue-50/80 text-blue-900 font-mono text-[11px] font-semibold uppercase tracking-wider dark:border-blue-900/60 dark:bg-blue-950/60 dark:text-blue-200"
        >
          <Lock className="h-3 w-3 text-blue-700 dark:text-blue-300" /> OFFICIAL USE ONLY
        </Badge>
        <div className="h-4 w-px bg-slate-200 dark:bg-slate-800 hidden sm:block" />
        <span className="text-xs text-slate-600 dark:text-slate-400 font-medium hidden sm:inline tracking-tight">
          NCRB &bull; MHA INDIA &bull; National Digital Evidence Platform
        </span>
      </div>

      {/* Right User & Security Status */}
      <div className="flex items-center gap-3.5">
        {/* Security Session Indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium transition-colors bg-slate-50 dark:bg-slate-900/80 border-slate-200 dark:border-slate-800">
          {isAuthenticated ? (
            <>
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-emerald-700 dark:text-emerald-400 font-semibold">Secure Session</span>
            </>
          ) : (
            <>
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              <span className="text-amber-700 dark:text-amber-400 font-semibold">Session Required</span>
            </>
          )}
        </div>

        {/* Notifications */}
        <button
          aria-label="Notifications"
          className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
          title="System Notifications"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 flex h-2 w-2 rounded-full bg-blue-600 ring-2 ring-white dark:ring-slate-900" />
        </button>

        {/* User Identity / Login CTA */}
        {isAuthenticated && user ? (
          <div className="flex items-center gap-3 border-l border-slate-200 pl-3 dark:border-slate-800">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                {user.full_name}
              </p>
              <div className="flex items-center justify-end gap-1.5">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">
                  {user.employee_id}
                </span>
                <span className="text-[10px] text-slate-300 dark:text-slate-700">&bull;</span>
                <span className="text-[10px] font-medium text-blue-600 dark:text-blue-400">
                  {getRoleLabel(user.role, user.role_display_name)}
                </span>
              </div>
            </div>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200 dark:border-blue-900/50 shadow-sm font-semibold text-xs">
              <UserCheck className="h-4 w-4" />
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => logout()}
              className="h-8 w-8 p-0 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 dark:hover:text-rose-300"
              title="Sign Out / Revoke Session"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2 border-l border-slate-200 pl-3 dark:border-slate-800">
            <Link href="/login">
              <Button size="sm" className="bg-blue-600 hover:bg-blue-500 text-white h-8 text-xs gap-1.5 font-medium shadow-sm">
                <LogIn className="h-3.5 w-3.5" /> Sign In
              </Button>
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
