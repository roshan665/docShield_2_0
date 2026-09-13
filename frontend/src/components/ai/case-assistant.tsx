"use client";

import { useState } from "react";
import {
  Sparkles,
  Search,
  MessageSquare,
  Send,
  FileText,
  ShieldAlert,
  ShieldCheck,
  Copy,
  Check,
  RefreshCw,
  HelpCircle,
  ExternalLink,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import {
  RAGAnswerResponse,
  SemanticSearchResponse,
} from "@/types";
import {
  askCaseAssistant,
  semanticSearchCase,
} from "@/lib/api";

interface CaseAssistantProps {
  caseId: string;
  caseTitle?: string;
  caseNumber?: string;
}

const RECOMMENDED_QUESTIONS = [
  "What are the primary offences and sections of law charged in this case?",
  "Who are the key persons, suspects, and witnesses mentioned in the records?",
  "What physical and digital evidence articles have been seized or examined?",
  "Summarize the timeline of events from the First Information Report (FIR).",
];

export function CaseAssistant({ caseId, caseTitle, caseNumber }: CaseAssistantProps) {
  const [activeTab, setActiveTab] = useState<"chat" | "search">("chat");

  // RAG Chat State
  const [question, setQuestion] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);
  const [chatAnswer, setChatAnswer] = useState<RAGAnswerResponse | null>(null);
  const [chatHistory, setChatHistory] = useState<Array<{ q: string; a: RAGAnswerResponse }>>([]);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  // Semantic Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [searchResults, setSearchResults] = useState<SemanticSearchResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleAsk = async (qText?: string) => {
    const queryToUse = qText || question;
    if (!queryToUse.trim()) return;

    try {
      setLoadingChat(true);
      setErrorMsg(null);
      const res = await askCaseAssistant(caseId, queryToUse.trim(), 5);
      setChatAnswer(res);
      setChatHistory((prev) => [{ q: queryToUse.trim(), a: res }, ...prev]);
      if (!qText) setQuestion("");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to generate answer from case records.");
    } finally {
      setLoadingChat(false);
    }
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    try {
      setLoadingSearch(true);
      setErrorMsg(null);
      const res = await semanticSearchCase(caseId, searchQuery.trim(), 8, 0.25);
      setSearchResults(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Semantic search failed.");
    } finally {
      setLoadingSearch(false);
    }
  };

  const copyText = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-blue-900/20 via-indigo-900/10 to-slate-900/20 rounded-xl p-5 border border-blue-500/20 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <div className="p-2 bg-blue-600 text-white rounded-lg shadow-sm">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  DOCSHIELD AI Case Assistant
                  <Badge variant="outline" className="border-blue-500 text-blue-600 dark:text-blue-400 text-[10px] font-semibold uppercase">
                    Zero-Trust RAG
                  </Badge>
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Grounded strictly in documents from {caseTitle || caseNumber || "this case"}. No cross-case leakage.
                </p>
              </div>
            </div>
          </div>

          {/* Tab Switcher */}
          <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === "chat"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <MessageSquare className="h-3.5 w-3.5" />
              Investigative Q&A
            </button>
            <button
              onClick={() => setActiveTab("search")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                activeTab === "search"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <Search className="h-3.5 w-3.5" />
              Dense Vector Search
            </button>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* TAB 1: RAG Question Answering */}
      {activeTab === "chat" && (
        <div className="space-y-6">
          {/* Query Input Box */}
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-blue-600" />
                Ask Case Intelligence Assistant
              </CardTitle>
              <CardDescription className="text-xs">
                Inquire about statements, suspect details, forensic ballistics, medical findings, or charges.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="e.g., What vehicle registration and clothing was observed near the crime scene?"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !loadingChat && handleAsk()}
                  className="text-xs border-slate-300 dark:border-slate-700 focus-visible:ring-blue-500"
                />
                <Button
                  onClick={() => handleAsk()}
                  disabled={loadingChat || !question.trim()}
                  className="bg-blue-600 hover:bg-blue-700 text-white text-xs flex items-center gap-1.5 px-4"
                >
                  {loadingChat ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Send className="h-3.5 w-3.5" />
                  )}
                  Synthesize
                </Button>
              </div>

              {/* Recommended Prompts */}
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
                  Investigative Quick Prompts
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {RECOMMENDED_QUESTIONS.map((rec, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleAsk(rec)}
                      disabled={loadingChat}
                      className="text-left text-[11px] px-2.5 py-1 bg-slate-100 hover:bg-blue-50 dark:bg-slate-800 dark:hover:bg-blue-950/40 text-slate-700 dark:text-slate-300 hover:text-blue-700 dark:hover:text-blue-300 rounded-md border border-slate-200 dark:border-slate-700 transition-colors"
                    >
                      {rec}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Conversation Stream */}
          {chatHistory.length > 0 && (
            <div className="space-y-4">
              {chatHistory.map((item, idx) => (
                <Card key={idx} className="border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                  <div className="bg-slate-50 dark:bg-slate-900/60 p-3.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <MessageSquare className="h-3.5 w-3.5 text-blue-600" />
                      Q: {item.q}
                    </span>
                    <button
                      onClick={() => copyText(item.a.answer, idx)}
                      className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs flex items-center gap-1"
                      title="Copy response"
                    >
                      {copiedIndex === idx ? (
                        <Check className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>

                  <CardContent className="p-4 space-y-4">
                    {/* Answer Text */}
                    <div className="text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-line bg-blue-50/40 dark:bg-blue-950/20 p-3.5 rounded-lg border border-blue-100 dark:border-blue-900/40 font-mono">
                      {item.a.answer}
                    </div>

                    {/* Grounding Sources */}
                    {item.a.sources && item.a.sources.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                        <p className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
                          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                          Verified Grounding Citations ({item.a.sources.length})
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {item.a.sources.map((src, sIdx) => (
                            <div
                              key={sIdx}
                              className="p-2.5 bg-slate-50 dark:bg-slate-900 rounded-md border border-slate-200 dark:border-slate-800 text-[11px] space-y-1"
                            >
                              <div className="flex items-center justify-between font-medium text-slate-800 dark:text-slate-200">
                                <span className="flex items-center gap-1 truncate max-w-[200px]" title={src.document_title}>
                                  <FileText className="h-3 w-3 text-blue-500" />
                                  {src.document_title}
                                </span>
                                <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 uppercase">
                                  {src.document_type}
                                </Badge>
                              </div>
                              <p className="text-slate-500 dark:text-slate-400 line-clamp-2 italic">
                                &quot;{src.snippet}&quot;
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Admissibility Disclaimer */}
                    <div className="p-2 bg-slate-100/80 dark:bg-slate-800/80 rounded text-[10px] text-slate-500 dark:text-slate-400 flex items-center justify-between">
                      <span>{item.a.disclaimer}</span>
                      <span className="font-mono text-[9px]">Case Scoped: {caseId.slice(0, 8)}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {chatHistory.length === 0 && !loadingChat && (
            <div className="text-center py-12 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl p-6">
              <Sparkles className="h-8 w-8 text-blue-400 mx-auto mb-2 opacity-50" />
              <h3 className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                No inquiries initiated yet
              </h3>
              <p className="text-[11px] text-slate-500 max-w-sm mx-auto mt-1">
                Type an investigative question above or click one of the quick prompts to synthesize intelligence from verified case documents.
              </p>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Case-Scoped Dense Vector Search */}
      {activeTab === "search" && (
        <div className="space-y-6">
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                <Search className="h-4 w-4 text-blue-600" />
                Case Semantic Search (pgvector HNSW)
              </CardTitle>
              <CardDescription className="text-xs">
                Query 768-dimensional text embeddings to retrieve relevant document excerpts based on conceptual similarity.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSearch} className="flex gap-2">
                <Input
                  placeholder="Enter concepts, e.g. ballistic projectile match, offshore money laundering, alibi witness..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="text-xs border-slate-300 dark:border-slate-700"
                />
                <Button
                  type="submit"
                  disabled={loadingSearch || !searchQuery.trim()}
                  className="bg-blue-600 hover:bg-blue-700 text-white text-xs flex items-center gap-1.5 px-4"
                >
                  {loadingSearch ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Search className="h-3.5 w-3.5" />
                  )}
                  Search Vectors
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Results List */}
          {searchResults && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>Found {searchResults.results_count} matching vector chunks for query: &quot;{searchResults.query}&quot;</span>
                <span className="font-mono text-[10px]">Case ID: {searchResults.case_id.slice(0, 8)}</span>
              </div>

              {searchResults.results.map((res, rIdx) => (
                <Card key={rIdx} className="border-slate-200 dark:border-slate-800 hover:border-blue-400 transition-colors">
                  <CardContent className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-blue-600" />
                        <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                          {res.document_title}
                        </span>
                        <Badge variant="secondary" className="text-[10px] uppercase">
                          {res.document_type}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[11px] font-medium text-slate-500">Cosine Similarity:</span>
                        <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-[10px] font-bold">
                          {(res.similarity * 100).toFixed(1)}%
                        </Badge>
                      </div>
                    </div>

                    <div className="p-3 bg-slate-50 dark:bg-slate-900/60 rounded-md border border-slate-100 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 font-mono leading-relaxed">
                      {res.chunk_text}
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-400">
                      <span>Chunk #{res.chunk_index + 1}</span>
                      <span>Doc ID: {res.document_id}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}

              {searchResults.results_count === 0 && (
                <div className="text-center py-8 text-xs text-slate-500">
                  No document chunks matched the similarity threshold. Try adjusting the search query terms.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

