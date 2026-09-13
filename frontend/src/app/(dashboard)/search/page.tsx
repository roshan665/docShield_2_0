"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  Sparkles,
  FileText,
  FolderLock,
  ShieldAlert,
  ShieldCheck,
  RefreshCw,
  SlidersHorizontal,
  Database,
  Layers,
  HelpCircle,
  Copy,
  Check,
  Send,
  ExternalLink,
  ChevronRight,
  Info,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Case,
  SearchMode,
  SearchResponse,
  SearchResultItem,
  SearchAskResponse,
  SearchStatusResponse,
} from "@/types";
import {
  listCases,
  searchSemantic,
  searchHybrid,
  searchKeyword,
  searchAsk,
  getSearchStatus,
} from "@/lib/api";

const DOCUMENT_TYPES = [
  { value: "", label: "All Document Types" },
  { value: "fir", label: "First Information Report (FIR)" },
  { value: "charge_sheet", label: "Charge Sheet" },
  { value: "police_report", label: "Police Report" },
  { value: "witness_statement", label: "Witness Statement" },
  { value: "forensic_report", label: "Forensic Report" },
  { value: "seizure_memo", label: "Seizure Memo" },
  { value: "court_filing", label: "Court Filing" },
  { value: "medical_report", label: "Medical Report" },
  { value: "supporting_document", label: "Supporting Document" },
];

const RECOMMENDED_PROMPTS = [
  "What are the primary charges, legal sections, and offences cited across documents?",
  "What forensic evidence, ballistics, or digital artifacts are recorded?",
  "Summarize key witness testimonies, deponent statements, and timelines.",
  "Which bank accounts, shell companies, or transactions are flagged?",
];

