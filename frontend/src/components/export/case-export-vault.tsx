"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  FileArchive,
  Download,
  ShieldCheck,
  ShieldAlert,
  Clock,
  RefreshCw,
  PlusCircle,
  Copy,
  Check,
  FileText,
  AlertCircle,
  CheckCircle2,
  Lock,
  ExternalLink,
  LogIn,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { CaseExport, ExportCreateRequest } from "@/types";
import {
  createCaseExport,
  listCaseExports,
  downloadCaseExport,
  saveBlobAsFile,
} from "@/lib/api";

interface CaseExportVaultProps {
  caseId: string;
  caseTitle: string;
  caseNumber: string;
  canExport?: boolean;
}

export function CaseExportVault({
  caseId,
  caseTitle,
  caseNumber,
  canExport = true,
}: CaseExportVaultProps) {
  const [exportsList, setExportsList] = useState<CaseExport[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Generate modal state
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [includeFiles, setIncludeFiles] = useState(true);
  const [exportReason, setExportReason] = useState("Filing before Hon'ble Court pursuant to Sec. 63/65B BSA, 2023");
  const [generating, setGenerating] = useState(false);

  // Manifest inspection modal state
  const [inspectExport, setInspectExport] = useState<CaseExport | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Download state
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const fetchExports = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await listCaseExports(caseId, 1, 50);
      setExportsList(res.items || []);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load case export history.");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    fetchExports();
  }, [fetchExports]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    setErrorMsg(null);
    try {
      const payload: ExportCreateRequest = {
        include_files: includeFiles,
        reason: exportReason.trim() || undefined,
      };
      const created = await createCaseExport(caseId, payload);
      setSuccessMsg(
        `Court export package ${created.file_name} generated successfully with integrity status: ${created.integrity_status.toUpperCase()}.`
      );
      setShowGenerateModal(false);
      await fetchExports();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to generate court export package.");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (exportItem: CaseExport) => {
    setDownloadingId(exportItem.id);
    setErrorMsg(null);
    try {
      const { blob, filename } = await downloadCaseExport(caseId, exportItem.id, exportItem.file_name);
      saveBlobAsFile(blob, filename);
      setSuccessMsg(`Downloaded export archive: ${filename}`);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to download export package.");
    } finally {
      setDownloadingId(null);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(id);
    setTimeout(() => setCopiedHash(null), 2500);
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 text-white rounded-xl shadow-lg border border-slate-700">
        <div>
          <div className="flex items-center gap-2">
            <FileArchive className="h-6 w-6 text-indigo-400" />
            <h2 className="text-lg font-bold tracking-tight">
              Legal & Court-Ready Evidence Export
            </h2>
            <Badge variant="outline" className="text-[10px] text-indigo-300 border-indigo-500/50 bg-indigo-950/40">
              BSA 2023 &bull; Sec. 63 / 65B
            </Badge>
          </div>
          <p className="text-xs text-slate-300 mt-1 max-w-2xl">
            Generate self-contained, cryptographically signed digital evidence dossiers for production before courts of law.
            Includes automated SHA-256 pre-export verification across all filings, custody ledger logs, and statutory certificates.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchExports}
            disabled={loading}
            className="border-slate-600 bg-slate-800/80 text-white hover:bg-slate-700"
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          {canExport && (
            <Button
              size="sm"
              onClick={() => setShowGenerateModal(true)}
              className="bg-indigo-600 hover:bg-indigo-500 text-white shadow-md"
            >
              <PlusCircle className="h-4 w-4 mr-1.5" />
              Generate Court Package
            </Button>
          )}
        </div>
      </div>

      {/* Status Messages */}
      {errorMsg && (
        <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-lg text-red-800 dark:text-red-200 text-sm">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-600 dark:text-red-400" />
          <div className="flex-1">{errorMsg}</div>
          {errorMsg.toLowerCase().includes("session required") && (
            <Link href="/login">
              <Button size="sm" variant="outline" className="h-7 text-xs bg-white dark:bg-slate-900 border-red-300 text-red-800 dark:text-red-200 gap-1">
                <LogIn className="h-3 w-3" /> Sign In
              </Button>
            </Link>
          )}
          <button
            onClick={() => setErrorMsg(null)}
            className="text-xs text-red-600 dark:text-red-400 underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center gap-3 p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 rounded-lg text-emerald-800 dark:text-emerald-200 text-sm">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-emerald-600 dark:text-emerald-400" />
          <div className="flex-1">{successMsg}</div>
          <button
            onClick={() => setSuccessMsg(null)}
            className="text-xs text-emerald-600 dark:text-emerald-400 underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Export List */}
      {loading && exportsList.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 space-y-3">
          <LoadingSpinner size="lg" />
          <p className="text-xs text-slate-500">Loading case export archives...</p>
        </div>
      ) : exportsList.length === 0 ? (
        <EmptyState
          icon={FileArchive}
          title="No Court Exports Generated Yet"
          description="Generate a court-ready package to bundle this case's documents, custody chain, forensic timeline, and cryptographic manifest."
          actionLabel={canExport ? "Generate First Court Export" : undefined}
          onAction={canExport ? () => setShowGenerateModal(true) : undefined}
        />
      ) : (
        <div className="space-y-4">
          {exportsList.map((exp) => {
            const isVerified = exp.integrity_status === "verified";
            const isCompromised = exp.integrity_status === "compromised";

            return (
              <Card
                key={exp.id}
                className={`overflow-hidden border transition-all ${
                  isCompromised
                    ? "border-red-400/80 bg-red-500/5 dark:border-red-900 dark:bg-red-950/20"
                    : "border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700"
                }`}
              >
                <CardContent className="p-5">
                  <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    {/* Package Info */}
                    <div className="space-y-2 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                          <FileArchive className="h-4 w-4 text-indigo-500" />
                          {exp.file_name}
                        </span>

                        {isVerified && (
                          <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300 flex items-center gap-1 text-[11px]">
                            <ShieldCheck className="h-3 w-3" /> Pre-Export Verified
                          </Badge>
                        )}
                        {isCompromised && (
                          <Badge className="bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300 border-red-300 flex items-center gap-1 text-[11px] font-bold">
                            <ShieldAlert className="h-3 w-3" /> Integrity Compromised
                          </Badge>
                        )}

                        <Badge variant="outline" className="text-slate-500 text-[10px]">
                          {formatBytes(exp.file_size_bytes)}
                        </Badge>
                      </div>

                      {/* Cryptographic Hashes */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                        <div className="flex items-center gap-1.5 font-mono text-[11px] bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1.5 rounded border border-slate-200 dark:border-slate-700">
                          <span className="text-slate-400 font-sans font-semibold text-[10px] uppercase tracking-wider">
                            ZIP SHA-256:
                          </span>
                          <span className="text-slate-700 dark:text-slate-300 truncate" title={exp.file_hash_sha256}>
                            {exp.file_hash_sha256.slice(0, 16)}...{exp.file_hash_sha256.slice(-8)}
                          </span>
                          <button
                            onClick={() => copyToClipboard(exp.file_hash_sha256, `zip-${exp.id}`)}
                            className="ml-auto text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                            title="Copy full SHA-256 hash"
                          >
                            {copiedHash === `zip-${exp.id}` ? (
                              <Check className="h-3.5 w-3.5 text-emerald-500" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>

                        <div className="flex items-center gap-1.5 font-mono text-[11px] bg-slate-100 dark:bg-slate-800/80 px-2.5 py-1.5 rounded border border-slate-200 dark:border-slate-700">
                          <span className="text-slate-400 font-sans font-semibold text-[10px] uppercase tracking-wider">
                            Manifest SHA-256:
                          </span>
                          <span className="text-slate-700 dark:text-slate-300 truncate" title={exp.manifest_hash_sha256}>
                            {exp.manifest_hash_sha256.slice(0, 16)}...{exp.manifest_hash_sha256.slice(-8)}
                          </span>
                          <button
                            onClick={() => copyToClipboard(exp.manifest_hash_sha256, `man-${exp.id}`)}
                            className="ml-auto text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                            title="Copy manifest SHA-256 hash"
                          >
                            {copiedHash === `man-${exp.id}` ? (
                              <Check className="h-3.5 w-3.5 text-emerald-500" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Timestamps and Verification metadata */}
                      <div className="flex items-center gap-4 text-[11px] text-slate-400 pt-1">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(exp.created_at).toLocaleString()}
                        </span>
                        {exp.verification_summary && (
                          <span>
                            Docs Verified: {exp.verification_summary.documents_checked ?? 0} &bull; Evidence: {exp.verification_summary.evidence_checked ?? 0}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 self-end md:self-center">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setInspectExport(exp)}
                        className="text-xs"
                      >
                        <FileText className="h-3.5 w-3.5 mr-1 text-slate-500" />
                        Inspect Manifest
                      </Button>

                      <Button
                        size="sm"
                        onClick={() => handleDownload(exp)}
                        disabled={downloadingId === exp.id}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs"
                      >
                        {downloadingId === exp.id ? (
                          <LoadingSpinner size="sm" className="mr-1.5" />
                        ) : (
                          <Download className="h-3.5 w-3.5 mr-1.5" />
                        )}
                        Download Package
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Modal: Generate Export Package */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-5">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <FileArchive className="h-5 w-5 text-indigo-600" />
                  Generate Court-Ready Export
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Case: {caseNumber} &bull; {caseTitle}
                </p>
              </div>
              <button
                onClick={() => setShowGenerateModal(false)}
                disabled={generating}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGenerate} className="space-y-4">
              <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 p-3.5 border border-slate-200 dark:border-slate-700 text-xs space-y-2">
                <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-indigo-500" />
                  Statutory Invariants & Guarantees:
                </div>
                <ul className="list-disc list-inside text-slate-600 dark:text-slate-400 space-y-1">
                  <li>Runs pre-export verification on all document baselines and custody chains.</li>
                  <li>Generates deterministic ZIP structure with SHA-256 root manifest.</li>
                  <li>Embeds Section 63/65B Bharatiya Sakshya Adhiniyam, 2023 authenticity certificate.</li>
                  <li>Records cryptographic hash-chained audit event for statutory compliance.</li>
                </ul>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Export Justification / Legal Reason
                </label>
                <textarea
                  value={exportReason}
                  onChange={(e) => setExportReason(e.target.value)}
                  rows={2}
                  className="w-full text-xs rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Reason for export (e.g., Filing before Sessions Court, New Delhi)"
                  required
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="includeFilesCheck"
                  checked={includeFiles}
                  onChange={(e) => setIncludeFiles(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="includeFilesCheck" className="text-xs font-medium text-slate-700 dark:text-slate-300 cursor-pointer">
                  Include raw forensic document files inside ZIP archive
                </label>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowGenerateModal(false)}
                  disabled={generating}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={generating}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white"
                >
                  {generating ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      Verifying & Packaging...
                    </>
                  ) : (
                    <>
                      <FileArchive className="h-4 w-4 mr-1.5" />
                      Generate Sealed Export
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Inspect Manifest & Certificate */}
      {inspectExport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-3xl bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Lock className="h-4 w-4 text-indigo-500" />
                  Cryptographic Manifest & Statutory Certificate
                </h3>
                <p className="text-xs font-mono text-slate-500 mt-0.5">
                  Package: {inspectExport.file_name}
                </p>
              </div>
              <button
                onClick={() => setInspectExport(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-sm font-semibold"
              >
                ✕
              </button>
            </div>

            {/* Verification Summary Banner */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
                <span className="text-slate-400 font-semibold uppercase text-[10px] block">Integrity State</span>
                <span className={`font-bold capitalize text-sm ${inspectExport.integrity_status === "verified" ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                  {inspectExport.integrity_status}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
                <span className="text-slate-400 font-semibold uppercase text-[10px] block">Documents Verified</span>
                <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                  {inspectExport.verification_summary?.documents_checked ?? 0} files
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
                <span className="text-slate-400 font-semibold uppercase text-[10px] block">Custody Chains</span>
                <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                  {inspectExport.verification_summary?.evidence_checked ?? 0} chains valid
                </span>
              </div>
            </div>

            {/* Root Hashes */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Cryptographic Baselines
              </label>
              <div className="space-y-1.5 font-mono text-xs">
                <div className="p-2.5 rounded bg-slate-900 text-slate-100 flex items-center justify-between gap-2 border border-slate-800">
                  <span className="text-indigo-400 text-[11px] font-semibold">ZIP SHA-256:</span>
                  <span className="truncate">{inspectExport.file_hash_sha256}</span>
                  <button
                    onClick={() => copyToClipboard(inspectExport.file_hash_sha256, "modal-zip")}
                    className="text-slate-400 hover:text-white"
                  >
                    {copiedHash === "modal-zip" ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
                <div className="p-2.5 rounded bg-slate-900 text-slate-100 flex items-center justify-between gap-2 border border-slate-800">
                  <span className="text-indigo-400 text-[11px] font-semibold">MANIFEST SHA-256:</span>
                  <span className="truncate">{inspectExport.manifest_hash_sha256}</span>
                  <button
                    onClick={() => copyToClipboard(inspectExport.manifest_hash_sha256, "modal-man")}
                    className="text-slate-400 hover:text-white"
                  >
                    {copiedHash === "modal-man" ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Enclosed Manifest Files */}
            {inspectExport.manifest_data?.files && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                    Enclosed Archive Files ({inspectExport.manifest_data.files.length})
                  </label>
                  <span className="text-[10px] text-slate-400">Canonical SHA-256 entries</span>
                </div>
                <div className="border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                      <tr>
                        <th className="p-2">Relative Path</th>
                        <th className="p-2">SHA-256 Digest</th>
                        <th className="p-2 text-right">Size</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono text-[11px]">
                      {inspectExport.manifest_data.files.map((f, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                          <td className="p-2 text-indigo-600 dark:text-indigo-400 font-sans">{f.path}</td>
                          <td className="p-2 text-slate-500 dark:text-slate-400 truncate max-w-xs">{f.sha256}</td>
                          <td className="p-2 text-right text-slate-500 font-sans">{formatBytes(f.size)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Statutory Certificate Preview */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Statutory Certificate (Bharatiya Sakshya Adhiniyam, 2023)
              </label>
              <pre className="p-3 bg-slate-950 text-slate-200 rounded-lg text-[10px] font-mono whitespace-pre-wrap max-h-44 overflow-y-auto border border-slate-800">
{`GOVERNMENT OF INDIA - MINISTRY OF HOME AFFAIRS
NATIONAL CRIME RECORDS BUREAU (NCRB)
DOCSHIELD EVIDENCE & LEGAL CASE LIFECYCLE MANAGEMENT SYSTEM
CERTIFICATE OF AUTHENTICITY AND DIGITAL INTEGRITY
BHARATIYA SAKSHYA ADHINIYAM (BSA), 2023 / SEC. 63 & 65B CERTIFICATE
Pursuant to Section 63 & 65B of the Bharatiya Sakshya Adhiniyam, 2023

CASE IDENTIFIER: ${caseNumber}
EXPORT UUID:     ${inspectExport.id}
GENERATED AT:    ${new Date(inspectExport.created_at).toISOString()}
PRE-EXPORT STATUS: ${inspectExport.integrity_status.toUpperCase()}
MANIFEST HASH:   ${inspectExport.manifest_hash_sha256}
PACKAGE HASH:    ${inspectExport.file_hash_sha256}

This digital evidence archive contains all verified forensic artifacts, legal
filings, investigative witness records, and chain-of-custody transfer records
pertaining to the above-referenced case. Immutability is guaranteed by cryptographic
SHA-256 digest sealing and hash-chained custody ledgers.`}
              </pre>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setInspectExport(null)}
              >
                Close
              </Button>
              <Button
                size="sm"
                onClick={() => handleDownload(inspectExport)}
                className="bg-indigo-600 hover:bg-indigo-500 text-white"
              >
                <Download className="h-4 w-4 mr-1.5" />
                Download Package
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
