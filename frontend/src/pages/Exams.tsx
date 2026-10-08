import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, Clock, Loader2 } from "lucide-react";
import { api, errorMessage } from "../services/api";
import type { ExamResult, ExamStart } from "../types";

const DIFFICULTIES = ["easy", "medium", "hard"];
const TYPES = [
  { value: "mcq", label: "Multiple choice" },
  { value: "true_false", label: "True / false" },
  { value: "short_answer", label: "Short answer" },
  { value: "scenario", label: "Scenario-based" },
];

export default function Exams() {
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [count, setCount] = useState(5);
  const [questionType, setQuestionType] = useState("mcq");
  const [timeLimit, setTimeLimit] = useState(15);

  const [exam, setExam] = useState<ExamStart | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [marked, setMarked] = useState<Set<number>>(new Set());
  const [index, setIndex] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [result, setResult] = useState<ExamResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!exam || result || secondsLeft == null) return;
    if (secondsLeft <= 0) {
      void submit(true);
      return;
    }
    const timer = setTimeout(() => setSecondsLeft((s) => (s == null ? null : s - 1)), 1000);
    return () => clearTimeout(timer);
  }, [exam, secondsLeft, result]);

  const generate = async () => {
    if (!topic.trim()) return;
    setBusy(true);
    setError("");
    setResult(null);
    setAnswers({});
    setMarked(new Set());
    setIndex(0);
    try {
      const { data } = await api.post<ExamStart>("/exams/generate", {
        topic: topic.trim(),
        difficulty,
        question_count: count,
        question_type: questionType,
        time_limit_minutes: timeLimit,
      });
      setExam(data);
      setSecondsLeft(data.exam.time_limit_minutes * 60);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const submit = async (auto = false) => {
    if (!exam) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<ExamResult>(
        `/exams/attempts/${exam.attempt_id}/submit`,
        {
          answers: exam.questions.map((q) => ({
            question_id: q.id,
            answer: answers[q.id] ?? "",
          })),
        },
      );
      setResult(data);
      setSecondsLeft(null);
      if (auto) setError("Time expired — the exam was submitted automatically.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const toggleMark = (questionId: number) => {
    setMarked((prev) => {
      const next = new Set(prev);
      if (next.has(questionId)) next.delete(questionId);
      else next.add(questionId);
      return next;
    });
  };

  const formatTime = (total: number) => {
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const current = exam?.questions[index];

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <div className="flex items-center gap-3">
        <BookOpen className="text-rose-600" size={26} />
        <h1 className="text-2xl font-bold tracking-tight text-slate-800">Exam mode</h1>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Generate a timed mock examination, then review your score, explanations and weak topics.
      </p>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle size={17} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-2">
        <label className="block sm:col-span-2">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Topic</span>
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g. Client registration"
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Difficulty</span>
          <select
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          >
            {DIFFICULTIES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Question type</span>
          <select
            value={questionType}
            onChange={(e) => setQuestionType(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Questions</span>
          <input
            type="number"
            min={1}
            max={30}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-600">Time limit (minutes)</span>
          <input
            type="number"
            min={1}
            max={240}
            value={timeLimit}
            onChange={(e) => setTimeLimit(Number(e.target.value))}
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
        </label>
        <button
          onClick={generate}
          disabled={busy || !topic.trim()}
          className="flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300 sm:col-span-2"
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <BookOpen size={16} />}
          Start mock exam
        </button>
      </div>

      {exam && !result && current && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
            <span className="text-sm font-medium text-slate-600">
              Question {index + 1} of {exam.questions.length}
            </span>
            <span
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ${
                secondsLeft != null && secondsLeft < 60
                  ? "bg-rose-50 text-rose-600"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              <Clock size={15} />
              {secondsLeft != null ? formatTime(secondsLeft) : "--:--"}
            </span>
          </div>

          <p className="mt-4 text-sm font-medium text-slate-800">{current.prompt}</p>

          <div className="mt-3 space-y-2">
            {current.options.length > 0 ? (
              current.options.map((opt) => (
                <label
                  key={opt}
                  className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition ${
                    answers[current.id] === opt
                      ? "border-teal-400 bg-teal-50 text-teal-800"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name={`eq-${current.id}`}
                    checked={answers[current.id] === opt}
                    onChange={() => setAnswers((prev) => ({ ...prev, [current.id]: opt }))}
                    className="accent-teal-600"
                  />
                  {opt}
                </label>
              ))
            ) : (
              <textarea
                rows={3}
                value={answers[current.id] ?? ""}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [current.id]: e.target.value }))}
                placeholder="Type your answer…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
              />
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              onClick={() => setIndex((i) => Math.max(0, i - 1))}
              disabled={index === 0}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setIndex((i) => Math.min(exam.questions.length - 1, i + 1))}
              disabled={index === exam.questions.length - 1}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-40"
            >
              Next
            </button>
            <button
              onClick={() => toggleMark(current.id)}
              className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
                marked.has(current.id)
                  ? "border-amber-300 bg-amber-50 text-amber-700"
                  : "border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {marked.has(current.id) ? "Unmark" : "Mark for review"}
            </button>
            <button
              onClick={() => submit(false)}
              disabled={busy}
              className="ml-auto flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:bg-slate-300"
            >
              {busy && <Loader2 size={15} className="animate-spin" />}
              Submit exam
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {exam.questions.map((q, i) => (
              <button
                key={q.id}
                onClick={() => setIndex(i)}
                className={`h-8 w-8 rounded-md text-xs font-semibold transition ${
                  i === index
                    ? "bg-teal-600 text-white"
                    : marked.has(q.id)
                      ? "bg-amber-100 text-amber-700"
                      : answers[q.id]
                        ? "bg-teal-100 text-teal-700"
                        : "bg-slate-100 text-slate-500"
                }`}
              >
                {i + 1}
              </button>
            ))}
          </div>
        </div>
      )}

      {result && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Results</h2>
          <p className="mt-2 text-3xl font-bold text-teal-700">{result.percentage}%</p>
          <p className="text-sm text-slate-500">
            {result.score} of {result.maximum_score} correct
          </p>
          {result.weak_topics.length > 0 && (
            <p className="mt-2 text-sm text-slate-600">
              Recommended revision: <span className="font-medium">{result.weak_topics.join(", ")}</span>
            </p>
          )}
          <div className="mt-4 space-y-3">
            {result.details.map((d, i) => (
              <div
                key={i}
                className={`rounded-lg border p-3 text-sm ${
                  d.is_correct ? "border-teal-200 bg-teal-50/60" : "border-rose-200 bg-rose-50/60"
                }`}
              >
                <p className="font-medium text-slate-700">{d.prompt}</p>
                <p className="mt-1 text-slate-600">
                  Your answer: <span className="font-medium">{d.your_answer || "—"}</span>
                </p>
                {!d.is_correct && d.correct_answer && (
                  <p className="text-slate-600">
                    Correct: <span className="font-medium">{d.correct_answer}</span>
                  </p>
                )}
                {d.explanation && <p className="mt-1 text-slate-500">{d.explanation}</p>}
              </div>
            ))}
          </div>
          <button
            onClick={() => {
              setExam(null);
              setResult(null);
            }}
            className="mt-5 rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
          >
            Start another exam
          </button>
        </div>
      )}
    </div>
  );
}
