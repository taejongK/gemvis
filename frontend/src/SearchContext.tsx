import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from './api';
import type { ChatFile, SearchFileContext, WebResult } from './types';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatDebugEntry {
  question: string;
  intent_type: 'general' | 'file_search';
  files: ChatFile[];
  web?: WebResult[];
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  debugLog: ChatDebugEntry[];
  searchContext: SearchFileContext | null;
  createdAt: number;
  updatedAt: number;
}

interface SearchContextValue {
  // Backwards-compatible shorthand for the active session.
  messages: ChatMessage[];
  debugLog: ChatDebugEntry[];
  input: string;
  setInput: (v: string) => void;
  loading: boolean;
  send: (question: string) => Promise<void>;
  reset: () => void;

  // Session management.
  sessions: ChatSession[];
  activeSessionId: string | null;
  newSession: () => void;
  selectSession: (id: string) => void;
  deleteSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;

  // Spotlight integration.
  sendFromSpotlight: (question: string, answer: string, files: ChatFile[]) => void;
}

const SearchContext = createContext<SearchContextValue | null>(null);

const SESSIONS_KEY = 'gemvis.chat.sessions';
const ACTIVE_KEY = 'gemvis.chat.activeSessionId';
const TITLE_FALLBACK = 'New chat';
const TITLE_MAX = 36;

const newId = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

const titleFromMessage = (text: string): string => {
  const trimmed = text.trim().replace(/\s+/g, ' ');
  if (!trimmed) return TITLE_FALLBACK;
  return trimmed.length > TITLE_MAX ? `${trimmed.slice(0, TITLE_MAX - 1)}…` : trimmed;
};

const blankSession = (): ChatSession => {
  const now = Date.now();
  return {
    id: newId(),
    title: TITLE_FALLBACK,
    messages: [],
    debugLog: [],
    searchContext: null,
    createdAt: now,
    updatedAt: now,
  };
};

const loadSessions = (): { sessions: ChatSession[]; activeId: string | null } => {
  if (typeof window === 'undefined') {
    const s = blankSession();
    return { sessions: [s], activeId: s.id };
  }
  try {
    const raw = window.localStorage.getItem(SESSIONS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const cleaned: ChatSession[] = parsed
          .filter((s) => s && typeof s.id === 'string' && Array.isArray(s.messages))
          .map((s) => ({
            id: String(s.id),
            title: typeof s.title === 'string' && s.title ? s.title : TITLE_FALLBACK,
            messages: s.messages.filter(
              (m: any) => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string',
            ),
            debugLog: Array.isArray(s.debugLog) ? s.debugLog : [],
            searchContext: s.searchContext ?? null,
            createdAt: typeof s.createdAt === 'number' ? s.createdAt : Date.now(),
            updatedAt: typeof s.updatedAt === 'number' ? s.updatedAt : Date.now(),
          }));
        if (cleaned.length > 0) {
          const storedActive = window.localStorage.getItem(ACTIVE_KEY);
          const activeId = storedActive && cleaned.some((c) => c.id === storedActive)
            ? storedActive
            : cleaned[0].id;
          return { sessions: cleaned, activeId };
        }
      }
    }
  } catch {
    // ignore
  }
  const fresh = blankSession();
  return { sessions: [fresh], activeId: fresh.id };
};

