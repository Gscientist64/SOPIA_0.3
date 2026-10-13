import { useState } from "react";
import { CheckCircle2, Loader2, Send, Users } from "lucide-react";
import Markdown from "../components/Markdown";
import Sources from "../components/Sources";
import { api, errorMessage } from "../services/api";
import type { InterviewQuestion, InterviewSession } from "../types";

interface Feedback {
  score?: number;
  strengths?: string[];
  weaknesses?: string[];
  missing_points?: string[];
  clarity?: string;
  accuracy?: string;
  relevance?: string;
  suggested_answer?: string;
  follow_up?: string;
  feedback?: string;
}

interface Entry {
  question: InterviewQuestion;
  answer: string;
  feedback: Feedback | null;
}

interface Summary {
  strengths?: string[];
  weak_areas?: string[];
  difficult_questions?: string[];
  recommended_topics?: string[];
  questions_answered?: number;
}

const LEVELS = ["entry", "mid", "senior", "lead"];
const TYPES = ["behavioral", "technical", "competency", "mixed"];

export default function Interviews() {
  const [jobTitle, setJobTitle] = useState("");
  const [industry, setIndustry] = useState("");
  const [level, setLevel] = useState("mid");
  const [type, setType] = useState("mixed");
  const [topics, setTopics] = useState("");

  const [session, setSession] = useState<InterviewSession | null>(null);
  const [current, setCurrent] = useState<InterviewQuestion | null>(null);
  const [total, setTotal] = useState(0);
  const [answer, setAnswer] = useState("");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const start = async () => {
    if (!jobTitle.trim()) return;
    setBusy(true);
    setError("");
    setEntries([]);
    setSummary(null);
    try {
      const { data } = await api.post("/interviews/start", {
        job_title: jobTitle.trim(),
        industry: industry || null,
        experience_level: level,
        interview_type: type,
        topics: topics || null,
      });
      setSession({ id: data.session_id, job_title: data.job_title, interview_type: type, status: "active" });
      setCurrent(data.question);
      setTotal(data.total_questions ?? 0);
      setAnswer("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const sendAnswer = async () => {
    const text = answer.trim();
    if (!text || !session || !current || busy) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post(`/interviews/${session.id}/answer`, { answer: text });
      setEntries((prev) => [
        ...prev,
        { question: current, answer: text, feedback: data.feedback ?? null },
      ]);
      setAnswer("");
      if (data.done) {
        setCurrent(null);
        setSummary(data.summary ?? null);
        if (!data.summary) {
          const res = await api.get(`/interviews/${session.id}/summary`);
          setSummary(res.data);
        }
      } else {
        setCurrent(data.next_question);
        if (data.total_questions) setTotal(data.total_questions);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <div className="flex items-center gap-3">
        <Users className="text-indigo-600" size={26} />
        <h1 className="text-2xl font-bold tracking-tight text-slate-800">Interview practice</h1>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Practise a realistic interview that gets harder as you go, and see a stronger
        answer after every reply.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2">
        <label className="block sm:col-span-2">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Job title</span>
          <input
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            placeholder="e.g. Monitoring and Evaluation Officer"
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-pink-500"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Industry</span>
          <input
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            placeholder="Health"
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-pink-500"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Experience level</span>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-pink-500"
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Interview type</span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-pink-500"
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Focus topics</span>
          <input
            value={topics}
            onChange={(e) => setTopics(e.target.value)}
            placeholder="data analysis, reporting"
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-pink-500"
          />
        </label>
        <button
          onClick={start}
          disabled={busy || !jobTitle.trim()}
          className="flex items-center justify-center gap-2 rounded-lg bg-pink-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-pink-700 disabled:cursor-not-allowed disabled:bg-slate-300 sm:col-span-2"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          {session ? "Restart interview" : "Start mock interview"}
        </button>
      </div>

      {session && (
        <div className="mt-3 text-xs text-slate-500">
          Practising for <span className="font-medium text-slate-700">{session.job_title}</span> Â·{" "}
          {session.interview_type}
        </div>
      )}

      <div className="mt-4 space-y-4">
        {entries.map((entry, i) => (
          <div key={i} className="space-y-2">
            <QuestionBubble question={entry.question} />
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-pink-600 px-4 py-2.5 text-sm text-white">
                {entry.answer}
              </div>
            </div>
            {entry.feedback && <FeedbackCard feedback={entry.feedback} />}
          </div>
        ))}

        {current && <QuestionBubble question={current} total={total} />}

        {busy && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 size={15} className="animate-spin" /> Evaluatingâ€¦
          </div>
        )}
      </div>

      {current && (
        <div className="mt-4 flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <textarea
            rows={3}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type your answerâ€¦"
            className="max-h-40 flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-pink-500"
          />
          <button
            onClick={sendAnswer}
            disabled={busy || !answer.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-pink-600 text-white transition hover:bg-pink-700 disabled:bg-slate-300"
            aria-label="Send answer"
          >
            <Send size={17} />
          </button>
        </div>
      )}

      {summary && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="text-pink-600" size={20} />
            <h2 className="font-semibold text-slate-800">Interview summary</h2>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <SummaryList title="Strengths" items={summary.strengths} tone="text-pink-700" />
            <SummaryList title="Areas to improve" items={summary.weak_areas} tone="text-rose-600" />
            <SummaryList
              title="Difficult questions"
              items={summary.difficult_questions}
              tone="text-slate-600"
            />
            <SummaryList
              title="Recommended study topics"
              items={summary.recommended_topics}
              tone="text-indigo-600"
            />
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryList({
  title,
  items,
  tone,
}: {
  title: string;
  items?: string[];
  tone: string;
}) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      {items && items.length ? (
        <ul className={`mt-2 space-y-1 text-sm ${tone}`}>
          {items.map((item, i) => (
            <li key={i}>â€¢ {item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-400">None recorded</p>
      )}
    </div>
  );
}

const DIFFICULTY_STYLE: Record<string, string> = {
  "warm-up": "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  challenging: "bg-rose-50 text-rose-700 border-rose-200",
};

function DifficultyBadge({ difficulty }: { difficulty?: string | null }) {
  if (!difficulty) return null;
  const label = difficulty === "warm-up" ? "Warm-up" : difficulty[0].toUpperCase() + difficulty.slice(1);
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        DIFFICULTY_STYLE[difficulty.toLowerCase()] ?? "bg-slate-50 text-slate-600 border-slate-200"
      }`}
    >
      {label}
    </span>
  );
}

function QuestionBubble({ question, total }: { question: InterviewQuestion; total?: number }) {
  const number = question.order_index + 1;
  return (
    <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-pink-600">
          {total ? `Question ${number} of ${total}` : `Question ${number}`}
        </span>
        <DifficultyBadge difficulty={question.difficulty} />
      </div>
      {total ? (
        <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-pink-500 transition-all"
            style={{ width: `${Math.round((number / total) * 100)}%` }}
          />
        </div>
      ) : null}
      <p className="font-medium text-slate-700">{question.prompt}</p>
      <Sources citations={question.citations} className="mt-2" />
    </div>
  );
}

function FeedbackCard({ feedback }: { feedback: Feedback }) {
  // Older sessions stored a single prose blob instead of structured feedback.
  if (feedback.feedback && !feedback.strengths) {
    return (
      <div className="rounded-2xl border border-pink-100 bg-pink-50/40 px-4 py-3 text-sm">
        <Markdown content={feedback.feedback} />
      </div>
    );
  }

  const score = typeof feedback.score === "number" ? feedback.score : null;
  const details = [
    feedback.missing_points?.length ? ["Worth adding", feedback.missing_points] : null,
    feedback.weaknesses?.length ? ["Could be stronger", feedback.weaknesses] : null,
  ].filter(Boolean) as [string, string[]][];

  return (
    <div className="overflow-hidden rounded-2xl border border-pink-100 bg-white text-sm shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-pink-100 bg-pink-50/50 px-4 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-pink-600">Feedback</span>
        {score !== null && (
          <span className="rounded-full bg-white px-2.5 py-0.5 text-xs font-semibold text-pink-700 ring-1 ring-pink-200">
            {score}/5
          </span>
        )}
      </div>

      <div className="space-y-3 px-4 py-3">
        {feedback.strengths?.length ? (
          <ul className="space-y-1 text-slate-600">
            {feedback.strengths.slice(0, 3).map((item, i) => (
              <li key={i} className="flex gap-2">
                <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-pink-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-slate-500">Thanks — here is how that answer would land.</p>
        )}

        {feedback.suggested_answer && (
          <div className="rounded-xl border border-pink-200 bg-pink-50/60 px-3.5 py-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-pink-700">
              A stronger answer
            </p>
            <Markdown content={feedback.suggested_answer} />
          </div>
        )}

        {feedback.follow_up && (
          <p className="text-xs text-slate-500">
            <span className="font-medium text-slate-600">They may follow up with:</span>{" "}
            {feedback.follow_up}
          </p>
        )}

        {(details.length > 0 || feedback.accuracy || feedback.clarity || feedback.relevance) && (
          <details className="group">
            <summary className="cursor-pointer list-none text-xs font-medium text-slate-500 hover:text-pink-600">
              <span className="group-open:hidden">Show more detail</span>
              <span className="hidden group-open:inline">Hide detail</span>
            </summary>
            <div className="mt-2 space-y-2 border-t border-slate-100 pt-2 text-slate-600">
              {details.map(([label, items]) => (
                <div key={label}>
                  <p className="text-xs font-semibold text-slate-500">{label}</p>
                  <ul className="mt-1 space-y-1">
                    {items.slice(0, 3).map((item, i) => (
                      <li key={i}>• {item}</li>
                    ))}
                  </ul>
                </div>
              ))}
              {(feedback.accuracy || feedback.clarity || feedback.relevance) && (
                <dl className="grid grid-cols-1 gap-1 sm:grid-cols-3">
                  {feedback.accuracy && <Rating label="Accuracy" value={feedback.accuracy} />}
                  {feedback.clarity && <Rating label="Clarity" value={feedback.clarity} />}
                  {feedback.relevance && <Rating label="Relevance" value={feedback.relevance} />}
                </dl>
              )}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function Rating({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-slate-500">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
