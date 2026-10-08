import { useEffect, useState } from "react";
import { Loader2, TrendingUp } from "lucide-react";
import { api, errorMessage } from "../services/api";
import type { UserDashboard } from "../types";

export default function Progress() {
  const [data, setData] = useState<UserDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
  const best = (data?.exam_attempts ?? []).reduce(
    (max, a) => Math.max(max, a.percentage ?? 0),
    0,
  );

  return (
    <div className="mx-auto max-w-5xl p-6 md:p-8">
      <div className="flex items-center gap-3">
        <TrendingUp className="text-teal-600" size={26} />
        <h1 className="text-2xl font-bold tracking-tight text-slate-800">Your progress</h1>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: "Topics studied", value: stats.learning_sessions ?? 0 },
          { label: "Topics completed", value: stats.learning_completed ?? 0 },
          { label: "Exams completed", value: stats.exams_completed ?? 0 },
          { label: "Best exam score", value: `${best}%` },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-slate-500">{item.label}</p>
            <p className="mt-1 text-2xl font-bold text-slate-800">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Topics needing revision</h2>
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
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
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
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Exam history</h2>
          {data?.exam_attempts.length ? (
            <table className="mt-3 w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase text-slate-400">
                  <th className="pb-2">Score</th>
                  <th className="pb-2">Result</th>
                  <th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.exam_attempts.map((a) => (
                  <tr key={a.id}>
                    <td className="py-2 text-slate-700">
                      {a.score}/{a.maximum_score}
                    </td>
                    <td className="py-2 font-medium text-teal-600">{a.percentage ?? 0}%</td>
                    <td className="py-2 text-slate-500">{a.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No activity yet</p>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Interview practice</h2>
          {data?.interview_sessions.length ? (
            <ul className="mt-3 divide-y divide-slate-100">
              {data.interview_sessions.map((s) => (
                <li key={s.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-slate-700">{s.job_title}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                    {s.status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-slate-400">No activity yet</p>
          )}
        </section>
      </div>
    </div>
  );
}
