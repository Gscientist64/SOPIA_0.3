import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BookOpen, Loader2 } from "lucide-react";
import { useAuth } from "../stores/auth";
import { errorMessage } from "../services/api";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await register(email.trim(), password, fullName.trim());
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600 text-white shadow-lg">
            <BookOpen size={28} />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-800">Create your account</h1>
          <p className="mt-1 text-sm text-slate-500">
            The first account created becomes the administrator.
          </p>
        </div>

        <form
          onSubmit={submit}
          className="space-y-5 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
        >
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-600">Full name</span>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-800 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
              placeholder="Jane Doe"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-600">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-800 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
              placeholder="you@organisation.com"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-600">
              Password (min 8 characters)
            </span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-800 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100"
              placeholder="••••••••"
            />
          </label>

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-600 py-2.5 font-semibold text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {busy && <Loader2 size={18} className="animate-spin" />}
            {busy ? "Creating account…" : "Create account"}
          </button>

          <p className="text-center text-sm text-slate-500">
            Already registered?{" "}
            <Link to="/login" className="font-medium text-teal-600 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
