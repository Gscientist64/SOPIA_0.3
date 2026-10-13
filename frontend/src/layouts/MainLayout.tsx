import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BookOpen,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  MessageSquarePlus,
  Pencil,
  Search,
  Shield,
  Trash2,
  TrendingUp,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "../stores/auth";
import { useConversations } from "../stores/conversations";
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

// Conversation history belongs beside the Chat and Interviews links rather than
// in a second rail, so the assistant has exactly one left sidebar.
const CHAT_ROUTES = ["/chat", "/interviews"];

const MODE_BADGE: Record<string, string> = {
  SOP_MODE: "SOP",
  LEARNING_MODE: "Learn",
  EXAM_MODE: "Exam",
  INTERVIEW_MODE: "Interview",
  RESEARCH_MODE: "Research",
  COMPARE_MODE: "Compare",
};

function ConversationPanel({ onNavigate }: { onNavigate: () => void }) {
  const {
    conversations,
    search,
    setSearch,
    activeId,
    setActiveId,
    startNew,
    rename,
    remove,
    error,
    clearError,
  } = useConversations();
  const navigate = useNavigate();

  const open = (id: number) => {
    clearError();
    setActiveId(id);
    // Selecting a thread always returns to the transcript.
    navigate("/chat");
    onNavigate();
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col border-t border-slate-200">
      <div className="space-y-2 p-3">
        <button
          onClick={() => {
            clearError();
            startNew();
            navigate("/chat");
            onNavigate();
          }}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-pink-600 py-2 text-sm font-semibold text-white transition hover:bg-pink-700"
        >
          <MessageSquarePlus size={16} />
          New conversation
        </button>
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations"
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm outline-none focus:border-pink-500"
          />
        </div>
        {error && (
          <p className="rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-700">{error}</p>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto scroll-slim px-2 pb-2">
        {conversations.length === 0 && (
          <p className="px-3 py-4 text-center text-sm text-slate-400">No conversations yet</p>
        )}
        {conversations.map((conversation) => (
          <div
            key={conversation.id}
            className={`group mb-1 flex items-center gap-1 rounded-lg px-2.5 py-2 text-sm transition ${
              activeId === conversation.id
                ? "bg-pink-50 text-pink-800"
                : "text-slate-700 hover:bg-slate-50"
            }`}
          >
            <button
              className="min-w-0 flex-1 text-left"
              onClick={() => open(conversation.id)}
              title={conversation.title}
            >
              <span className="block truncate font-medium">{conversation.title}</span>
              <span className="text-xs text-slate-400">
                {MODE_BADGE[conversation.mode] ?? conversation.mode}
              </span>
            </button>
            <button
              onClick={() => void rename(conversation)}
              className="text-slate-400 opacity-0 transition group-hover:opacity-100 hover:text-pink-600"
              aria-label="Rename conversation"
            >
              <Pencil size={14} />
            </button>
            <button
              onClick={() => void remove(conversation)}
              className="text-slate-400 opacity-0 transition group-hover:opacity-100 hover:text-red-500"
              aria-label="Delete conversation"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MainLayout() {
  const { user, logout, isMember: member } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const guest = user?.role === "GUEST";
  const admin = isAdmin(user);
  const showConversations = CHAT_ROUTES.includes(pathname);

  const items = NAV.filter((item) =>
    item.access === "all" ? true : item.access === "member" ? member : admin,
  );

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const sidebar = (
    <div className="flex h-full flex-col bg-white">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 px-5">
        <span className="text-xl font-bold tracking-tight text-pink-700">SOPIA</span>
        <button
          className="text-slate-400 md:hidden"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X size={20} />
        </button>
      </div>

      <nav
        className={`space-y-1 overflow-y-auto px-3 py-3 scroll-slim ${
          showConversations ? "shrink-0" : "flex-1"
        }`}
      >
        {items.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
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

      {showConversations && <ConversationPanel onNavigate={() => setOpen(false)} />}

      <div className="shrink-0 border-t border-slate-200 p-3">
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
      <aside className="hidden w-72 shrink-0 border-r border-slate-200 md:block">{sidebar}</aside>

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

