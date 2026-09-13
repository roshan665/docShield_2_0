"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Shield,
  Key,
  UserCheck,
  UserX,
  Lock,
  Unlock,
  RefreshCw,
  PlusCircle,
  AlertCircle,
  CheckCircle2,
  Users,
  Hash,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import {
  changePassword,
  listUsers,
  createUser,
  updateUserStatus,
  adminResetPassword,
  listAuditEvents,
  verifyAuditChain,
} from "@/lib/api";
import { User, UserRole, UserCreateRequest, AuditEvent, AuditVerificationResult } from "@/types";

export default function SettingsPage() {
  const { user, hasRole } = useAuth();

  // Password Change state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null);
  const [pwdError, setPwdError] = useState<string | null>(null);

  // Admin User Management state
  const [usersList, setUsersList] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [adminMsg, setAdminMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // New User Form State
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUserForm, setNewUserForm] = useState<UserCreateRequest>({
    employee_id: "",
    email: "",
    full_name: "",
    password: "",
    role_name: "investigator",
    department: "Crime Investigation",
    designation: "Officer",
  });
  const [creatingUser, setCreatingUser] = useState(false);

  const fetchUsers = useCallback(async () => {
    if (!hasRole("system_admin")) return;
    setUsersLoading(true);
    try {
      const items = await listUsers({ skip: 0, limit: 50 });
      setUsersList(items);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAdminMsg({ type: "error", text: err.message });
      }
    } finally {
      setUsersLoading(false);
    }
  }, [hasRole]);

  // Audit Verification State
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [verificationResult, setVerificationResult] = useState<AuditVerificationResult | null>(null);
  const [verifyingChain, setVerifyingChain] = useState(false);
  const [auditMsg, setAuditMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchAuditData = useCallback(async () => {
    if (!hasRole("system_admin") && !hasRole("supervisor")) return;
    setAuditLoading(true);
    try {
      const events = await listAuditEvents({ limit: 20 });
      setAuditEvents(events);
    } catch {
      // Graceful fallback
    } finally {
      setAuditLoading(false);
    }
  }, [hasRole]);

  useEffect(() => {
    fetchAuditData();
  }, [fetchAuditData]);

  const handleVerifyChain = async () => {
    setVerifyingChain(true);
    setAuditMsg(null);
    try {
      const res = await verifyAuditChain();
      setVerificationResult(res);
      if (res.is_valid) {
        setAuditMsg({
          type: "success",
          text: `Cryptographic audit hash chain fully verified across ${res.total_events_checked} records. Zero tampering detected.`,
        });
      } else {
        setAuditMsg({
          type: "error",
          text: `INTEGRITY VIOLATION DETECTED: Tampered event ID: ${res.tampered_event_id}. ${res.detail}`,
        });
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAuditMsg({ type: "error", text: `Verification failed: ${err.message}` });
      }
    } finally {
      setVerifyingChain(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdSuccess(null);
    setPwdError(null);

    if (newPassword !== confirmPassword) {
      setPwdError("New passwords do not match.");
      return;
    }

    if (newPassword.length < 8) {
      setPwdError("New password must be at least 8 characters long.");
      return;
    }

    setPwdLoading(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPwdSuccess("Password updated successfully. Active sessions revoked.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setPwdError(err.message);
      } else {
        setPwdError("Failed to update password.");
      }
    } finally {
      setPwdLoading(false);
    }
  };

  const handleToggleStatus = async (targetUser: User) => {
    setAdminMsg(null);
    try {
      await updateUserStatus(targetUser.id, !targetUser.is_active, targetUser.is_locked ? false : undefined);
      setAdminMsg({
        type: "success",
        text: `User ${targetUser.email} status updated to ${!targetUser.is_active ? "Active" : "Inactive"}.`,
      });
      await fetchUsers();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAdminMsg({ type: "error", text: err.message });
      }
    }
  };

  const handleUnlockUser = async (targetUser: User) => {
    setAdminMsg(null);
    try {
      await updateUserStatus(targetUser.id, undefined, false);
      setAdminMsg({
        type: "success",
        text: `User ${targetUser.email} lockout cleared successfully.`,
      });
      await fetchUsers();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAdminMsg({ type: "error", text: err.message });
      }
    }
  };

  const handleAdminResetPassword = async (targetUser: User) => {
    setAdminMsg(null);
    try {
      const res = await adminResetPassword(targetUser.id);
      setAdminMsg({
        type: "success",
        text: `Password reset for ${targetUser.email}. Temporary Password: ${res.temporary_password}`,
      });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAdminMsg({ type: "error", text: err.message });
      }
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdminMsg(null);
    setCreatingUser(true);
    try {
      await createUser(newUserForm);
      setAdminMsg({
        type: "success",
        text: `Officer ${newUserForm.full_name} (${newUserForm.email}) created successfully.`,
      });
      setShowAddUser(false);
      setNewUserForm({
        employee_id: "",
        email: "",
        full_name: "",
        password: "",
        role_name: "investigator",
        department: "Crime Investigation",
        designation: "Officer",
      });
      await fetchUsers();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAdminMsg({ type: "error", text: err.message });
      }
    } finally {
      setCreatingUser(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Account & Security Settings
        </h2>
        <p className="text-sm text-slate-500">
          Manage officer credentials, session security, and role-based operational permissions.
        </p>
      </div>

      {/* Security Architecture & Guarantees Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center gap-2.5 shadow-sm">
          <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0" />
          <div>
            <span className="text-[11px] font-bold text-slate-900 dark:text-slate-100 block">Argon2id Protected</span>
            <span className="text-[10px] text-slate-400 font-mono">m=64MB, t=3, p=4</span>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center gap-2.5 shadow-sm">
          <Lock className="h-4 w-4 text-blue-500 shrink-0" />
          <div>
            <span className="text-[11px] font-bold text-slate-900 dark:text-slate-100 block">JWT Session</span>
            <span className="text-[10px] text-slate-400 font-mono">HS256 Scoped</span>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center gap-2.5 shadow-sm">
          <RefreshCw className="h-4 w-4 text-indigo-500 shrink-0" />
          <div>
            <span className="text-[11px] font-bold text-slate-900 dark:text-slate-100 block">JTI Revocation</span>
            <span className="text-[10px] text-slate-400 font-mono">Redis Blacklist</span>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center gap-2.5 shadow-sm">
          <UserCheck className="h-4 w-4 text-purple-500 shrink-0" />
          <div>
            <span className="text-[11px] font-bold text-slate-900 dark:text-slate-100 block">RBAC Enabled</span>
            <span className="text-[10px] text-slate-400 font-mono">5 Officer Roles</span>
          </div>
        </div>

        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center gap-2.5 col-span-2 sm:col-span-1 shadow-sm">
          <Hash className="h-4 w-4 text-emerald-500 shrink-0" />
          <div>
            <span className="text-[11px] font-bold text-slate-900 dark:text-slate-100 block">Case Membership</span>
            <span className="text-[10px] text-slate-400 font-mono">Zero-Trust Enforced</span>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Officer Profile Information */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-blue-600" />
              <CardTitle className="text-base">Authenticated Identity</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Cryptographically verified government officer profile
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="text-slate-500">Full Name</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {user?.full_name || "—"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="text-slate-500">Employee ID</span>
              <span className="font-mono text-slate-900 dark:text-slate-100">
                {user?.employee_id || "—"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="text-slate-500">Official Email</span>
              <span className="text-slate-900 dark:text-slate-100">{user?.email || "—"}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="text-slate-500">Assigned Role</span>
              <Badge variant="outline" className="capitalize bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                {user?.role?.replace("_", " ") || "—"}
              </Badge>
            </div>
            <div className="flex justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
              <span className="text-slate-500">Department</span>
              <span className="text-slate-900 dark:text-slate-100">
                {user?.department || "MHA / NCRB"}
              </span>
            </div>
            <div className="flex justify-between pb-1">
              <span className="text-slate-500">Account Security</span>
              <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Argon2id Hash Verified
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Change Password Form */}
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Key className="h-5 w-5 text-blue-600" />
              <CardTitle className="text-base">Change Password</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Re-hashes password with Argon2id parameters (m=64MB, t=3, p=4)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {pwdSuccess && (
              <div className="mb-3 flex items-center gap-2 rounded bg-emerald-50 dark:bg-emerald-950/40 p-2.5 text-xs text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                {pwdSuccess}
              </div>
            )}
            {pwdError && (
              <div className="mb-3 flex items-center gap-2 rounded bg-rose-50 dark:bg-rose-950/40 p-2.5 text-xs text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {pwdError}
              </div>
            )}

            <form onSubmit={handleChangePassword} className="space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Current Password
                </label>
                <Input
                  type="password"
                  placeholder="••••••••••••"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="mt-1"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  New Password (min 8 chars)
                </label>
                <Input
                  type="password"
                  placeholder="••••••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1"
                  required
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Confirm New Password
                </label>
                <Input
                  type="password"
                  placeholder="••••••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1"
                  required
                />
              </div>

              <Button
                type="submit"
                disabled={pwdLoading}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white mt-2"
              >
                {pwdLoading ? "Updating Password..." : "Update Password & Revoke Sessions"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* System Admin User Management Section */}
      {hasRole("system_admin") && (
        <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-blue-600" />
                <CardTitle className="text-lg">User Administration & RBAC</CardTitle>
              </div>
              <CardDescription className="text-xs">
                Manage government personnel accounts, assign single locked roles, and enforce account lockouts.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchUsers}
                disabled={usersLoading}
                className="gap-1.5 text-xs"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${usersLoading ? "animate-spin" : ""}`} /> Refresh
              </Button>
              <Button
                size="sm"
                onClick={() => setShowAddUser(!showAddUser)}
                className="gap-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white"
              >
                <PlusCircle className="h-3.5 w-3.5" />
                {showAddUser ? "Cancel" : "Add Officer"}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {adminMsg && (
              <div
                className={`flex items-center gap-2 rounded p-3 text-xs border ${
                  adminMsg.type === "success"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800"
                    : "bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800"
                }`}
              >
                {adminMsg.type === "success" ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                ) : (
                  <AlertCircle className="h-4 w-4 shrink-0" />
                )}
                <span>{adminMsg.text}</span>
              </div>
            )}

            {/* Create New User Modal/Inline Form */}
            {showAddUser && (
              <form
                onSubmit={handleCreateUser}
                className="rounded-lg border border-blue-200 dark:border-blue-900/60 bg-blue-50/50 dark:bg-blue-950/20 p-4 space-y-3"
              >
                <h4 className="text-xs font-bold uppercase tracking-wider text-blue-900 dark:text-blue-300">
                  Provision New Officer Account
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                      Employee ID
                    </label>
                    <Input
                      placeholder="EMP-INV-002"
                      value={newUserForm.employee_id}
                      onChange={(e) =>
                        setNewUserForm({ ...newUserForm, employee_id: e.target.value })
                      }
                      className="mt-1"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                      Official Email
                    </label>
                    <Input
                      type="email"
                      placeholder="officer2@ncrb.gov.in"
                      value={newUserForm.email}
                      onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value })}
                      className="mt-1"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                      Full Name
                    </label>
                    <Input
                      placeholder="Dr. Sunita Sharma"
                      value={newUserForm.full_name}
                      onChange={(e) =>
                        setNewUserForm({ ...newUserForm, full_name: e.target.value })
                      }
                      className="mt-1"
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                      Initial Password
                    </label>
                    <Input
                      type="password"
                      placeholder="SecurePass@2026!"
                      value={newUserForm.password}
                      onChange={(e) =>
                        setNewUserForm({ ...newUserForm, password: e.target.value })
                      }
                      className="mt-1"
                      required
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                      Assigned Role (Single-Role Locked)
                    </label>
                    <select
                      value={newUserForm.role_name}
                      onChange={(e) =>
                        setNewUserForm({ ...newUserForm, role_name: e.target.value as UserRole })
                      }
                      className="mt-1 flex h-9 w-full rounded-md border border-slate-300 bg-white px-3 py-1 text-sm dark:border-slate-800 dark:bg-slate-900"
                    >
                      <option value="investigator">Investigator</option>
                      <option value="forensic_expert">Forensic Expert</option>
                      <option value="legal_officer">Legal Officer</option>
                      <option value="supervisor">Supervisor</option>
                      <option value="system_admin">System Administrator</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                      Department
                    </label>
                    <Input
                      placeholder="Cyber Forensics Unit"
                      value={newUserForm.department || ""}
                      onChange={(e) =>
                        setNewUserForm({ ...newUserForm, department: e.target.value })
                      }
                      className="mt-1"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowAddUser(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={creatingUser}
                    className="bg-blue-600 hover:bg-blue-500 text-white"
                  >
                    {creatingUser ? "Provisioning..." : "Provision Officer Account"}
                  </Button>
                </div>
              </form>
            )}

            {/* Users Table */}
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-950 font-medium text-slate-600 dark:text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Employee ID</th>
                    <th className="px-4 py-3">Officer Name / Email</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Administrative Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {usersList.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50">
                      <td className="px-4 py-3 font-mono font-medium">{u.employee_id}</td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900 dark:text-slate-100">
                          {u.full_name}
                        </div>
                        <div className="text-[11px] text-slate-500">{u.email}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className="capitalize">
                          {u.role.replace("_", " ")}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                        {u.department || "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          {u.is_active ? (
                            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 font-medium">
                              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[11px] text-slate-400 font-medium">
                              <span className="h-1.5 w-1.5 rounded-full bg-slate-400" /> Inactive
                            </span>
                          )}
                          {u.is_locked && (
                            <span className="inline-flex items-center gap-1 text-[10px] text-rose-600 font-medium">
                              <Lock className="h-2.5 w-2.5" /> Locked
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {u.is_locked && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleUnlockUser(u)}
                              className="h-7 px-2 text-[11px] text-amber-600 border-amber-300 dark:border-amber-800 hover:bg-amber-50 dark:hover:bg-amber-950"
                              title="Clear lockout and reset failed login attempts"
                            >
                              <Unlock className="h-3 w-3 mr-1" /> Unlock
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleToggleStatus(u)}
                            className="h-7 px-2 text-[11px]"
                            title={u.is_active ? "Deactivate User" : "Activate User"}
                          >
                            {u.is_active ? (
                              <>
                                <UserX className="h-3 w-3 mr-1 text-rose-500" /> Deactivate
                              </>
                            ) : (
                              <>
                                <UserCheck className="h-3 w-3 mr-1 text-emerald-500" /> Activate
                              </>
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleAdminResetPassword(u)}
                            className="h-7 px-2 text-[11px]"
                            title="Generate a temporary password"
                          >
                            <Key className="h-3 w-3 mr-1" /> Reset Pwd
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {usersList.length === 0 && !usersLoading && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        No registered personnel found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 3. Immutable Audit Trail & Cryptographic Verification */}
      {(hasRole("system_admin") || hasRole("supervisor")) && (
        <Card>
          <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-blue-600" />
                <CardTitle className="text-lg">Immutable Audit Trail & Cryptographic Verification</CardTitle>
              </div>
              <CardDescription>
                Sequential SHA-256 hash-chaining verification.
                Guarantees mathematical tamper-evidence for all case lifecycle events.
              </CardDescription>
            </div>
            <Button
              onClick={handleVerifyChain}
              disabled={verifyingChain}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium shrink-0 h-9"
            >
              {verifyingChain ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> Verifying Chain...
                </>
              ) : (
                <>
                  <ShieldCheck className="h-4 w-4 mr-2" /> Verify Hash Chain Integrity
                </>
              )}
            </Button>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
            {/* Audit Status Alert */}
            {auditMsg && (
              <div
                className={`flex items-start gap-2 p-3.5 text-xs rounded-lg border ${
                  auditMsg.type === "success"
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-950 dark:border-emerald-900 dark:text-emerald-200"
                    : "bg-rose-50 border-rose-200 text-rose-800 dark:bg-rose-950 dark:border-rose-900 dark:text-rose-200"
                }`}
              >
                {auditMsg.type === "success" ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                ) : (
                  <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 font-medium">{auditMsg.text}</div>
              </div>
            )}

            {/* Verification Result Card */}
            {verificationResult && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4 rounded-lg bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500 font-medium block">Integrity Status</span>
                  <span className="mt-1 inline-block">
                    {verificationResult.is_valid ? (
                      <Badge className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold">
                        CHAIN VALIDATED
                      </Badge>
                    ) : (
                      <Badge className="bg-rose-600 hover:bg-rose-700 text-white font-semibold">
                        INTEGRITY VIOLATION
                      </Badge>
                    )}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Events Verified</span>
                  <span className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-1 block">
                    {verificationResult.total_events_checked} records
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Genesis Block Hash</span>
                  <span className="font-mono text-[11px] text-slate-700 dark:text-slate-300 mt-1 block truncate">
                    {verificationResult.genesis_hash ? verificationResult.genesis_hash.substring(0, 16) + "..." : "N/A"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 font-medium block">Current Chain Tip Hash</span>
                  <span className="font-mono text-[11px] text-slate-700 dark:text-slate-300 mt-1 block truncate">
                    {verificationResult.latest_hash ? verificationResult.latest_hash.substring(0, 16) + "..." : "N/A"}
                  </span>
                </div>
              </div>
            )}

            {/* Audit Trail Events Table */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                  Recent System Audit Trail ({auditEvents.length} records)
                </h4>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={fetchAuditData}
                  className="h-7 px-2 text-xs"
                >
                  <RefreshCw className={`h-3 w-3 mr-1 ${auditLoading ? "animate-spin" : ""}`} /> Refresh Log
                </Button>
              </div>

              <div className="rounded-md border border-slate-200 dark:border-slate-800 overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-medium">
                    <tr>
                      <th className="px-4 py-2.5">Timestamp</th>
                      <th className="px-4 py-2.5">Actor</th>
                      <th className="px-4 py-2.5">Action</th>
                      <th className="px-4 py-2.5">Resource</th>
                      <th className="px-4 py-2.5">Cryptographic Event Hash</th>
                      <th className="px-4 py-2.5 text-right">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {auditEvents.map((evt) => (
                      <tr key={evt.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                        <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">
                          {new Date(evt.timestamp).toLocaleString()}
                        </td>
                        <td className="px-4 py-2.5 font-medium text-slate-900 dark:text-slate-100">
                          {evt.actor_name}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="font-mono font-medium text-blue-600 dark:text-blue-400">
                            {evt.action}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">
                          {evt.resource_type}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[10px] text-slate-500 max-w-[180px] truncate">
                          {evt.event_hash}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <Badge
                            variant={evt.result === "success" ? "outline" : "destructive"}
                            className="text-[10px] uppercase h-5"
                          >
                            {evt.result}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                    {auditEvents.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                          No audit records found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
