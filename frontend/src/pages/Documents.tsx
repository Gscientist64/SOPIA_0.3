import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  FileText,
  Loader2,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";
import { api, errorMessage } from "../services/api";
import { useAuth } from "../stores/auth";
import { isAdmin, type DocumentItem } from "../types";

const STATUS_TONE: Record<string, string> = {
  Active: "bg-teal-50 text-teal-700 border-teal-200",
  Processing: "bg-amber-50 text-amber-700 border-amber-200",
  Error: "bg-red-50 text-red-700 border-red-200",
  Draft: "bg-slate-100 text-slate-600 border-slate-200",
  Archived: "bg-slate-100 text-slate-500 border-slate-200",
};

export default function Documents() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [versionLabel, setVersionLabel] = useState("1.0");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<DocumentItem[]>("/documents/");
      setDocuments(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    if (department) form.append("department", department);
    form.append("version_label", versionLabel || "1.0");
    try {
      const { data } = await api.post<DocumentItem>("/documents/upload", form);
      const version = data.versions?.[0];
      if (version?.processing_status === "error") {
        setError(`Upload stored but processing failed: ${version.processing_error ?? "unknown error"}`);
      } else {
        setNotice(
          `"${data.title}" processed successfully (${version?.chunk_count ?? 0} chunks indexed).`,
        );
      }
      setFile(null);
      setTitle("");
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (doc: DocumentItem) => {
    if (!window.confirm(`Delete "${doc.title}" and all its versions?`)) return;
    try {
      await api.delete(`/documents/${doc.id}`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const activate = async (docId: number, versionId: number) => {
    try {
      await api.post(`/documents/${docId}/versions/${versionId}/activate`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const reprocess = async (docId: number) => {
    try {
      await api.post(`/documents/${docId}/reprocess`);
      setNotice("Reprocessing complete.");
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const loadVersions = async (doc: DocumentItem) => {
    if (expanded === doc.id) {
      setExpanded(null);
      return;
    }
    try {
      const { data } = await api.get(`/documents/${doc.id}`);
      setDocuments((prev) => prev.map((d) => (d.id === doc.id ? { ...d, versions: data.versions } : d)));
      setExpanded(doc.id);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div className="mx-auto max-w-5xl p-6 md:p-8">
      <h1 className="text-2xl font-bold tracking-tight text-slate-800">Knowledge base</h1>
      <p className="mt-1 text-sm text-slate-500">
        {admin
          ? "Upload SOPs and manage their versions. Only the active version is used for answers."
          : "Browse the SOPs available to you. Content is served with your organisation's permissions."}
      </p>

      {error && (
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-700">
          <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      {admin && (
        <form
          onSubmit={upload}
          className="mt-6 space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <h2 className="font-semibold text-slate-800">Upload a new SOP</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <label className="block md:col-span-3">
              <span className="mb-1.5 block text-sm font-medium text-slate-600">File</span>
              <input
                type="file"
                required
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setFile(f);
                  if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, ""));
                }}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-teal-50 file:px-3 file:py-1.5 file:text-teal-700"
              />
              <span className="mt-1 block text-xs text-slate-400">
                PDF, DOCX, TXT or Markdown
              </span>
            </label>
            <label className="block md:col-span-2">
              <span className="mb-1.5 block text-sm font-medium text-slate-600">Title</span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
                placeholder="Client Registration SOP"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-600">Version</span>
              <input
                value={versionLabel}
                onChange={(e) => setVersionLabel(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
                placeholder="1.0"
              />
            </label>
            <label className="block md:col-span-3">
              <span className="mb-1.5 block text-sm font-medium text-slate-600">Department</span>
              <input
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
                placeholder="Clinical Services"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={busy || !file}
            className="flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {busy ? "Uploading & indexing…" : "Upload & index"}
          </button>
        </form>
      )}

      <div className="mt-6 space-y-3">
        {loading && (
          <div className="flex items-center gap-2 p-6 text-sm text-slate-400">
            <Loader2 size={16} className="animate-spin" /> Loading documents…
          </div>
        )}
        {!loading && documents.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center">
            <FileText className="mx-auto text-slate-300" size={32} />
            <p className="mt-2 text-sm text-slate-500">
              {admin ? "No documents yet. Upload your first SOP above." : "No SOPs available yet."}
            </p>
          </div>
        )}

        {documents.map((doc) => (
          <div key={doc.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="font-semibold text-slate-800">{doc.title}</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {[
                    doc.department,
                    doc.category,
                    doc.active_version_label ? `Active v${doc.active_version_label}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "No metadata"}
                </p>
              </div>
              <span
                className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                  STATUS_TONE[doc.status] ?? STATUS_TONE.Draft
                }`}
              >
                {doc.status}
              </span>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                onClick={() => loadVersions(doc)}
                className="flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-teal-600"
              >
                <ChevronDown
                  size={14}
                  className={expanded === doc.id ? "rotate-180 transition" : "transition"}
                />
                Versions
              </button>
              {admin && (
                <>
                  <button
                    onClick={() => reprocess(doc.id)}
                    className="flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-teal-600"
                  >
                    <RefreshCw size={13} /> Reprocess
                  </button>
                  <button
                    onClick={() => remove(doc)}
                    className="flex items-center gap-1.5 text-xs font-medium text-slate-500 transition hover:text-red-600"
                  >
                    <Trash2 size={13} /> Delete
                  </button>
                </>
              )}
            </div>

            {expanded === doc.id && (
              <div className="mt-3 divide-y divide-slate-100 rounded-lg bg-slate-50 p-3">
                {(doc.versions ?? []).length === 0 && (
                  <p className="text-xs text-slate-400">No versions recorded.</p>
                )}
                {(doc.versions ?? []).map((v) => (
                  <div key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <div className="text-xs text-slate-600">
                      <span className="font-medium">v{v.version_label}</span>
                      {" · "}
                      <span
                        className={
                          v.processing_status === "error" ? "text-red-600" : "text-slate-500"
                        }
                      >
                        {v.processing_status}
                      </span>
                      {v.chunk_count != null && ` · ${v.chunk_count} chunks`}
                      {v.page_count ? ` · ${v.page_count} pages` : ""}
                      {v.is_active && (
                        <span className="ml-2 rounded-full bg-teal-100 px-2 py-0.5 text-teal-700">
                          active
                        </span>
                      )}
                      {v.processing_error && (
                        <span className="mt-1 block text-red-600">{v.processing_error}</span>
                      )}
                    </div>
                    {admin && !v.is_active && v.processing_status === "ready" && (
                      <button
                        onClick={() => activate(doc.id, v.id)}
                        className="rounded-md border border-teal-300 px-2.5 py-1 text-xs font-medium text-teal-700 transition hover:bg-teal-50"
                      >
                        Make active
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
