import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, tokenStore } from "../services/api";
import { isGuest, isMember, type User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  isGuest: boolean;
  isMember: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  /**
   * Start an anonymous session.
   *
   * The app opens straight into the assistant, so a visitor with no account is
   * given a guest session instead of being sent to a sign-in wall. Guests are
   * scoped to the organisation the deployment publishes, and the backend
   * refuses the request entirely if no such organisation is configured.
   */
  const startGuestSession = useCallback(async (): Promise<User | null> => {
    try {
      const { data } = await api.post("/auth/guest");
      tokenStore.set(data.access_token);
      return data.user as User;
    } catch {
      // Anonymous access is not enabled on this deployment: leave the visitor
      // unauthenticated so the protected routes send them to /login.
      tokenStore.clear();
      return null;
    }
  }, []);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.access()) {
      setUser(await startGuestSession());
      return;
    }
    try {
      const { data } = await api.get<User>("/auth/me");
      setUser(data);
    } catch {
      // An expired guest token is expected: replace it with a fresh session.
      tokenStore.clear();
      setUser(await startGuestSession());
    }
  }, [startGuestSession]);

  useEffect(() => {
    (async () => {
      await refreshUser();
      setLoading(false);
    })();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post("/auth/login", { email, password });
    tokenStore.set(data.access_token, data.refresh_token);
    const me = await api.get<User>("/auth/me");
    setUser(me.data);
  }, []);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const { data } = await api.post("/auth/register", {
      email,
      password,
      full_name: fullName || null,
    });
    tokenStore.set(data.access_token, data.refresh_token);
    const me = await api.get<User>("/auth/me");
    setUser(me.data);
  }, []);

  /** Signing out returns to the anonymous session rather than a dead end. */
  const logout = useCallback(async () => {
    tokenStore.clear();
    setUser(null);
    setUser(await startGuestSession());
  }, [startGuestSession]);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      register,
      logout,
      refreshUser,
      isGuest: isGuest(user),
      isMember: isMember(user),
    }),
    [user, loading, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
