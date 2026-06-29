import { useCallback, useEffect, useState } from 'react';
import {
  DEFAULT_GRAPH_THEME,
  GRAPH_THEMES,
  GRAPH_THEME_IDS,
  type GraphTheme,
  type GraphThemeId,
} from './graphThemes';

const STORAGE_KEY = 'gemvis.graphTheme';
const CHANGE_EVENT = 'gemvis:graph-theme-change';

const readStoredTheme = (): GraphThemeId => {
  if (typeof window === 'undefined') return DEFAULT_GRAPH_THEME;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw && (GRAPH_THEME_IDS as string[]).includes(raw)) {
      return raw as GraphThemeId;
    }
  } catch {
    // localStorage may be disabled (e.g., private mode) — fall through
  }
  return DEFAULT_GRAPH_THEME;
};

const broadcast = (id: GraphThemeId) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // ignore — still emit event so in-memory state updates
  }
  window.dispatchEvent(new CustomEvent<GraphThemeId>(CHANGE_EVENT, { detail: id }));
};

export interface UseGraphTheme {
  themeId: GraphThemeId;
  theme: GraphTheme;
  setTheme: (id: GraphThemeId) => void;
  cycleTheme: () => void;
}

export function useGraphTheme(): UseGraphTheme {
  const [themeId, setThemeIdState] = useState<GraphThemeId>(readStoredTheme);

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<GraphThemeId>).detail;
      if (detail && (GRAPH_THEME_IDS as string[]).includes(detail)) {
        setThemeIdState(detail);
      }
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && e.newValue && (GRAPH_THEME_IDS as string[]).includes(e.newValue)) {
        setThemeIdState(e.newValue as GraphThemeId);
      }
    };
    window.addEventListener(CHANGE_EVENT, onChange as EventListener);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onChange as EventListener);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  const setTheme = useCallback((id: GraphThemeId) => {
    broadcast(id);
    setThemeIdState(id);
  }, []);

  const cycleTheme = useCallback(() => {
    setThemeIdState((prev) => {
      const idx = GRAPH_THEME_IDS.indexOf(prev);
      const next = GRAPH_THEME_IDS[(idx + 1) % GRAPH_THEME_IDS.length];
      broadcast(next);
      return next;
    });
  }, []);

  return {
    themeId,
    theme: GRAPH_THEMES[themeId],
    setTheme,
    cycleTheme,
  };
}
