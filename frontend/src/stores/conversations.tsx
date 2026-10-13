import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, errorMessage } from "../services/api";
import type { Conversation } from "../types";
import { useAuth } from "./auth";

interface ConversationsContextValue {
  conversations: Conversation[];
  search: string;
  setSearch: (value: string) => void;
  activeId: number | null;
  setActiveId: (id: number | null) => void;
  /** Clear the transcript and start a fresh thread. */
  startNew: () => void;
  /** Reload the list, honouring the current search text. */
  reload: () => void;
  rename: (conversation: Conversation) => Promise<void>;
  remove: (conversation: Conversation) => Promise<void>;
  error: string;
  clearError: () => void;
}

const ConversationsContext = createContext<ConversationsContextValue | null>(null);

export function ConversationsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [search, setSearch] = useState("");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async (query: string) => {
    try {
      const { data } = await api.get<Conversation[]>("/conversations", {
        params: query ? { q: query } : {},
      });
      setConversations(data);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  // Wait for the account to settle: a guest token is issued asynchronously on
  // first load, so fetching before it exists would 401.
  useEffect(() => {
    if (!user) {
      setConversations([]);
      setActiveId(null);
      return;
    }
    load("");
    setSearch("");
    setActiveId(null);
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    const timer = setTimeout(() => load(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search, load, user]);

  const reload = useCallback(() => {
    void load(search.trim());
  }, [load, search]);

  const startNew = useCallback(() => {
    setActiveId(null);
  }, []);

  const rename = useCallback(
    async (conversation: Conversation) => {
      const title = window.prompt("Rename conversation", conversation.title);
      if (!title) return;
      try {
        await api.patch(`/conversations/${conversation.id}`, { title });
        await load(search.trim());
      } catch (err) {
        setError(errorMessage(err));
      }
    },
    [load, search],
  );

  const remove = useCallback(
    async (conversation: Conversation) => {
      if (!window.confirm(`Delete "${conversation.title}"?`)) return;
      try {
        await api.delete(`/conversations/${conversation.id}`);
        if (activeId === conversation.id) setActiveId(null);
        await load(search.trim());
      } catch (err) {
        setError(errorMessage(err));
      }
    },
    [activeId, load, search],
  );

  const value = useMemo(
    () => ({
      conversations,
      search,
      setSearch,
      activeId,
      setActiveId,
      startNew,
      reload,
      rename,
      remove,
      error,
      clearError: () => setError(""),
    }),
    [conversations, search, activeId, startNew, reload, rename, remove, error],
  );

  return <ConversationsContext.Provider value={value}>{children}</ConversationsContext.Provider>;
}

export function useConversations(): ConversationsContextValue {
  const context = useContext(ConversationsContext);
  if (!context) {
    throw new Error("useConversations must be used within a ConversationsProvider");
  }
  return context;
}
