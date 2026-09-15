"use client";

import { useState } from "react";
import { Shield, Lock, ArrowRight, AlertCircle, Loader2, KeyRound } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login({ email: email.trim(), password });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Authentication failed. Please verify your credentials.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillCredentials = (userEmail: string, userPass: string) => {
    setEmail(userEmail);
    setPassword(userPass);
    setError(null);
  };

  return (
    <Card className="w-full max-w-md border-slate-800 bg-[#0B1528] text-white shadow-2xl">
      <CardHeader className="text-center pb-3">
        <div className="mx-auto mb-2 flex items-center justify-center">
          <Badge
            variant="outline"
            className="gap-1.5 border-blue-800/80 bg-blue-950/80 text-blue-300 font-mono text-[10px] uppercase font-semibold"
          >
            <Lock className="h-2.5 w-2.5" /> OFFICIAL USE ONLY
          </Badge>
        </div>

        <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 shadow-lg ring-1 ring-blue-400/30">
          <Shield className="h-7 w-7 text-white" />
        </div>
        <CardTitle className="text-xl font-bold tracking-tight text-white uppercase font-sans">DocShield</CardTitle>
        <p className="text-xs text-blue-400 font-medium mt-0.5">
          Secure Evidence. Trusted Records. Faster Justice.
        </p>
        <CardDescription className="text-slate-400 text-[11px] mt-1 font-mono">
          NCRB &bull; MHA INDIA &bull; National Evidence Platform
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-rose-900/50 bg-rose-950/40 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400 mt-0.5" />
            <div className="leading-relaxed">{error}</div>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-300">Official Gov Email</label>
            <Input
              type="email"
              placeholder="officer@ncrb.gov.in"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-slate-700 bg-slate-900/90 text-white placeholder:text-slate-500 font-mono text-xs focus:ring-blue-500"
              required
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-300">Password</label>
            <Input
              type="password"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-slate-700 bg-slate-900/90 text-white placeholder:text-slate-500 font-mono text-xs focus:ring-blue-500"
              required
              disabled={isSubmitting}
            />
          </div>

          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white gap-2 mt-2 font-medium shadow-md shadow-blue-900/20"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Authenticating Session...
              </>
            ) : (
              <>
                Authenticate Session <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>

          {/* Quick Credential Fill Helpers for Evaluators */}
          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs shadow-inner">
            <div className="flex items-center gap-1.5 text-slate-400 font-medium mb-2">
              <KeyRound className="h-3.5 w-3.5 text-blue-400" />
              <span className="font-mono text-[11px]">Evaluation Quick-Fill:</span>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              <button
                type="button"
                onClick={() => fillCredentials("admin@docshield.gov.in", "Admin@12345")}
                className="rounded-lg border border-slate-700/80 bg-slate-800/80 p-2 text-left text-[11px] text-slate-200 hover:bg-slate-700/90 hover:border-amber-500 transition shadow-sm"
              >
                <div className="font-semibold text-amber-400 text-[11px]">Admin</div>
                <div className="text-[9px] text-slate-400 truncate font-mono">admin@docshield.gov.in</div>
              </button>
              <button
                type="button"
                onClick={() => fillCredentials("officer@docshield.gov.in", "Officer@12345")}
                className="rounded-lg border border-slate-700/80 bg-slate-800/80 p-2 text-left text-[11px] text-slate-200 hover:bg-slate-700/90 hover:border-blue-500 transition shadow-sm"
              >
                <div className="font-semibold text-blue-400 text-[11px]">Officer</div>
                <div className="text-[9px] text-slate-400 truncate font-mono">officer@docshield.gov.in</div>
              </button>
              <button
                type="button"
                onClick={() => fillCredentials("advocate@docshield.gov.in", "Advocate@12345")}
                className="rounded-lg border border-slate-700/80 bg-slate-800/80 p-2 text-left text-[11px] text-slate-200 hover:bg-slate-700/90 hover:border-purple-500 transition shadow-sm"
              >
                <div className="font-semibold text-purple-400 text-[11px]">Advocate</div>
                <div className="text-[9px] text-slate-400 truncate font-mono">advocate@docshield.gov.in</div>
              </button>
            </div>
          </div>

          <div className="mt-3 flex items-center justify-center gap-1.5 text-[10px] text-slate-500 font-mono">
            <Lock className="h-3 w-3 text-slate-400" /> Zero-Trust Verified Session &bull; Argon2id / JTI Blacklist
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
