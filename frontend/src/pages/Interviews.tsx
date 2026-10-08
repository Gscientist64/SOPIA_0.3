import { useState } from "react";
import { CheckCircle2, Loader2, Send, Users } from "lucide-react";
import Markdown from "../components/Markdown";
import { api, errorMessage } from "../services/api";
import type { InterviewQuestion, InterviewSession } from "../types";

interface Feedback {
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
        Practise a realistic interview and receive structured feedback on every answer.
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
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Industry</span>
          <input
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            placeholder="Health"
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Experience level</span>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
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
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
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
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
        </label>
        <button
          onClick={start}
          disabled={busy || !jobTitle.trim()}
          className="flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300 sm:col-span-2"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          {session ? "Restart interview" : "Start mock interview"}
        </button>
      </div>

      {session && (
        <div className="mt-3 text-xs text-slate-500">
          Practising for <span className="font-medium text-slate-700">{session.job_title}</span> ·{" "}
          {session.interview_type}
        </div>
      )}

      <div className="mt-4 space-y-4">
        {entries.map((entry, i) => (
          <div key={i} className="space-y-2">
            <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
              <p className="font-medium text-slate-700">{entry.question.prompt}</p>
            </div>
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-teal-600 px-4 py-2.5 text-sm text-white">
                {entry.answer}
              </div>
            </div>
            {entry.feedback && (
              <div className="rounded-2xl border border-indigo-100 bg-indigo-50/50 px-4 py-3 text-sm">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-indigo-500">
                  Feedback
                </p>
                <Markdown content={formatFeedback(entry.feedback)} />
              </div>
            )}
          </div>
        ))}

        {current && (
          <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
            <p className="font-medium text-slate-700">{current.prompt}</p>
          </div>
        )}

        {busy && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 size={15} className="animate-spin" /> Evaluating…
          </div>
        )}
      </div>

      {current && (
        <div className="mt-4 flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <textarea
            rows={3}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Type your answer…"
            className="max-h-40 flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
          <button
            onClick={sendAnswer}
            disabled={busy || !answer.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-600 text-white transition hover:bg-teal-700 disabled:bg-slate-300"
            aria-label="Send answer"
          >
            <Send size={17} />
          </button>
        </div>
      )}

      {summary && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="text-teal-600" size={20} />
            <h2 className="font-semibold text-slate-800">Interview summary</h2>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <SummaryList title="Strengths" items={summary.strengths} tone="text-teal-700" />
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
            <li key={i}>• {item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-400">None recorded</p>
      )}
    </div>
  );
}

function formatFeedback(feedback: Feedback): string {
  if (feedback.feedback && !feedback.strengths) return feedback.feedback;
  const lines: string[] = [];
  const list = (label: string, values?: string[]) => {
    if (values && values.length) lines.push(`**${label}:** ${values.join("; ")}`);
  };
  list("Strengths", feedback.strengths);
  list("Missing points", feedback.missing_points);
  list("Weaknesses", feedback.weaknesses);
  if (feedback.accuracy) lines.push(`**Technical accuracy:** ${feedback.accuracy}`);
  if (feedback.clarity) lines.push(`**Clarity:** ${feedback.clarity}`);
  if (feedback.relevance) lines.push(`**Relevance:** ${feedback.relevance}`);
  if (feedback.suggested_answer) lines.push(`**Suggested answer:** ${feedback.suggested_answer}`);
  if (feedback.follow_up) lines.push(`**Follow-up:** ${feedback.follow_up}`);
  return lines.join("\n\n") || "No feedback returned.";
}
