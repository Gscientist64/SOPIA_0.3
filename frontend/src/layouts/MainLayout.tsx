import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BookOpen,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Shield,
  TrendingUp,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "../stores/auth";
import { isAdmin } from "../types";

const NAV = [
  // Available without an account, so the app opens straight into the assistant.
  { name: "Chat", href: "/chat", icon: MessageSquare, access: "all" as const },
  { name: "Interviews", href: "/interviews", icon: Users, access: "all" as const },
  // Need a registered account (they track progress against a person).
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard, access: "member" as const },
  { name: "Learn", href: "/learn", icon: GraduationCap, access: "member" as const },
  { name: "Exams", href: "/exams", icon: BookOpen, access: "member" as const },
  { name: "Progress", href: "/progress", icon: TrendingUp, access: "member" as const },
  // Administration of the knowledge base and of users.
  { name: "Knowledge Base", href: "/documents", icon: FileText, access: "admin" as const },
  { name: "Administration", href: "/admin", icon: Shield, access: "admin" as const },
];

export default function MainLayout() {
  const { user, logout, isMember: member } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const guest = user?.role === "GUEST";
  const admin = isAdmin(user);

  const items = NAV.filter((item) =>
    item.access === "all" ? true : item.access === "member" ? member : admin,
  );

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const sidebar = (
    <div className="flex h-full flex-col bg-white">
      <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
        <span className="text-xl font-bold tracking-tight text-pink-700">SOPIA</span>
        <button
          className="text-slate-400 md:hidden"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X size={20} />
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {items.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                isActive
                  ? "bg-pink-50 text-pink-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`
            }
          >
            <item.icon size={18} />
            {item.name}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-slate-200 p-3">
        {guest ? (
          <div className="rounded-lg bg-pink-50 px-3 py-3 text-center">
            <p className="text-sm font-medium text-slate-700">You're browsing as a guest</p>
            <p className="mt-1 text-xs text-slate-500">
              Create an account to unlock Learn, Exams and Progress.
            </p>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => navigate("/register")}
                className="flex-1 rounded-lg bg-pink-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-pink-700"
              >
                Sign up
              </button>
              <button
                onClick={() => navigate("/login")}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
              >
                Sign in
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-pink-600 text-white">
                <UserRound size={18} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-800">
                  {user?.full_name || user?.email}
                </p>
                <p className="truncate text-xs text-slate-500">{user?.role.replace("_", " ")}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-red-50 hover:text-red-600"
            >
              <LogOut size={18} />
              Sign out
            </button>
          </>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-slate-50">
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 md:block">{sidebar}</aside>

      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-0 h-full w-72 shadow-xl">{sidebar}</div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center gap-3 border-b border-slate-200 bg-white px-4 md:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open navigation" className="text-slate-600">
            <Menu size={22} />
          </button>
          <span className="text-lg font-bold text-pink-700">SOPIA</span>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto scroll-slim">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

