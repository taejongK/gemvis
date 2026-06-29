import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { api } from '../api';
import i18nClient, { SUPPORTED_LANGS, LANG_NATIVE_NAMES, setLanguage, translateApiMessage, type Lang } from '../i18n';
import { useGraphTheme } from '../theme/useGraphTheme';
import FolderPicker from '../FolderPicker';
import ScanMonitor from '../ScanMonitor';
import { GRAPH_THEMES, GRAPH_THEME_IDS, type GraphThemeId } from '../theme/graphThemes';
import { useDockPosition, DOCK_POSITIONS, type DockPosition } from '../useDockPosition';
import type {
  WatcherStatus,
  WorkScheduleMap,
  DayHours,
  FileRecord,
  AnalysisStatus,
  ApiMessage,
} from '../types';

const STATUS_ICON: Record<AnalysisStatus, string> = {
  pending: '⏳', processing: '⚙️', completed: '✅', failed: '❌',
};

const DAY_KEYS: (keyof WorkScheduleMap)[] = [
  'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
];

interface DirItem {
  path: string;
  enabled: boolean;
}

type SectionId = 'dirs' | 'schedule' | 'files' | 'llm' | 'apikey' | 'danger';
type ScanMode = 'all' | 'documents' | 'images' | 'skeleton';

interface SectionProps {
  id: SectionId;
  title: string;
  badge?: ReactNode;
  defaultOpen?: boolean;
  tone?: 'default' | 'danger';
  open: Record<SectionId, boolean>;
  setOpen: (id: SectionId, next: boolean) => void;
  children: ReactNode;
}

function Section({ id, title, badge, tone = 'default', open, setOpen, children }: SectionProps) {
  const isOpen = open[id];
  return (
    <section className={`settings-accordion${isOpen ? ' open' : ''}${tone === 'danger' ? ' danger' : ''}`}>
      <button
        type="button"
        className="settings-accordion-head"
        onClick={() => setOpen(id, !isOpen)}
        aria-expanded={isOpen}
      >
        <span className="settings-accordion-chevron" aria-hidden="true">
          {isOpen ? '▾' : '▸'}
        </span>
        <span className="settings-accordion-title">{title}</span>
        {badge !== undefined && <span className="settings-accordion-badge">{badge}</span>}
      </button>
      {isOpen && <div className="settings-accordion-body">{children}</div>}
    </section>
  );
}

