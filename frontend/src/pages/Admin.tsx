import { useCallback, useEffect, useState } from "react";
import { Loader2, Shield, Users } from "lucide-react";
import { api, errorMessage } from "../services/api";
import { useAuth } from "../stores/auth";
import type { AdminDashboard, Role, User } from "../types";

const ROLES: Role[] = ["SUPER_ADMIN", "CONTENT_ADMIN", "USER"];

export default function Admin() {
  const { user } = useAuth();
  const [stats, setStats] = useState<AdminDashboard | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const dashboard = await api.get<AdminDashboard>("/admin/dashboard");
      setStats(dashboard.data);
      if (user?.role === "SUPER_ADMIN") {
        const list = await api.get<User[]>("/admin/users");
        setUsers(list.data);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [user?.role]);

  useEffect(() => {
    load();
  }, [load]);

  const updateUser = async (target: User, patch: { role?: string; is_active?: boolean }) => {
    setBusyId(target.id);
    setError("");
    try {
      await api.patch(`/admin/users/${target.id}`, patch);
      const list = await api.get<User[]>("/admin/users");
      setUsers(list.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-400">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  const totals = stats?.totals ?? {};
  const documents = stats?.documents ?? {};

  return (
    <div className="mx-auto max-w-6xl p-6 md:p-8">
      <div className="flex items-center gap-3">
        <Shield className="text-teal-700" size={26} />
        <h1 className="text-2xl font-bold tracking-tight text-slate-800">Administration</h1>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Live metrics from the database. Nothing here is simulated.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-slate-400">
        System totals
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Users", value: totals.users ?? 0 },
          { label: "Conversations", value: totals.conversations ?? 0 },
          { label: "Questions asked", value: totals.questions_asked ?? 0 },
          { label: "Learning sessions", value: totals.learning_sessions ?? 0 },
          { label: "Exams completed", value: totals.exams_completed ?? 0 },
          { label: "Interviews completed", value: totals.interviews_completed ?? 0 },
          { label: "AI calls", value: stats?.engagement?.ai_calls ?? 0 },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-slate-500">{item.label}</p>
            <p className="mt-1 text-2xl font-bold text-slate-800">{item.value}</p>
          </div>
        ))}
      </div>

      <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-slate-400">
        Documents
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Total SOPs", value: documents.total ?? 0 },
          { label: "Active", value: documents.active ?? 0 },
          { label: "Processing", value: documents.processing ?? 0 },
          { label: "Failed", value: documents.errored ?? 0 },
          { label: "Versions", value: documents.versions ?? 0 },
          { label: "Chunks indexed", value: documents.chunks ?? 0 },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-slate-500">{item.label}</p>
            <p className="mt-1 text-2xl font-bold text-slate-800">{item.value}</p>
          </div>
        ))}
      </div>

      <h2 className="mt-8 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-400">
        <Users size={15} /> Recent documents
      </h2>
      <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Department</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(stats?.recent_documents ?? []).map((doc) => (
              <tr key={doc.id}>
                <td className="px-4 py-3 font-medium text-slate-700">{doc.title}</td>
                <td className="px-4 py-3 text-slate-500">{doc.department || "—"}</td>
                <td className="px-4 py-3 text-slate-500">{doc.status}</td>
              </tr>
            ))}
            {(stats?.recent_documents ?? []).length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-400">
                  No documents yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {user?.role === "SUPER_ADMIN" && (
        <>
          <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-slate-400">
            User management
          </h2>
          <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Active</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-slate-700">{u.full_name || u.email}</p>
                      <p className="text-xs text-slate-400">{u.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        disabled={busyId === u.id || u.id === user.id}
                        onChange={(e) => updateUser(u, { role: e.target.value })}
                        className="rounded-lg border border-slate-300 px-2 py-1.5 text-xs outline-none focus:border-teal-500 disabled:bg-slate-50"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        disabled={busyId === u.id || u.id === user.id}
                        onClick={() => updateUser(u, { is_active: !u.is_active })}
                        className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                          u.is_active
                            ? "bg-teal-100 text-teal-700 hover:bg-teal-200"
                            : "bg-slate-200 text-slate-600 hover:bg-slate-300"
                        } disabled:opacity-50`}
                      >
                        {u.is_active ? "Active" : "Disabled"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
