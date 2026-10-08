import { useRef, useState } from "react";
import { GraduationCap, Loader2, Send, Sparkles } from "lucide-react";
import Markdown from "../components/Markdown";
import { api, errorMessage } from "../services/api";
import type { LearningSession, QuizQuestion } from "../types";

interface Turn {
  role: "user" | "tutor";
  content: string;
}

interface QuizResult {
  score: number;
  maximum_score: number;
  percentage: number;
  weak_topics: string[];
  details: {
    question_id: number;
    prompt: string;
    your_answer: string | null;
    correct_answer: string | null;
    is_correct: boolean;
    explanation: string | null;
  }[];
}

export default function Learn() {
  const [topic, setTopic] = useState("");
  const [session, setSession] = useState<LearningSession | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [quiz, setQuiz] = useState<QuizQuestion[] | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const startRef = useRef<HTMLDivElement>(null);

  const startSession = async () => {
    if (!topic.trim()) return;
    setBusy(true);
    setError("");
    setQuiz(null);
    setResult(null);
    setTurns([]);
    try {
      const { data } = await api.post("/learning/sessions/start", { topic: topic.trim() });
      setSession(data.session);
      setTurns([{ role: "tutor", content: data.reply }]);
      setTimeout(() => startRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const sendTurn = async () => {
    const message = input.trim();
    if (!message || !session || busy) return;
    setInput("");
    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/learning/sessions/turn", {
        session_id: session.id,
        message,
      });
      setSession(data.session);
      setTurns((prev) => [...prev, { role: "tutor", content: data.reply }]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const generateQuiz = async () => {
    const name = session?.topic_name || topic.trim();
    if (!name) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const { data } = await api.post("/learning/quiz", {
        topic: name,
        question_count: 5,
        difficulty: "medium",
        question_type: "mcq",
        session_id: session?.id ?? null,
      });
      setQuiz(data.questions ?? []);
      setAnswers({});
      if (!data.questions?.length) setError("The AI could not generate quiz questions.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const submitQuiz = async () => {
    if (!quiz) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post<QuizResult>("/learning/quiz/submit", {
        topic: session?.topic_name || topic,
        answers: quiz.map((q) => ({ question_id: q.id, answer: answers[q.id] ?? "" })),
      });
      setResult(data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl p-6 md:p-8">
      <div className="flex items-center gap-3">
        <GraduationCap className="text-amber-600" size={26} />
        <h1 className="text-2xl font-bold tracking-tight text-slate-800">Learning mode</h1>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Ask SOPIA to teach you a topic. It breaks it into sections, explains progressively and
        checks your understanding.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && startSession()}
          placeholder="e.g. Monitoring and Evaluation"
          className="min-w-[220px] flex-1 rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
        />
        <button
          onClick={startSession}
          disabled={busy || !topic.trim()}
          className="flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          {session ? "Restart" : "Start learning"}
        </button>
      </div>

      <div ref={startRef} />

      {session && (
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="rounded-full bg-amber-50 px-3 py-1 font-medium text-amber-700">
            {session.topic_name}
          </span>
          <span>{session.total_sections} sections</span>
          <span>{session.status}</span>
          <button
            onClick={generateQuiz}
            disabled={busy}
            className="ml-auto rounded-lg border border-teal-300 px-3 py-1.5 text-xs font-semibold text-teal-700 transition hover:bg-teal-50"
          >
            Generate quiz
          </button>
        </div>
      )}

      <div className="mt-4 space-y-4">
        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-teal-600 px-4 py-2.5 text-sm text-white">
                {turn.content}
              </div>
            </div>
          ) : (
            <div
              key={i}
              className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm"
            >
              <Markdown content={turn.content} />
            </div>
          ),
        )}
        {busy && !quiz && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Loader2 size={15} className="animate-spin" /> SOPIA is preparing…
          </div>
        )}
      </div>

      {session && (
        <div className="mt-4 flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendTurn();
              }
            }}
            placeholder="Answer or ask a follow-up…"
            className="max-h-32 flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-teal-500"
          />
          <button
            onClick={sendTurn}
            disabled={busy || !input.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-600 text-white transition hover:bg-teal-700 disabled:bg-slate-300"
            aria-label="Send"
          >
            <Send size={17} />
          </button>
        </div>
      )}

      {quiz && quiz.length > 0 && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Quick quiz</h2>
          <div className="mt-4 space-y-5">
            {quiz.map((q, index) => (
              <div key={q.id}>
                <p className="text-sm font-medium text-slate-700">
                  {index + 1}. {q.prompt}
                </p>
                <div className="mt-2 space-y-1.5">
                  {q.options.length > 0 ? (
                    q.options.map((opt) => (
                      <label
                        key={opt}
                        className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-50"
                      >
                        <input
                          type="radio"
                          name={`q-${q.id}`}
                          value={opt}
                          checked={answers[q.id] === opt}
                          onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                          className="accent-teal-600"
                        />
                        {opt}
                      </label>
                    ))
                  ) : (
                    <input
                      value={answers[q.id] ?? ""}
                      onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder="Your answer"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-500"
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
          <button
            onClick={submitQuiz}
            disabled={busy}
            className="mt-5 flex items-center gap-2 rounded-lg bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-700 disabled:bg-slate-300"
          >
            {busy && <Loader2 size={16} className="animate-spin" />}
            Submit quiz
          </button>
        </div>
      )}

      {result && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold text-slate-800">Quiz results</h2>
          <p className="mt-2 text-3xl font-bold text-teal-700">{result.percentage}%</p>
          <p className="text-sm text-slate-500">
            {result.score} of {result.maximum_score} correct
          </p>
          {result.weak_topics.length > 0 && (
            <p className="mt-2 text-sm text-slate-600">
              Revise: <span className="font-medium">{result.weak_topics.join(", ")}</span>
            </p>
          )}
          <div className="mt-4 space-y-3">
            {result.details.map((d, i) => (
              <div
                key={i}
                className={`rounded-lg border p-3 text-sm ${
                  d.is_correct
                    ? "border-teal-200 bg-teal-50/60"
                    : "border-rose-200 bg-rose-50/60"
                }`}
              >
                <p className="font-medium text-slate-700">{d.prompt}</p>
                <p className="mt-1 text-slate-600">
                  Your answer: <span className="font-medium">{d.your_answer || "—"}</span>
                </p>
                {!d.is_correct && (
                  <p className="text-slate-600">
                    Correct: <span className="font-medium">{d.correct_answer}</span>
                  </p>
                )}
                {d.explanation && <p className="mt-1 text-slate-500">{d.explanation}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
