import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { isAdmin } from "../types";

export function FullPageSpinner() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-teal-600" />
    </div>
  );
}

export default function ProtectedRoute({
  children,
  adminOnly = false,
}: {
  children: ReactNode;
  adminOnly?: boolean;
}) {
  const { user, loading } = useAuth();

  if (loading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin(user)) return <Navigate to="/dashboard" replace />;

  return <>{children}</>;
}