export default function SearchPage() {
  // Navigation / Mode
  const [activeTab, setActiveTab] = useState<SearchMode | "rag">("semantic");

  // Filter & Scope States
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [selectedDocType, setSelectedDocType] = useState<string>("");
  const [resultLimit, setResultLimit] = useState<number>(10);
  const [semanticWeight, setSemanticWeight] = useState<number>(0.6);
  const [loadingCases, setLoadingCases] = useState(true);

  // Status State
  const [indexStatus, setIndexStatus] = useState<SearchStatusResponse | null>(null);

  // Search State
  const [query, setQuery] = useState("");
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [copiedCitation, setCopiedCitation] = useState<string | null>(null);

  // RAG State
  const [ragQuestion, setRagQuestion] = useState("");
  const [loadingRag, setLoadingRag] = useState(false);
  const [ragHistory, setRagHistory] = useState<SearchAskResponse[]>([]);
  const [copiedRagIdx, setCopiedRagIdx] = useState<number | null>(null);

  // Global Error State
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load cases and search status on mount
  const loadInitialData = useCallback(async () => {
    try {
      setLoadingCases(true);
      const [caseList, status] = await Promise.allSettled([
        listCases(),
        getSearchStatus(),
      ]);

      if (caseList.status === "fulfilled") {
        setCases(caseList.value);
      }
      if (status.status === "fulfilled") {
        setIndexStatus(status.value);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load initial context.");
    } finally {
      setLoadingCases(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Execute Search
  const handleExecuteSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    try {
      setLoadingSearch(true);
      setErrorMsg(null);

      const baseParams = {
        query: query.trim(),
        case_id: selectedCaseId || undefined,
        document_type: selectedDocType || undefined,
        limit: resultLimit,
      };

      let res: SearchResponse;
      if (activeTab === "semantic") {
        res = await searchSemantic(baseParams);
      } else if (activeTab === "hybrid") {
        res = await searchHybrid({
          ...baseParams,
          semantic_weight: semanticWeight,
          keyword_weight: Math.round((1 - semanticWeight) * 10) / 10,
        });
      } else {
        res = await searchKeyword(baseParams);
      }

      setSearchResults(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Search retrieval failed.");
    } finally {
      setLoadingSearch(false);
    }
  };

  // Execute RAG Ask
  const handleExecuteRag = async (qPrompt?: string) => {
    const promptToUse = qPrompt || ragQuestion;
    if (!promptToUse.trim()) return;

    try {
      setLoadingRag(true);
      setErrorMsg(null);

      const res = await searchAsk({
        question: promptToUse.trim(),
        case_id: selectedCaseId || undefined,
        limit: 5,
        temperature: 0.1,
      });

      setRagHistory((prev) => [res, ...prev]);
      if (!qPrompt) setRagQuestion("");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "RAG synthesis failed.");
    } finally {
      setLoadingRag(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCitation(label);
    setTimeout(() => setCopiedCitation(null), 2000);
  };

  const copyRagAnswer = (answer: string, idx: number) => {
    navigator.clipboard.writeText(answer);
    setCopiedRagIdx(idx);
    setTimeout(() => setCopiedRagIdx(null), 2000);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header & Status Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              Evidence Intelligence & Search
            </h1>
            <Badge variant="outline" className="border-blue-500/40 text-blue-600 dark:text-blue-400 text-xs font-semibold px-2 py-0.5">
              pgvector HNSW
            </Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Pre-retrieval authorization enforced directly in SQL. Zero cross-case leakage.
            Authorization-aware retrieval across verified case records.
          </p>
        </div>

        {/* Live Index Statistics */}
        {indexStatus && (
          <div className="flex items-center gap-3 bg-slate-50 dark:bg-slate-900 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-800 text-xs">
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <Database className="h-3.5 w-3.5 text-emerald-500" />
              <span>Embeddings:</span>
              <span className="font-bold text-slate-900 dark:text-slate-100">
                {indexStatus.searchable_embeddings}
              </span>
            </div>
            <span className="text-slate-300 dark:text-slate-700">|</span>
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <FileText className="h-3.5 w-3.5 text-blue-500" />
              <span>Indexed Docs:</span>
              <span className="font-bold text-slate-900 dark:text-slate-100">
                {indexStatus.indexed_documents_count}
              </span>
            </div>
            <span className="text-slate-300 dark:text-slate-700">|</span>
            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-400 text-[10px] font-mono">
              768-dim HNSW Active
            </Badge>
          </div>
        )}
      </div>

      {/* Error Alert */}
      {errorMsg && (
        <div className="p-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          {errorMsg.toLowerCase().includes("session required") && (
            <Link
              href="/login"
              className="inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-md bg-red-600 text-white hover:bg-red-700 transition-colors shrink-0"
            >
              Sign In
            </Link>
          )}
        </div>
      )}

      {/* Scope Controls and Mode Tabs */}
      <div className="bg-slate-50 dark:bg-slate-900/80 rounded-xl p-4 border border-slate-200 dark:border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Mode Switcher */}
          <div className="flex items-center bg-slate-200/80 dark:bg-slate-800 p-1 rounded-lg border border-slate-300 dark:border-slate-700">
            <button
              onClick={() => setActiveTab("semantic")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === "semantic"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <Search className="h-3.5 w-3.5" />
              Dense Semantic
            </button>
            <button
              onClick={() => setActiveTab("hybrid")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === "hybrid"
                  ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              Hybrid (RRF)
            </button>
            <button
              onClick={() => setActiveTab("keyword")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === "keyword"
                  ? "bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-sm font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <FileText className="h-3.5 w-3.5" />
              Keyword Lexical
            </button>
            <button
              onClick={() => setActiveTab("rag")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === "rag"
                  ? "bg-white dark:bg-slate-900 text-purple-600 dark:text-purple-400 shadow-sm font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" />
              Authorized Assistant (RAG)
            </button>
          </div>

          {/* Case Scope Selection */}
          <div className="flex items-center gap-2">
            <FolderLock className="h-4 w-4 text-blue-600 shrink-0" />
            <select
              value={selectedCaseId}
              onChange={(e) => {
                setSelectedCaseId(e.target.value);
                setSearchResults(null);
              }}
              className="text-xs font-medium bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-md p-1.5 text-slate-900 dark:text-slate-100 min-w-[220px]"
            >
              <option value="">All Authorized Cases</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.case_number} - {c.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Secondary Filters for Search Modes */}
        {activeTab !== "rag" && (
          <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-slate-200 dark:border-slate-800 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-500 font-medium">Filter Type:</span>
              <select
                value={selectedDocType}
                onChange={(e) => setSelectedDocType(e.target.value)}
                className="bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded p-1 text-slate-900 dark:text-slate-100"
              >
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-500 font-medium">Max Limit:</span>
              <select
                value={resultLimit}
                onChange={(e) => setResultLimit(Number(e.target.value))}
                className="bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded p-1 text-slate-900 dark:text-slate-100"
              >
                <option value={5}>Top 5</option>
                <option value={10}>Top 10</option>
                <option value={20}>Top 20</option>
                <option value={50}>Top 50</option>
              </select>
            </div>

            {/* Hybrid Weights Selector */}
            {activeTab === "hybrid" && (
              <div className="flex items-center gap-2 bg-indigo-50/70 dark:bg-indigo-950/30 px-2.5 py-1 rounded border border-indigo-200 dark:border-indigo-800">
                <SlidersHorizontal className="h-3 w-3 text-indigo-600" />
                <span className="text-indigo-900 dark:text-indigo-200 font-medium">
                  Dense Weight: {semanticWeight * 100}% | Keyword: {Math.round((1 - semanticWeight) * 100)}%
                </span>
                <input
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.1"
                  value={semanticWeight}
                  onChange={(e) => setSemanticWeight(parseFloat(e.target.value))}
                  className="w-20 cursor-pointer accent-indigo-600"
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* SEARCH MODES: Semantic, Hybrid, Keyword */}
      {activeTab !== "rag" && (
        <div className="space-y-6">
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                {activeTab === "semantic" && <Search className="h-4 w-4 text-blue-600" />}
                {activeTab === "hybrid" && <Layers className="h-4 w-4 text-indigo-600" />}
                {activeTab === "keyword" && <FileText className="h-4 w-4 text-emerald-600" />}
                {activeTab === "semantic" && "Semantic Concept Retrieval (pgvector Cosine)"}
                {activeTab === "hybrid" && "Hybrid Rank Fusion (Dense Vector + Sparse Lexical RRF)"}
                {activeTab === "keyword" && "Lexical Full-Text Search (Exact Substrings)"}
              </CardTitle>
              <CardDescription className="text-xs">
                {activeTab === "semantic" && "Performs high-dimensional nearest neighbor search against 768-dim embeddings across authorized case documents."}
                {activeTab === "hybrid" && "Combines pgvector conceptual similarity with keyword ranking via Reciprocal Rank Fusion."}
                {activeTab === "keyword" && "Filters document text chunks using SQL ILIKE search with strict case boundary enforcement."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleExecuteSearch} className="flex gap-2">
                <Input
                  placeholder={
                    activeTab === "semantic"
                      ? "Search conceptual topics (e.g., shell corporation fund diversion, deponent contradiction, ballistic caliber)..."
                      : activeTab === "hybrid"
                      ? "Enter keywords or concepts for reciprocal rank fusion..."
                      : "Enter exact names, numbers, or phrases (e.g. DL-04-AB-1234, Sec 302, Dr. Rao)..."
                  }
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="text-xs border-slate-300 dark:border-slate-700"
                />
                <Button
                  type="submit"
                  disabled={loadingSearch || !query.trim()}
                  className="bg-blue-600 hover:bg-blue-700 text-white text-xs flex items-center gap-1.5 px-5"
                >
                  {loadingSearch ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Search className="h-3.5 w-3.5" />
                  )}
                  Execute Search
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Search Results */}
          {searchResults && (
            <div className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-slate-500 gap-1">
                <div className="flex items-center gap-2">
                  <span>
                    Found <strong className="text-slate-800 dark:text-slate-200">{searchResults.total_results}</strong> results
                    for &quot;{searchResults.query}&quot;
                  </span>
                  <Badge variant="outline" className="text-[10px] uppercase font-mono">
                    Mode: {searchResults.search_type}
                  </Badge>
                </div>
              </div>

              {searchResults.results.map((res: SearchResultItem, idx: number) => {
                const citationTag = res.chunk_id || res.citation_label || `DOC-${res.document_id.slice(0, 8)}-C${res.chunk_index}`;
                const matchScore = res.similarity ?? res.score ?? 0;
                return (
                  <Card key={idx} className="border-slate-200 dark:border-slate-800 hover:border-blue-400 transition-colors">
                    <CardContent className="p-4 space-y-2.5">
                      {/* Header: Title, Citation Label, Score */}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-blue-600 shrink-0" />
                          <Link
                            href={`/documents`}
                            className="text-xs font-bold text-slate-900 dark:text-slate-100 hover:text-blue-600 hover:underline flex items-center gap-1"
                          >
                            {res.document_title}
                            <ExternalLink className="h-3 w-3 opacity-60" />
                          </Link>
                          <Badge variant="secondary" className="text-[10px] uppercase">
                            {res.document_type}
                          </Badge>
                        </div>

                        <div className="flex items-center gap-2">
                          {/* Citation Pill */}
                          <button
                            onClick={() => copyToClipboard(citationTag, citationTag)}
                            className="flex items-center gap-1 px-2 py-0.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded font-mono text-[10px] transition-colors border border-slate-200 dark:border-slate-700"
                            title="Click to copy citation identifier"
                          >
                            <span>[{citationTag}]</span>
                            {copiedCitation === citationTag ? (
                              <Check className="h-2.5 w-2.5 text-emerald-600" />
                            ) : (
                              <Copy className="h-2.5 w-2.5 opacity-60" />
                            )}
                          </button>

                          {/* Match Score */}
                          <Badge
                            className={`text-[10px] font-bold ${
                              matchScore >= 0.75
                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                : matchScore >= 0.5
                                ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                                : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                            }`}
                          >
                            Score: {(matchScore * 100).toFixed(1)}%
                          </Badge>
                        </div>
                      </div>

                    {/* Excerpt Chunk */}
                    <div className="p-3 bg-slate-50 dark:bg-slate-900/60 rounded-md border border-slate-100 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 font-mono leading-relaxed whitespace-pre-wrap">
                      {res.chunk_text}
                    </div>

                    {/* Footer Info */}
                    <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                      <span>Chunk Index: #{res.chunk_index + 1}</span>
                      <span>Case ID: {res.case_id.slice(0, 8)}...</span>
                      <span>Doc ID: {res.document_id.slice(0, 8)}...</span>
                    </div>
                  </CardContent>
                </Card>
              );
            })}

              {searchResults.results.length === 0 && (
                <div className="text-center py-12 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl text-xs text-slate-500">
                  No matching document chunks found within authorized cases.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* RAG ASSISTANT TAB */}
      {activeTab === "rag" && (
        <div className="space-y-6">
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-purple-600" />
                Case Intelligence Assistant (Zero-Trust Grounded RAG)
              </CardTitle>
              <CardDescription className="text-xs">
                Answers are synthesized exclusively from verified chunks in authorized cases. Hallucinations stripped via citation verification.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Ask any investigative question (e.g., What vehicle license numbers and weapons were identified?)..."
                  value={ragQuestion}
                  onChange={(e) => setRagQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !loadingRag && handleExecuteRag()}
                  className="text-xs border-slate-300 dark:border-slate-700"
                />
                <Button
                  onClick={() => handleExecuteRag()}
                  disabled={loadingRag || !ragQuestion.trim()}
                  className="bg-purple-600 hover:bg-purple-700 text-white text-xs flex items-center gap-1.5 px-5"
                >
                  {loadingRag ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Send className="h-3.5 w-3.5" />
                  )}
                  Synthesize
                </Button>
              </div>

              {/* Recommended Quick Prompts */}
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
                  Investigative Quick Prompts
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {RECOMMENDED_PROMPTS.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleExecuteRag(prompt)}
                      disabled={loadingRag}
                      className="text-left text-[11px] px-2.5 py-1 bg-slate-100 hover:bg-purple-50 dark:bg-slate-800 dark:hover:bg-purple-950/40 text-slate-700 dark:text-slate-300 hover:text-purple-700 dark:hover:text-purple-300 rounded-md border border-slate-200 dark:border-slate-700 transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* RAG Answer Stream */}
          {ragHistory.length > 0 && (
            <div className="space-y-4">
              {ragHistory.map((item: SearchAskResponse, idx: number) => (
                <Card key={idx} className="border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                  <div className="bg-slate-50 dark:bg-slate-900/60 p-3.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <HelpCircle className="h-3.5 w-3.5 text-purple-600" />
                      Q: {item.question}
                    </span>
                    <div className="flex items-center gap-3">
                      <Badge className="bg-purple-50 text-purple-700 border-purple-300 dark:bg-purple-950 dark:text-purple-400 text-[10px] font-bold">
                        {item.ai_generated ? "Grounded AI Synthesis" : "Case Record Extraction"}
                      </Badge>
                      <button
                        onClick={() => copyRagAnswer(item.answer, idx)}
                        className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs flex items-center gap-1"
                        title="Copy answer"
                      >
                        {copiedRagIdx === idx ? (
                          <Check className="h-3.5 w-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  </div>

                  <CardContent className="p-4 space-y-4">
                    {/* Synthesized Answer */}
                    <div className="text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-line bg-purple-50/30 dark:bg-purple-950/20 p-4 rounded-lg border border-purple-100 dark:border-purple-900/40 font-mono">
                      {item.answer}
                    </div>

                    {/* Citations List */}
                    {item.citations && item.citations.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                        <div className="flex items-center justify-between">
                          <p className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                            Verified Evidence Citations ({item.citations.length})
                          </p>
                          {item.unverified_citations_removed !== undefined && item.unverified_citations_removed > 0 && (
                            <span className="text-[10px] text-amber-600 font-mono">
                              ({item.unverified_citations_removed} unverified removed)
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {item.citations.map((cite, cIdx) => (
                            <div
                              key={cIdx}
                              className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 text-[11px] space-y-1.5 shadow-sm"
                            >
                              <div className="flex items-center justify-between font-medium">
                                <span className="font-mono text-[9px] font-bold text-purple-700 dark:text-purple-300 bg-purple-100/80 dark:bg-purple-950/80 px-1.5 py-0.5 rounded border border-purple-200 dark:border-purple-800">
                                  SOURCE {String(cIdx + 1).padStart(2, "0")}
                                </span>
                                <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 uppercase font-mono">
                                  [{cite.chunk_id}]
                                </Badge>
                              </div>
                              <div className="flex items-center gap-1 truncate text-slate-900 dark:text-slate-100 font-medium" title={cite.document_title}>
                                <FileText className="h-3 w-3 text-purple-500 shrink-0" />
                                <span className="truncate">{cite.document_title}</span>
                              </div>
                              <p className="text-slate-500 dark:text-slate-400 line-clamp-2 italic font-mono text-[10px] bg-white dark:bg-slate-950 p-1.5 rounded border border-slate-100 dark:border-slate-800">
                                &quot;{cite.snippet}&quot;
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Prominent Statutory Legal Disclaimer */}
                    <div className="p-3 bg-amber-50/90 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 rounded-lg text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
                      <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold block uppercase tracking-wider text-[10px] text-amber-800 dark:text-amber-300">
                          AI-Assisted Analysis &bull; Human Verification Required
                        </span>
                        <p className="text-[11px] text-amber-700/90 dark:text-amber-300/90 mt-0.5 leading-relaxed">
                          {item.disclaimer || "All AI responses must be independently reviewed against physical or primary digital evidence filings pursuant to Section 63/65B of the Bharatiya Sakshya Adhiniyam, 2023."}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {ragHistory.length === 0 && !loadingRag && (
            <div className="text-center py-12 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl p-6">
              <Sparkles className="h-8 w-8 text-purple-400 mx-auto mb-2 opacity-50" />
              <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                No inquiries initiated yet
              </h3>
              <p className="text-[11px] text-slate-500 max-w-sm mx-auto mt-1">
                Type an investigative question or select a prompt above to synthesize intelligence from verified case documents.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
