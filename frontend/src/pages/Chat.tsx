import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  Loader2,
  MessageSquarePlus,
  Pencil,
  RefreshCw,
  Search,
  Send,
  Trash2,
  X,
} from "lucide-react";
import Markdown from "../components/Markdown";
import { api, API_URL, errorMessage, tokenStore } from "../services/api";
import type { ChatModeInfo, Citation, Conversation, Message } from "../types";

interface ChunkSource {
  chunk_id: number;
  document_id: number;
  document_title?: string | null;
  section?: string | null;
  heading?: string | null;
  page?: number | null;
  content: string;
}

const MODE_BADGE: Record<string, string> = {
  SOP_MODE: "SOP",
  LEARNING_MODE: "Learn",
  EXAM_MODE: "Exam",
  INTERVIEW_MODE: "Interview",
  RESEARCH_MODE: "Research",
  COMPARE_MODE: "Compare",
};

export default function Chat() {
  const [modes, setModes] = useState<ChatModeInfo[]>([]);
  const [mode, setMode] = useState("SOP_MODE");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<ChunkSource | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async (q = "") => {
    try {
      const { data } = await api.get<Conversation[]>("/conversations", {
        params: q ? { q } : {},
      });
      setConversations(data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    api
      .get<{ modes: ChatModeInfo[] }>("/chat/modes")
      .then(({ data }) => setModes(data.modes))
      .catch(() => setModes([{ value: "SOP_MODE", label: "SOP Assistant", available: true }]));
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    const timer = setTimeout(() => loadConversations(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search, loadConversations]);

  useEffect(() => {
    if (activeId == null) {
      setMessages([]);
      return;
    }
    api
      .get<{ messages: Message[] }>(`/conversations/${activeId}`)
      .then(({ data }) => setMessages(data.messages))
      .catch((err) => setError(errorMessage(err)));
  }, [activeId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamText]);

  const send = async () => {
    const question = input.trim();
    if (!question || sending) return;
    setError("");
    setInput("");
    setSending(true);
    setStreamText("");

    setMessages((prev) => [
      ...prev,
      { id: -Date.now(), role: "user", content: question, mode, citations: [] },
    ]);

    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${tokenStore.access() ?? ""}`,
        },
        body: JSON.stringify({ message: question, mode, conversation_id: activeId }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Streaming failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let answer = "";
      let citations: Citation[] = [];

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const eventLine = block.split("\n").find((l) => l.startsWith("event:"));
          const dataLine = block.split("\n").find((l) => l.startsWith("data:"));
          if (!eventLine || !dataLine) continue;
          const event = eventLine.slice(6).trim();
          // Per the SSE spec only ONE leading space is stripped. Fully trimming
          // each delta would destroy the word boundaries between chunks.
          let payload = dataLine.slice(5);
          if (payload.startsWith(" ")) payload = payload.slice(1);

          if (event === "meta") {
            setActiveId(JSON.parse(payload).conversation_id);
          } else if (event === "delta") {
            // Deltas arrive JSON-encoded so that newlines survive intact.
            let piece = payload;
            try {
              piece = JSON.parse(payload).text ?? "";
            } catch {
              /* fall back to the raw payload */
            }
            answer += piece;
            setStreamText(answer);
          } else if (event === "citations") {
            citations = JSON.parse(payload);
          } else if (event === "error") {
            setError(JSON.parse(payload).message ?? "The AI provider reported an error.");
          }
        }
      }

      setStreamText("");
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), role: "assistant", content: answer, mode, citations },
      ]);
      loadConversations(search.trim());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  const retry = async (message: Message) => {
    if (activeId == null || sending) return;
    setSending(true);
    setError("");
    try {
      const { data } = await api.post<Message>(
        `/conversations/${activeId}/messages/${message.id}/retry`,
      );
      setMessages((prev) => prev.filter((m) => m.id !== message.id).concat(data));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  const rename = async (conversation: Conversation) => {
    const title = window.prompt("Rename conversation", conversation.title);
    if (!title) return;
    try {
      await api.patch(`/conversations/${conversation.id}`, { title });
      loadConversations(search.trim());
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const remove = async (conversation: Conversation) => {
    if (!window.confirm(`Delete "${conversation.title}"?`)) return;
    try {
      await api.delete(`/conversations/${conversation.id}`);
      if (activeId === conversation.id) {
        setActiveId(null);
        setMessages([]);
      }
      loadConversations(search.trim());
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const clear = async () => {
    if (activeId == null || !window.confirm("Clear all messages in this conversation?")) return;
    try {
      await api.post(`/conversations/${activeId}/clear`);
      setMessages([]);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const copy = async (message: Message) => {
    await navigator.clipboard.writeText(message.content);
    setCopiedId(message.id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const openSource = async (citation: Citation) => {
    if (!citation.chunk_id) return;
    try {
      const { data } = await api.get<ChunkSource>(`/documents/chunks/${citation.chunk_id}`);
      setSource(data);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const availableModes = useMemo(() => modes.filter((m) => m.available), [modes]);
  const unavailableModes = useMemo(() => modes.filter((m) => !m.available), [modes]);

  return (
    <div className="flex h-full min-h-0">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="space-y-3 border-b border-slate-200 p-3">
          <button
            onClick={() => {
              setActiveId(null);
              setMessages([]);
            }}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-600 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700"
          >
            <MessageSquarePlus size={17} />
            New conversation
          </button>
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations"
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm outline-none focus:border-teal-500"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto scroll-slim p-2">
          {conversations.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-slate-400">No conversations yet</p>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`group mb-1 flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm transition ${
                activeId === c.id ? "bg-teal-50 text-teal-800" : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              <button
                className="min-w-0 flex-1 text-left"
                onClick={() => setActiveId(c.id)}
                title={c.title}
              >
                <span className="block truncate font-medium">{c.title}</span>
                <span className="text-xs text-slate-400">{MODE_BADGE[c.mode] ?? c.mode}</span>
              </button>
              <button
                onClick={() => rename(c)}
                className="text-slate-400 opacity-0 transition group-hover:opacity-100 hover:text-teal-600"
                aria-label="Rename conversation"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => remove(c)}
                className="text-slate-400 opacity-0 transition group-hover:opacity-100 hover:text-red-500"
                aria-label="Delete conversation"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      <div className="flex min-h-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-500">Mode</span>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 outline-none focus:border-teal-500"
            >
              {availableModes.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
              {unavailableModes.length > 0 && (
                <optgroup label="Coming soon">
                  {unavailableModes.map((m) => (
                    <option key={m.value} value={m.value} disabled>
                      {m.label} (coming soon)
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>
          {messages.length > 0 && activeId != null && (
            <button
              onClick={clear}
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:bg-slate-100"
            >
              Clear conversation
            </button>
          )}
        </header>

        <div className="flex-1 overflow-y-auto scroll-slim px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.length === 0 && !streamText && (
              <div className="py-16 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600 text-white">
                  <BookOpen size={26} />
                </div>
                <h2 className="text-xl font-semibold text-slate-800">Ask SOPIA</h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                  {mode === "SOP_MODE"
                    ? "Ask a question about your organisation's SOPs. Answers are grounded in uploaded documents and cite their sources."
                    : "Ask SOPIA to teach you a topic. It will guide you step by step."}
                </p>
              </div>
            )}

            {messages.map((message) =>
              message.role === "user" ? (
                <div key={message.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-teal-600 px-4 py-3 text-white">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
                  </div>
                </div>
              ) : (
                <div key={message.id} className="flex justify-start">
                  <div className="w-full max-w-[95%] rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                    <Markdown content={message.content} />

                    {message.citations.length > 0 && (
                      <div className="mt-3 border-t border-slate-100 pt-3">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                          Sources
                        </p>
                        <div className="space-y-2">
                          {message.citations.map((c, i) => (
                            <button
                              key={i}
                              onClick={() => openSource(c)}
                              className="block w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left transition hover:border-teal-300 hover:bg-teal-50/50"
                            >
                              <span className="block text-sm font-medium text-slate-800">
                                {c.document_title}
                              </span>
                              <span className="block text-xs text-slate-500">
                                {[
                                  c.version ? `Version ${c.version}` : null,
                                  c.section ? `Section ${c.section}` : null,
                                  c.page ? `Page ${c.page}` : null,
                                ]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </span>
                              <span className="mt-1 block text-xs font-medium text-teal-600">
                                View source →
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="mt-3 flex items-center gap-3 border-t border-slate-100 pt-2">
                      <button
                        onClick={() => copy(message)}
                        className="flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-teal-600"
                      >
                        {copiedId === message.id ? <Check size={13} /> : <Copy size={13} />}
                        {copiedId === message.id ? "Copied" : "Copy"}
                      </button>
                      {activeId != null && (
                        <button
                          onClick={() => retry(message)}
                          className="flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-teal-600"
                        >
                          <RefreshCw size={13} />
                          Retry
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ),
            )}

            {streamText && (
              <div className="flex justify-start">
                <div className="w-full max-w-[95%] rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <Markdown content={streamText} />
                </div>
              </div>
            )}

            {sending && !streamText && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 size={16} className="animate-spin" />
                SOPIA is thinking…
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        {error && (
          <div className="mx-auto mb-2 w-full max-w-3xl px-4">
            <div className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <span>{error}</span>
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={16} />
              </button>
            </div>
          </div>
        )}

        <div className="border-t border-slate-200 bg-white p-4">
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={
                mode === "SOP_MODE" ? "Ask about your SOPs…" : "Ask SOPIA to teach you something…"
              }
              disabled={sending}
              className="max-h-40 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100 disabled:bg-slate-50"
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              aria-label="Send message"
            >
              {sending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      </div>

      {source && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setSource(null)} />
          <div className="relative max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <button
              onClick={() => setSource(null)}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-700"
              aria-label="Close source"
            >
              <X size={20} />
            </button>
            <h3 className="pr-8 text-lg font-semibold text-slate-800">{source.document_title}</h3>
            <p className="mt-1 text-sm text-slate-500">
              {[source.section, source.page ? `Page ${source.page}` : null]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <div className="mt-4 whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
              {source.content}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
