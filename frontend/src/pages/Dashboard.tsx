import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  FileText,
  GraduationCap,
  Loader2,
  MessageSquare,
  Target,
} from "lucide-react";
import { api, errorMessage } from "../services/api";
import type { UserDashboard } from "../types";

const STAT_CARDS = [
  { key: "conversations", label: "Conversations", icon: MessageSquare, tone: "bg-teal-50 text-teal-700" },
  { key: "questions_asked", label: "Questions asked", icon: Target, tone: "bg-indigo-50 text-indigo-700" },
  { key: "learning_sessions", label: "Learning sessions", icon: GraduationCap, tone: "bg-amber-50 text-amber-700" },
  { key: "exams_completed", label: "Exams completed", icon: BookOpen, tone: "bg-rose-50 text-rose-700" },
];

export default function Dashboard() {
  const [data, setData] = useState<UserDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get<UserDashboard>("/dashboard/me")
      .then(({ data }) => setData(data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-400">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  const stats = data?.stats ?? {};

  return (
    <div className="mx-auto max-w-6xl p-6 md:p-8">
      <h1 className="text-2xl font-bold tracking-tight text-slate-800">Dashboard</h1>
      <p className="mt-1 text-sm text-slate-500">
        Your activity across SOPIA. Everything here comes from your real usage.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STAT_CARDS.map((card) => (
          <div
            key={card.key}
            className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${card.tone}`}>
              <card.icon size={22} />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-500">{card.label}</p>
              <p className="text-2xl font-bold text-slate-800">{stats[card.key] ?? 0}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Weak areas</h2>
          {data?.weak_topics.length ? (
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {data.weak_topics.map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                  {t}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No activity yet</p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Recommended next</h2>
          {data?.recommended_topics.length ? (
            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              {data.recommended_topics.map((t) => (
                <li key={t} className="flex items-center justify-between gap-2">
                  <span>{t}</span>
                  <button
                    onClick={() => navigate("/learn")}
                    className="text-xs font-medium text-teal-600 hover:underline"
                  >
                    Study
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No activity yet</p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Recent conversations</h2>
          {data?.recent_conversations.length ? (
            <ul className="mt-3 space-y-2">
              {data.recent_conversations.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => navigate("/chat")}
                    className="w-full truncate text-left text-sm text-slate-600 hover:text-teal-600"
                  >
                    {c.label}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No activity yet</p>
          )}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Learning sessions</h2>
          {data?.recent_learning.length ? (
            <ul className="mt-3 divide-y divide-slate-100">
              {data.recent_learning.map((s) => (
                <li key={s.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-slate-700">{s.label}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                    {s.detail}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No activity yet</p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Exam attempts</h2>
          {data?.exam_attempts.length ? (
            <ul className="mt-3 divide-y divide-slate-100">
              {data.exam_attempts.map((a) => (
                <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-slate-700">
                    {a.score}/{a.maximum_score}
                  </span>
                  <span className="text-xs font-medium text-teal-600">{a.percentage ?? 0}%</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No activity yet</p>
          )}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <button
          onClick={() => navigate("/chat")}
          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-teal-300 hover:shadow"
        >
          <MessageSquare className="text-teal-600" size={22} />
          <span className="font-medium text-slate-700">Ask about SOPs</span>
        </button>
        <button
          onClick={() => navigate("/learn")}
          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-teal-300 hover:shadow"
        >
          <GraduationCap className="text-amber-600" size={22} />
          <span className="font-medium text-slate-700">Start learning</span>
        </button>
        <button
          onClick={() => navigate("/documents")}
          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-teal-300 hover:shadow"
        >
          <FileText className="text-indigo-600" size={22} />
          <span className="font-medium text-slate-700">Knowledge base</span>
        </button>
      </div>
    </div>
  );
}
