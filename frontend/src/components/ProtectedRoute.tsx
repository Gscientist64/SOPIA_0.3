import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { isAdmin } from "../types";

export function FullPageSpinner() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-pink-600" />
    </div>
  );
}

/**
 * Route guard.
 *
 * Three levels, matching the access model:
 *   - default      : any session, including an anonymous guest (Chat, Interviews)
 *   - memberOnly   : a registered account is required (Learn, Exams, Progress)
 *   - adminOnly    : administrators only (Knowledge Base, Administration)
 *
 * A guest who hits a member-only route is sent to sign in rather than being
 * bounced elsewhere, so the reason is obvious.
 */
export default function ProtectedRoute({
  children,
  adminOnly = false,
  memberOnly = false,
}: {
  children: ReactNode;
  adminOnly?: boolean;
  memberOnly?: boolean;
}) {
  const { user, loading, isMember } = useAuth();

  if (loading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin(user)) return <Navigate to="/chat" replace />;
  if (memberOnly && !isMember) return <Navigate to="/login" replace state={{ reason: "account" }} />;

  return <>{children}</>;
}
