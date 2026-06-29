import { useState, useEffect } from 'react';
import { BrowserRouter, NavLink, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Dashboard from './pages/Dashboard';
import GraphView from './pages/GraphView';
import Search from './pages/Search';
import Settings from './pages/Settings';
import Calendar from './pages/Calendar';
import Spotlight from './Spotlight';
import StatusBar from './StatusBar';
import ScanToast from './ScanToast';
import NoopToast from './NoopToast';
import Onboarding from './Onboarding';
import { SearchProvider } from './SearchContext';
import FloatingParticles from './FloatingParticles';
import { useDockPosition } from './useDockPosition';

interface NavItem {
  to: string;
  end?: boolean;
  icon: React.ReactNode;
  labelKey: string;
}

const CalendarIcon = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

const GraphIcon = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="18" cy="8" r="2.5" />
    <circle cx="8" cy="18" r="2.5" />
    <circle cx="18" cy="18" r="2.5" />
    <line x1="8.2" y1="7.2" x2="15.8" y2="7.5" />
    <line x1="7" y1="8.5" x2="7.5" y2="15.5" />
    <line x1="10.2" y1="17.2" x2="15.5" y2="17.5" />
  </svg>
);

const NAV_ITEMS: NavItem[] = [
  { to: '/', end: true, icon: '◈', labelKey: 'nav.dashboard' },
  { to: '/calendar', icon: CalendarIcon, labelKey: 'nav.calendar' },
  { to: '/graph', icon: GraphIcon, labelKey: 'nav.graph' },
  { to: '/search', icon: '✦', labelKey: 'nav.search' },
  { to: '/settings', icon: '⚙', labelKey: 'nav.settings' },
];

const ONBOARDING_KEY = 'gemvis.onboardingCompleted';
const STATUSBAR_KEY = 'gemvis.statusbarVisible';

const readOnboarding = (): boolean => {
  try {
    return window.localStorage.getItem(ONBOARDING_KEY) === '1';
  } catch {
    return false;
  }
};

const readStatusbar = (): boolean => {
  try {
    const v = window.localStorage.getItem(STATUSBAR_KEY);
    // default to visible
    return v !== '0';
  } catch {
    return true;
  }
};

const PAGES = [
  { path: '/', Component: Dashboard },
  { path: '/calendar', Component: Calendar },
  { path: '/graph', Component: GraphView },
  { path: '/search', Component: Search },
  { path: '/settings', Component: Settings },
] as const;

function AppPages() {
  const { pathname } = useLocation();
  const [visited, setVisited] = useState<Set<string>>(new Set([pathname]));

  useEffect(() => {
    setVisited((prev) => (prev.has(pathname) ? prev : new Set(prev).add(pathname)));
  }, [pathname]);

  return (
    <main className="main">
      {PAGES.map(({ path, Component }) => {
        const active = pathname === path || (path === '/' && pathname === '');
        if (!visited.has(path)) return null;
        return (
          <div key={path} className="page-slot" style={{ display: active ? 'contents' : 'none' }}>
            <Component />
          </div>
        );
      })}
    </main>
  );
}

export default function App() {
  const { t } = useTranslation();
  const [onboardingDone, setOnboardingDone] = useState(readOnboarding);
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [statusbarVisible, setStatusbarVisible] = useState(readStatusbar);
  const { position: dockPosition } = useDockPosition();

  const completeOnboarding = () => {
    try { window.localStorage.setItem(ONBOARDING_KEY, '1'); } catch { /* ignore */ }
    setOnboardingDone(true);
  };

  const toggleStatusbar = () => {
    setStatusbarVisible((prev) => {
      const next = !prev;
      try { window.localStorage.setItem(STATUSBAR_KEY, next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  };

  // Cmd/Ctrl+K → open command palette
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().includes('MAC');
      const mod = isMac ? e.metaKey : e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSpotlightOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    const open = () => setSpotlightOpen(true);
    window.addEventListener('gemvis:open-spotlight', open);
    return () => window.removeEventListener('gemvis:open-spotlight', open);
  }, []);

  if (!onboardingDone) {
    return <Onboarding onComplete={completeOnboarding} />;
  }

  return (
    <BrowserRouter>
      <SearchProvider>
      <FloatingParticles />
      <div className={`app-shell dock-${dockPosition}${statusbarVisible ? '' : ' statusbar-hidden'}`}>
        {/* Floating glass dock — icon-only, vertically centered on the left */}
        <nav className="hud-dock" aria-label="Primary">
          <div className="hud-dock-logo">
            <img
              src={dockPosition === 'left' || dockPosition === 'right'
                ? '/Gemvis_logo_stacked.png'
                : '/Gemvis_logo_white_v2.png'}
              alt="Gemvis"
            />
          </div>
          {NAV_ITEMS.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              className={({ isActive }) => `hud-dock-item${isActive ? ' active' : ''}`}
              title={t(it.labelKey)}
              aria-label={t(it.labelKey)}
            >
              <span className="hud-dock-item-icon">{it.icon}</span>
              <span className="hud-dock-item-tooltip">{t(it.labelKey)}</span>
            </NavLink>
          ))}
          <div className="hud-dock-spacer" />
          {/* Search trigger — visible label + key hint so the shortcut is obvious */}
          <button
            type="button"
            className="hud-dock-search"
            onClick={() => setSpotlightOpen(true)}
            title={t('topbar.searchOpen')}
            aria-label={t('topbar.searchOpen')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <span className="hud-dock-search-label">{t('topbar.searchPlaceholder')}</span>
            <kbd className="hud-dock-search-kbd">
              <span aria-hidden="true">⌘</span>K
            </kbd>
          </button>
        </nav>

        <AppPages />

        <StatusBar />
        <button
          type="button"
          className="statusbar-toggle"
          onClick={toggleStatusbar}
          title={statusbarVisible ? t('nav.hideStatusbar') : t('nav.showStatusbar')}
          aria-label={statusbarVisible ? t('nav.hideStatusbar') : t('nav.showStatusbar')}
          aria-pressed={statusbarVisible}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            {statusbarVisible ? <polyline points="6 9 12 15 18 9" /> : <polyline points="18 15 12 9 6 15" />}
          </svg>
        </button>
        <Spotlight open={spotlightOpen} onClose={() => setSpotlightOpen(false)} />
        <ScanToast />
        <NoopToast />
      </div>
      </SearchProvider>
    </BrowserRouter>
  );
}