export function SearchProvider({ children }: { children: ReactNode }) {
  const initial = useRef(loadSessions()).current;
  const [sessions, setSessions] = useState<ChatSession[]>(initial.sessions);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(initial.activeId);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  // Persist sessions whenever they change.
  useEffect(() => {
    try {
      window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    } catch {
      // quota / private mode — fall through
    }
  }, [sessions]);

  useEffect(() => {
    if (!activeSessionId) return;
    try {
      window.localStorage.setItem(ACTIVE_KEY, activeSessionId);
    } catch {
      // ignore
    }
  }, [activeSessionId]);

  const activeSession = useMemo<ChatSession | null>(
    () => sessions.find((s) => s.id === activeSessionId) ?? sessions[0] ?? null,
    [sessions, activeSessionId],
  );

  const updateActiveSession = useCallback(
    (mutate: (s: ChatSession) => ChatSession) => {
      setSessions((prev) => {
        const id = activeSessionId ?? prev[0]?.id;
        if (!id) return prev;
        return prev.map((s) => (s.id === id ? mutate(s) : s));
      });
    },
    [activeSessionId],
  );

  const send = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (!q || loading) return;

      const currentMessages = activeSession?.messages ?? [];
      const userMsg: ChatMessage = { role: 'user', content: q };
      const allMessages = [...currentMessages, userMsg];

      // Add user message + empty assistant placeholder immediately.
      updateActiveSession((s) => {
        const isFirst = s.messages.length === 0;
        return {
          ...s,
          title: isFirst ? titleFromMessage(q) : s.title,
          messages: [...s.messages, userMsg, { role: 'assistant' as const, content: '' }],
          updatedAt: Date.now(),
        };
      });
      setInput('');
      setLoading(true);

      let intentType: 'general' | 'file_search' = 'general';
      let files: ChatFile[] = [];
      let web: WebResult[] = [];
      let answer = '';

      try {
        for await (const event of api.chatStream(allMessages, activeSession?.searchContext)) {
          if (event.type === 'meta') {
            intentType = event.intent_type;
            files = event.files ?? [];
            web = event.web ?? [];
            if (intentType === 'file_search' && files.length > 0) {
              updateActiveSession((s) => ({
                ...s,
                searchContext: { query: q, files },
              }));
            }
            setLoading(false);
          } else if (event.type === 'chunk') {
            answer += event.text;
            updateActiveSession((s) => {
              const msgs = [...s.messages];
              if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
                msgs[msgs.length - 1] = { role: 'assistant', content: answer };
              }
              return { ...s, messages: msgs, updatedAt: Date.now() };
            });
          } else if (event.type === 'error') {
            answer = event.text || '오류가 발생했습니다. 다시 시도해주세요.';
            updateActiveSession((s) => {
              const msgs = [...s.messages];
              if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
                msgs[msgs.length - 1] = { role: 'assistant', content: answer };
              }
              return { ...s, messages: msgs, updatedAt: Date.now() };
            });
          }
        }
      } catch {
        updateActiveSession((s) => {
          const msgs = [...s.messages];
          if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
            msgs[msgs.length - 1] = { role: 'assistant', content: '오류가 발생했습니다. 다시 시도해주세요.' };
          }
          return { ...s, messages: msgs, updatedAt: Date.now() };
        });
      } finally {
        setLoading(false);
        updateActiveSession((s) => ({
          ...s,
          debugLog: [...s.debugLog, { question: q, intent_type: intentType, files, web }],
          updatedAt: Date.now(),
        }));
      }
    },
    [loading, activeSession, updateActiveSession],
  );

  // reset = clear messages of the active session (kept for back-compat with existing UI).
  const reset = useCallback(() => {
    updateActiveSession((s) => ({
      ...s,
      title: TITLE_FALLBACK,
      messages: [],
      debugLog: [],
      searchContext: null,
      updatedAt: Date.now(),
    }));
    setInput('');
  }, [updateActiveSession]);

  const newSession = useCallback(() => {
    const s = blankSession();
    setSessions((prev) => [s, ...prev]);
    setActiveSessionId(s.id);
    setInput('');
  }, []);

  const selectSession = useCallback((id: string) => {
    setActiveSessionId(id);
    setInput('');
  }, []);

  const deleteSession = useCallback((id: string) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      // Always keep at least one session so the UI never has a null state.
      if (next.length === 0) {
        const fresh = blankSession();
        setActiveSessionId(fresh.id);
        return [fresh];
      }
      // If we deleted the active one, fall back to the most-recently-updated.
      if (id === activeSessionId) {
        const fallback = [...next].sort((a, b) => b.updatedAt - a.updatedAt)[0];
        setActiveSessionId(fallback.id);
      }
      return next;
    });
  }, [activeSessionId]);

  const renameSession = useCallback((id: string, title: string) => {
    const cleaned = title.trim().slice(0, 80) || TITLE_FALLBACK;
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, title: cleaned, updatedAt: Date.now() } : s)),
    );
  }, []);

  const sendFromSpotlight = useCallback(
    (question: string, answer: string, files: ChatFile[]) => {
      const userMsg: ChatMessage = { role: 'user', content: question };
      const assistantMsg: ChatMessage = { role: 'assistant', content: answer };
      const intentType: 'file_search' = 'file_search';

      updateActiveSession((s) => {
        const isFirst = s.messages.length === 0;
        return {
          ...s,
          title: isFirst ? titleFromMessage(question) : s.title,
          messages: [...s.messages, userMsg, assistantMsg],
          debugLog: [...s.debugLog, { question, intent_type: intentType, files }],
          searchContext: files.length > 0 ? { query: question, files } : s.searchContext,
          updatedAt: Date.now(),
        };
      });
    },
    [updateActiveSession],
  );

  const value: SearchContextValue = {
    messages: activeSession?.messages ?? [],
    debugLog: activeSession?.debugLog ?? [],
    input,
    setInput,
    loading,
    send,
    reset,
    sessions,
    activeSessionId,
    newSession,
    selectSession,
    deleteSession,
    renameSession,
    sendFromSpotlight,
  };

  return <SearchContext.Provider value={value}>{children}</SearchContext.Provider>;
}

export function useSearch(): SearchContextValue {
  const ctx = useContext(SearchContext);
  if (!ctx) throw new Error('useSearch must be inside SearchProvider');
  return ctx;
}