export default function Settings() {
  const { t, i18n } = useTranslation();
  const currentLang = (i18n.resolvedLanguage || i18n.language || 'ko') as Lang;
  const { themeId: graphThemeId, setTheme: setGraphTheme } = useGraphTheme();
  const { position: dockPosition, setPosition: setDockPosition } = useDockPosition();
  const [dirs, setDirs] = useState<DirItem[]>([]);
  const [status, setStatus] = useState<WatcherStatus | null>(null);
  const [schedule, setSchedule] = useState<WorkScheduleMap | null>(null);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [analyzeImages, setAnalyzeImages] = useState(true);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [llmTemperature, setLlmTemperature] = useState(0.1);
  const [llmMaxTokens, setLlmMaxTokens] = useState(4096);
  const [llmTopP, setLlmTopP] = useState(0.95);
  const [llmTopK, setLlmTopK] = useState(40);
  const [watchedFiles, setWatchedFiles] = useState<FileRecord[]>([]);
  const [filesTotal, setFilesTotal] = useState(0);
  const [filesAnalyzed, setFilesAnalyzed] = useState(0);
  const [filesProcessing, setFilesProcessing] = useState(0);
  const [open, setOpenState] = useState<Record<SectionId, boolean>>({
    dirs: false,
    schedule: false,
    files: false,
    llm: false,
    apikey: false,
    danger: false,
  });
  const setOpen = (id: SectionId, next: boolean) =>
    setOpenState((prev) => ({ ...prev, [id]: next }));

  // Extract menu (Hero 우상단 분할 액션) — outside-click to close
  const [extractMenuOpen, setExtractMenuOpen] = useState(false);
  const [scanRequest, setScanRequest] = useState<{ token: number; mode: ScanMode } | null>(null);
  const extractMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!extractMenuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (extractMenuRef.current && !extractMenuRef.current.contains(e.target as Node)) {
        setExtractMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExtractMenuOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [extractMenuOpen]);

  const loadStatus = () => {
    api.watcherStatus().then((s) => {
      setStatus(s);
      const watchSet = new Set(s.watch_dirs);
      const allPaths = new Set([...s.watch_dirs, ...s.default_dirs]);
      const items: DirItem[] = Array.from(allPaths).map((p) => ({
        path: p,
        enabled: watchSet.has(p),
      }));
      items.sort((a, b) => a.path.localeCompare(b.path));
      setDirs(items);
    });
  };

  const loadSchedule = () => {
    api.getSchedule().then((r) => setSchedule(r.schedule));
  };

  const loadFiles = () => {
    api.files({ limit: 10000 }).then((r) => {
      setWatchedFiles(r.files);
      setFilesTotal(r.pagination.total);
      setFilesAnalyzed(r.status_counts?.completed ?? 0);
      setFilesProcessing(r.status_counts?.processing ?? 0);
    });
  };

  const loadPreferences = () => {
    api.getPreferences().then((p) => {
      setAnalyzeImages(p.analyze_images);
      setWebSearchEnabled(p.web_search_enabled);
      setLlmTemperature(p.llm_temperature);
      setLlmMaxTokens(p.llm_max_tokens);
      setLlmTopP(p.llm_top_p);
      setLlmTopK(p.llm_top_k);
    });
  };

  const location = useLocation();
  const isActive = location.pathname === '/settings';

  useEffect(() => {
    loadStatus();
    loadSchedule();
    loadFiles();
    loadPreferences();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isActive) return;
    const tick = setInterval(() => {
      loadStatus();
      loadFiles();
    }, 4000);
    return () => clearInterval(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive]);

  const showMsg = (text: string) => {
    setMsg(text);
    setTimeout(() => setMsg(''), 4000);
  };

  const doAction = async (action: () => Promise<ApiMessage>) => {
    setBusy(true);
    try {
      const res = await action();
      showMsg(translateApiMessage(res));
      loadStatus();
      loadFiles();
    } catch {
      showMsg(t('settings.error'));
    } finally {
      setBusy(false);
    }
  };

  const runScan = (mode: ScanMode) => {
    setExtractMenuOpen(false);
    setScanRequest((prev) => ({ token: (prev?.token ?? 0) + 1, mode }));
    doAction(() => api.watcherScan(mode));
  };

  const toggleDir = (path: string) => {
    setDirs((prev) => prev.map((d) => (d.path === path ? { ...d, enabled: !d.enabled } : d)));
  };

  const removeDir = (path: string) => {
    setDirs((prev) => prev.filter((d) => d.path !== path));
  };

  const saveSettings = async () => {
    setBusy(true);
    try {
      const enabledDirs = dirs.filter((d) => d.enabled).map((d) => d.path);
      const res = await api.saveConfig(undefined, enabledDirs);
      showMsg(translateApiMessage(res));
      loadStatus();
    } catch {
      showMsg(t('settings.saveFailed'));
    } finally {
      setBusy(false);
    }
  };

  const enabledDirsCount = dirs.filter((d) => d.enabled).length;
  const enabledDaysCount = schedule
    ? DAY_KEYS.filter((k) => schedule[k] !== null).length
    : 0;
  // Three-state label so the hero never lies about a not-yet-loaded watcher
  // by flashing "stopped" before the first /api/watcher/status response.
  const watcherLoading = status === null;
  const runningLabel = watcherLoading
    ? t('settings.statusLoading', { defaultValue: '확인 중…' })
    : status.running
    ? t('settings.statusRunning')
    : t('settings.statusStopped');
  const heroStatusClass = watcherLoading
    ? 'checking'
    : status.running
    ? 'on'
    : 'off';

  return (
    <div className="page settings-page">
      {msg && <div className="toast">{msg}</div>}

      {/* Priority 1 — Live watcher state + primary controls */}
      <div className="settings-hero">
        <div className="settings-hero-stats">
          <div className={`settings-stat ${heroStatusClass}`}>
            <span className="settings-stat-label">{t('settings.statusLabel')}</span>
            <span className="settings-stat-value">
              <span className="settings-stat-dot" aria-hidden="true" />
              {runningLabel}
            </span>
          </div>
          <div className="settings-stat">
            <span className="settings-stat-label">{t('settings.statusDirCount')}</span>
            <span className="settings-stat-value">{status?.watch_dirs.length ?? 0}</span>
          </div>
          <div className="settings-stat">
            <span className="settings-stat-label">{t('settings.statusWatchedFiles', { defaultValue: '감시 대상 파일' })}</span>
            <span
              className="settings-stat-value"
              title={t('settings.statusWatchedFilesHint', { defaultValue: '감시 폴더에 실제로 존재하는 지원 파일 수 (node_modules, .git 등 제외)' })}
            >
              {status?.watched_files_total ?? '—'}
            </span>
          </div>
          <div className="settings-stat">
            <span className="settings-stat-label">
              {t('settings.statusAnalyzedFiles', { defaultValue: '분석된 파일' })}
              {filesProcessing > 0 && (
                <span
                  className="settings-stat-led"
                  aria-label={t('settings.processingActive', { defaultValue: '분석 중' })}
                  title={t('settings.processingActiveHint', { count: filesProcessing, defaultValue: `${filesProcessing}개 파일 분석 중` })}
                />
              )}
            </span>
            <span
              className="settings-stat-value"
              title={t('settings.statusInsightExtractedHint')}
            >
              {filesAnalyzed}
              <span className="settings-stat-fraction">
                / {status?.watched_files_total ?? filesTotal}
              </span>
            </span>
          </div>
        </div>
        <div className="settings-hero-actions">
          <label
            className={`switch-inline${status?.running ? ' on' : ''}${busy || watcherLoading ? ' busy' : ''}`}
          >
            <span className="switch-inline-text">{t('settings.watchToggleLabel')}</span>
            <input
              type="checkbox"
              checked={!!status?.running}
              disabled={busy || watcherLoading}
              onChange={() => doAction(status?.running ? api.watcherStop : api.watcherStart)}
            />
            <span className="switch-inline-track" aria-hidden="true">
              <span className="switch-inline-thumb" />
            </span>
          </label>

          <label
            className={`switch-inline${analyzeImages ? ' on' : ''}${busy ? ' busy' : ''}`}
          >
            <span className="switch-inline-text">
              {t('settings.imageAnalysisSection')}
              <span
                className="summary-block-info summary-block-info-center summary-block-info-super"
                tabIndex={0}
                role="button"
                aria-label={t('settings.imageAnalysisDesc')}
                onClick={(e) => e.preventDefault()}
              >
                ⓘ
                <span className="summary-block-info-popup" role="tooltip">
                  {t('settings.imageAnalysisDesc')}
                </span>
              </span>
            </span>
            <input
              type="checkbox"
              checked={analyzeImages}
              disabled={busy}
              onChange={async () => {
                const next = !analyzeImages;
                setAnalyzeImages(next);
                setBusy(true);
                try {
                  await api.updatePreferences({ analyze_images: next });
                  showMsg(t('settings.saved'));
                } catch {
                  setAnalyzeImages(!next);
                  showMsg(t('settings.error'));
                } finally {
                  setBusy(false);
                }
              }}
            />
            <span className="switch-inline-track" aria-hidden="true">
              <span className="switch-inline-thumb" />
            </span>
          </label>

          <label
            className={`switch-inline${webSearchEnabled ? ' on' : ''}${busy ? ' busy' : ''}`}
          >
            <span className="switch-inline-text">
              {t('settings.webSearchSection')}
              <span
                className="summary-block-info summary-block-info-center summary-block-info-super"
                tabIndex={0}
                role="button"
                aria-label={t('settings.webSearchDesc')}
                onClick={(e) => e.preventDefault()}
              >
                ⓘ
                <span className="summary-block-info-popup" role="tooltip">
                  {t('settings.webSearchDesc')}
                </span>
              </span>
            </span>
            <input
              type="checkbox"
              checked={webSearchEnabled}
              disabled={busy}
              onChange={async () => {
                const next = !webSearchEnabled;
                setWebSearchEnabled(next);
                setBusy(true);
                try {
                  await api.updatePreferences({ web_search_enabled: next });
                  showMsg(t('settings.saved'));
                } catch {
                  setWebSearchEnabled(!next);
                  showMsg(t('settings.error'));
                } finally {
                  setBusy(false);
                }
              }}
            />
            <span className="switch-inline-track" aria-hidden="true">
              <span className="switch-inline-thumb" />
            </span>
          </label>

          <div className="extract-menu" ref={extractMenuRef}>
            <button
              type="button"
              className="btn btn-primary extract-menu-btn"
              disabled={busy}
              aria-haspopup="menu"
              aria-expanded={extractMenuOpen}
              onClick={() => setExtractMenuOpen((v) => !v)}
            >
              <span>{t('settings.extractAction', { defaultValue: '인사이트 추출' })}</span>
              <svg className="extract-menu-caret" width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
                <path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {extractMenuOpen && (
              <div className="extract-menu-pop" role="menu">
                <button
                  type="button"
                  role="menuitem"
                  className="extract-menu-item"
                  disabled={busy}
                  onClick={() => runScan('all')}
                >
                  <span className="extract-menu-item-title">{t('settings.extractAll', { defaultValue: '전체 추출' })}</span>
                  <span className="extract-menu-item-desc">{t('settings.extractAllDesc', { defaultValue: '문서 + 이미지' })}</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="extract-menu-item"
                  disabled={busy}
                  onClick={() => runScan('documents')}
                >
                  <span className="extract-menu-item-title">{t('settings.extractDocuments', { defaultValue: '문서만 추출' })}</span>
                  <span className="extract-menu-item-desc">{t('settings.extractDocumentsDesc', { defaultValue: '텍스트 / PDF / 마크다운' })}</span>
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="extract-menu-item"
                  disabled={busy}
                  onClick={() => runScan('images')}
                >
                  <span className="extract-menu-item-title">{t('settings.extractImages', { defaultValue: '이미지만 추출' })}</span>
                  <span className="extract-menu-item-desc">{t('settings.extractImagesDesc', { defaultValue: 'Vision (PNG / JPG / GIF / ...)' })}</span>
                </button>
                <div className="extract-menu-divider" />
                <button
                  type="button"
                  role="menuitem"
                  className="extract-menu-item subtle"
                  disabled={busy}
                  onClick={() => runScan('skeleton')}
                >
                  <span className="extract-menu-item-title">{t('settings.scanSkeleton', { defaultValue: '디스크 다시 스캔' })}</span>
                  <span className="extract-menu-item-desc">{t('settings.scanSkeletonDesc', { defaultValue: 'AI 호출 없이 파일 목록만 갱신' })}</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Inline scan monitor — appears below the hero while a scan is running
          or for ~30s after it finishes. Replaces the floating ScanToast for
          users who are already on the Settings page. */}
      <ScanMonitor requestToken={scanRequest?.token ?? 0} requestedMode={scanRequest?.mode} />

      {/* Priority 2 — Quick preferences (language + theme) in a compact row */}
      <div className="settings-quickrow">
        <div className="settings-quick">
          <div className="settings-quick-label">{t('settings.languageSection')}</div>
          <div className="settings-chip-row">
            {SUPPORTED_LANGS.map((code) => (
              <button
                key={code}
                type="button"
                className={`settings-chip${currentLang === code ? ' active' : ''}`}
                onClick={() => {
                  setLanguage(code);
                  // Use new language directly — closure t() is stale until next render
                  showMsg(i18nClient.t('settings.saved', { lng: code }));
                }}
              >
                {LANG_NATIVE_NAMES[code]}
              </button>
            ))}
          </div>
        </div>

        <div className="settings-quick">
          <div className="settings-quick-label">{t('graph.theme.sectionTitle')}</div>
          <div className="settings-chip-row">
            {GRAPH_THEME_IDS.map((id: GraphThemeId) => {
              const theme = GRAPH_THEMES[id];
              const swatches = Object.values(theme.nodeTypes).slice(0, 4).map((v) => v.color);
              const active = graphThemeId === id;
              return (
                <button
                  key={id}
                  type="button"
                  className={`settings-chip theme-chip${active ? ' active' : ''}`}
                  onClick={() => {
                    setGraphTheme(id);
                    showMsg(t('settings.saved'));
                  }}
                  title={t(`graph.theme.${id}Desc`)}
                >
                  <span className="theme-chip-swatches" aria-hidden="true">
                    {swatches.map((c, i) => (
                      <span key={i} className="theme-chip-swatch" style={{ background: c }} />
                    ))}
                  </span>
                  {t(theme.labelKey)}
                </button>
              );
            })}
          </div>
        </div>

        <div className="settings-quick">
          <div className="settings-quick-label">{t('settings.dockSection')}</div>
          <div className="settings-chip-row">
            {DOCK_POSITIONS.map((pos: DockPosition) => {
              const active = dockPosition === pos;
              return (
                <button
                  key={pos}
                  type="button"
                  className={`settings-chip${active ? ' active' : ''}`}
                  onClick={() => {
                    setDockPosition(pos);
                    showMsg(t('settings.saved'));
                  }}
                >
                  {t(`settings.dock${pos.charAt(0).toUpperCase()}${pos.slice(1)}`)}
                </button>
              );
            })}
          </div>
        </div>

      </div>

      {/* Priority 3 — Collapsible detail sections */}
      <div className="settings-accordions">
        <Section
          id="dirs"
          title={t('settings.watchSection')}
          badge={t('settings.dirsActiveBadge', { count: enabledDirsCount, defaultValue: `${enabledDirsCount} active` })}
          open={open}
          setOpen={setOpen}
        >
          <p className="settings-help">{t('settings.watchDescription')}</p>
          <div className="dir-list">
            {dirs.length === 0 && <div className="dir-empty">{t('settings.dirsEmpty')}</div>}
            {dirs.map((d) => (
              <div key={d.path} className="dir-row">
                <label className="dir-check">
                  <input
                    type="checkbox"
                    checked={d.enabled}
                    onChange={() => toggleDir(d.path)}
                  />
                  <code className={d.enabled ? '' : 'dir-disabled'}>{d.path}</code>
                </label>
                <button
                  className="btn btn-ghost"
                  onClick={() => removeDir(d.path)}
                  title={t('settings.dirRemove')}
                  aria-label={t('settings.dirRemoveAria', { path: d.path })}
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          <button className="btn" onClick={() => setShowPicker(true)}>
            + {t('settings.dirAdd')}
          </button>

          <div className="settings-accordion-footer">
            <button className="btn btn-primary" disabled={busy} onClick={saveSettings}>
              {t('settings.watchSave')}
            </button>
          </div>
        </Section>

        <Section
          id="schedule"
          title={t('settings.scheduleSection')}
          badge={`${enabledDaysCount} / 7`}
          open={open}
          setOpen={setOpen}
        >
          <p
            className="settings-help"
            dangerouslySetInnerHTML={{ __html: t('settings.scheduleDescription') }}
          />
          {schedule && (
            <div className="schedule-grid">
              {DAY_KEYS.map((key) => {
                const cfg = schedule[key];
                const enabled = cfg !== null;
                const updateDay = (next: DayHours) => {
                  setSchedule({ ...schedule, [key]: next });
                };
                return (
                  <div key={key} className={`schedule-row ${enabled ? 'on' : 'off'}`}>
                    <label className="schedule-day">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={(e) => {
                          updateDay(e.target.checked ? { start: '08:00', end: '17:00' } : null);
                        }}
                      />
                      <span>{t(`settings.days.${key}`)}</span>
                    </label>
                    <input
                      type="time"
                      disabled={!enabled}
                      value={cfg?.start ?? ''}
                      onChange={(e) => enabled && updateDay({ start: e.target.value, end: cfg!.end })}
                    />
                    <span className="schedule-sep">~</span>
                    <input
                      type="time"
                      disabled={!enabled}
                      value={cfg?.end ?? ''}
                      onChange={(e) => enabled && updateDay({ start: cfg!.start, end: e.target.value })}
                    />
                  </div>
                );
              })}
            </div>
          )}
          <div className="settings-accordion-footer">
            <button
              className="btn btn-primary"
              disabled={busy || !schedule}
              onClick={async () => {
                if (!schedule) return;
                setBusy(true);
                try {
                  await api.saveSchedule(schedule);
                  showMsg(t('settings.scheduleSaved'));
                } catch {
                  showMsg(t('settings.scheduleSaveFailed'));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t('settings.scheduleSave')}
            </button>
          </div>
        </Section>

        <Section
          id="files"
          title={t('settings.analyzedFilesSection', { defaultValue: '분석 결과 파일' })}
          badge={`${filesAnalyzed} / ${status?.watched_files_total ?? filesTotal}`}
          open={open}
          setOpen={setOpen}
        >
          <div className="file-scroll">
            {watchedFiles.length === 0 && (
              <p className="empty-state">{t('settings.filesEmpty')}</p>
            )}
            {watchedFiles.map((f) => {
              const completed = f.analysis_status === 'completed';
              const sizeKb = f.size_bytes ? (f.size_bytes / 1024).toFixed(1) : '-';
              return (
                <div key={f.file_id} className="file-row" title={f.error ?? f.analysis_status}>
                  <span className="file-status-icon">{STATUS_ICON[f.analysis_status]}</span>
                  <div className="file-meta">
                    <div className={`file-name${completed ? ' completed' : ''}`}>
                      {f.file_name}
                      {f.category && <span className="file-category">({f.category})</span>}
                    </div>
                    <div className="file-path">{f.file_id}</div>
                  </div>
                  <span className="file-size">{sizeKb} KB</span>
                </div>
              );
            })}
          </div>
        </Section>

        <Section
          id="llm"
          title={t('settings.llmSection')}
          open={open}
          setOpen={setOpen}
        >
          <div className="llm-params">
            {([
              { label: 'Temperature', hint: '낮을수록 정확, 높을수록 창의적', value: llmTemperature, set: setLlmTemperature, min: 0, max: 2, step: 0.1, key: 'llm_temperature' as const, fmt: (v: number) => v.toFixed(1) },
              { label: 'Max Tokens', hint: '응답 최대 길이', value: llmMaxTokens, set: setLlmMaxTokens, min: 512, max: 8192, step: 256, key: 'llm_max_tokens' as const, fmt: (v: number) => String(v) },
              { label: 'Top P', hint: '누적 확률 기반 샘플링', value: llmTopP, set: setLlmTopP, min: 0, max: 1, step: 0.05, key: 'llm_top_p' as const, fmt: (v: number) => v.toFixed(2) },
              { label: 'Top K', hint: '상위 K개 토큰만 선택', value: llmTopK, set: setLlmTopK, min: 1, max: 100, step: 1, key: 'llm_top_k' as const, fmt: (v: number) => String(v) },
            ] as const).map((param) => (
              <div className="llm-param-row" key={param.label}>
                <div className="llm-param-info">
                  <span className="llm-param-label">{param.label}</span>
                  <span className="llm-param-hint">{param.hint}</span>
                </div>
                <div className="llm-param-controls">
                  <input
                    type="range"
                    className="llm-param-slider"
                    min={param.min}
                    max={param.max}
                    step={param.step}
                    value={param.value}
                    disabled={busy}
                    onChange={(e) => param.set(parseFloat(e.target.value) as never)}
                    onMouseUp={async () => {
                      setBusy(true);
                      try {
                        await api.updatePreferences({ [param.key]: param.value });
                        showMsg(t('settings.saved'));
                      } catch {
                        showMsg(t('settings.error'));
                      } finally {
                        setBusy(false);
                      }
                    }}
                  />
                  <input
                    type="number"
                    className="llm-param-input"
                    min={param.min}
                    max={param.max}
                    step={param.step}
                    value={param.fmt(param.value)}
                    disabled={busy}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value);
                      if (!isNaN(v)) param.set(Math.max(param.min, Math.min(param.max, v)) as never);
                    }}
                    onBlur={async () => {
                      setBusy(true);
                      try {
                        await api.updatePreferences({ [param.key]: param.value });
                        showMsg(t('settings.saved'));
                      } catch {
                        showMsg(t('settings.error'));
                      } finally {
                        setBusy(false);
                      }
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section
          id="danger"
          title={t('settings.dataSection')}
          open={open}
          setOpen={setOpen}
        >
          <p className="settings-help">
            {t('settings.dataDescription')} <code>~/.gemvis/</code>
            <br />
            {t('settings.dataFiles')}
          </p>
          <div className="settings-accordion-footer">
            <button
              className="btn btn-danger"
              disabled={busy}
              onClick={async () => {
                if (!confirm(t('settings.dataClearConfirm'))) return;
                setBusy(true);
                try {
                  const res = await api.clearGraph();
                  showMsg(translateApiMessage(res));
                  loadStatus();
                  loadFiles();
                } catch {
                  showMsg(t('settings.dataClearFailed'));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t('settings.dataClear')}
            </button>
          </div>
          <p className="settings-help muted">{t('settings.dataClearNote')}</p>
        </Section>
      </div>

      <div className="settings-footer-actions">
        <button
          className="btn btn-ghost"
          onClick={() => {
            window.localStorage.removeItem('gemvis.onboardingCompleted');
            window.location.reload();
          }}
        >
          {t('settings.resetOnboarding')}
        </button>
      </div>

      <FolderPicker
        open={showPicker}
        onSelect={(path) => {
          setShowPicker(false);
          if (dirs.some((d) => d.path === path)) {
            showMsg(t('settings.dirAlreadyExists'));
            return;
          }
          setDirs((prev) => [...prev, { path, enabled: true }]);
        }}
        onCancel={() => setShowPicker(false)}
      />
    </div>
  );
}
