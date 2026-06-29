import { useCallback, useEffect, useState } from 'react';

export type DockPosition = 'top' | 'bottom' | 'left' | 'right';
export const DOCK_POSITIONS: DockPosition[] = ['top', 'bottom', 'left', 'right'];
export const DEFAULT_DOCK_POSITION: DockPosition = 'top';

const STORAGE_KEY = 'gemvis.dockPosition';
const CHANGE_EVENT = 'gemvis:dock-position-change';

const readStored = (): DockPosition => {
  if (typeof window === 'undefined') return DEFAULT_DOCK_POSITION;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw && (DOCK_POSITIONS as string[]).includes(raw)) {
      return raw as DockPosition;
    }
  } catch { /* ignore */ }
  return DEFAULT_DOCK_POSITION;
};

const broadcast = (pos: DockPosition) => {
  try { window.localStorage.setItem(STORAGE_KEY, pos); } catch { /* ignore */ }
  window.dispatchEvent(new CustomEvent<DockPosition>(CHANGE_EVENT, { detail: pos }));
};

export function useDockPosition() {
  const [position, setPositionState] = useState<DockPosition>(readStored);

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<DockPosition>).detail;
      if (detail && (DOCK_POSITIONS as string[]).includes(detail)) {
        setPositionState(detail);
      }
    };
    window.addEventListener(CHANGE_EVENT, onChange);
    return () => window.removeEventListener(CHANGE_EVENT, onChange);
  }, []);

  const setPosition = useCallback((pos: DockPosition) => {
    setPositionState(pos);
    broadcast(pos);
  }, []);

  return { position, setPosition };
}
