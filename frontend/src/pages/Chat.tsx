import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  Loader2,
  RefreshCw,
  Send,
  X,
} from "lucide-react";
import Markdown from "../components/Markdown";
import { api, API_URL, errorMessage, tokenStore } from "../services/api";
import { useConversations } from "../stores/conversations";
import type { Citation, Message } from "../types";

interface ChunkSource {
  chunk_id: number;
  document_id: number;
  document_title?: string | null;
  section?: string | null;
  heading?: string | null;
  page?: number | null;
  content: string;
}

// The assistant always answers from the SOPs. Learning, exams and interviews
// have their own pages now, so the old mode selector only invited confusion.
const CHAT_MODE = "SOP_MODE";

export default function Chat() {
  const { activeId, setActiveId, reload } = useConversations();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState("");
  const [source, setSource] = useState<ChunkSource | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

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
      { id: -Date.now(), role: "user", content: question, mode: CHAT_MODE, citations: [] },
    ]);

    try {
      const response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${tokenStore.access() ?? ""}`,
        },
        body: JSON.stringify({ message: question, mode: CHAT_MODE, conversation_id: activeId }),
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
        { id: Date.now(), role: "assistant", content: answer, mode: CHAT_MODE, citations },
      ]);
      reload();
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









  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-h-0 flex-1 flex-col">
        {messages.length > 0 && activeId != null && (
          <header className="flex items-center justify-end border-b border-slate-200 bg-white px-4 py-2">
            <button
              onClick={clear}
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:bg-slate-100"
            >
              Clear conversation
            </button>
          </header>
        )}

        <div className="flex-1 overflow-y-auto scroll-slim px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.length === 0 && !streamText && (
              <div className="py-16 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-pink-600 text-white">
                  <BookOpen size={26} />
                </div>
                <h2 className="text-xl font-semibold text-slate-800">Ask SOPIA</h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                  Ask a question about your organisation's SOPs. Answers are grounded in
                  uploaded documents and cite their sources.
                </p>
              </div>
            )}

            {messages.map((message) =>
              message.role === "user" ? (
                <div key={message.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-pink-600 px-4 py-3 text-white">
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
                              className="block w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left transition hover:border-pink-300 hover:bg-pink-50/50"
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
                                  .join(" Â· ")}
                              </span>
                              <span className="mt-1 block text-xs font-medium text-pink-600">
                                View source â†’
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="mt-3 flex items-center gap-3 border-t border-slate-100 pt-2">
                      <button
                        onClick={() => copy(message)}
                        className="flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-pink-600"
                      >
                        {copiedId === message.id ? <Check size={13} /> : <Copy size={13} />}
                        {copiedId === message.id ? "Copied" : "Copy"}
                      </button>
                      {activeId != null && (
                        <button
                          onClick={() => retry(message)}
                          className="flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-pink-600"
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
                SOPIA is thinkingâ€¦
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
              placeholder="Ask about your SOPs"
              disabled={sending}
              className="max-h-40 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-pink-500 focus:ring-2 focus:ring-pink-100 disabled:bg-slate-50"
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-pink-600 text-white transition hover:bg-pink-700 disabled:cursor-not-allowed disabled:bg-slate-300"
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
                .join(" Â· ")}
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
