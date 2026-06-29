import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import type { DateClickArg } from '@fullcalendar/interaction';
import type { DatesSetArg } from '@fullcalendar/core';
import Markdown from 'react-markdown';
import { api } from '../api';
import type { DailySummary, DaySummaryResponse, SummaryPeriod, TaskProgress } from '../types';
import TaskSection from '../TaskSection';

type ConfirmAction =
  | { kind: 'regenerate'; date: string; period: SummaryPeriod }
  | { kind: 'delete'; date: string; period: SummaryPeriod }
  | null;

const CAL_FONTSIZE_KEY = 'gemvis.calendarFontSize';

export default function Calendar() {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const [fontSize, setFontSize] = useState<number>(() => {
    try {
      const raw = window.localStorage.getItem(CAL_FONTSIZE_KEY);
      return raw ? Math.min(18, Math.max(10, Number(raw))) : 13;
    } catch { return 13; }
  });
  const months = useMemo(
    () => Array.from({ length: 12 }, (_, i) => t(`calendar.months.m${i + 1}`)),
    // re-evaluate when language changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [i18n.resolvedLanguage, t],
  );
  const periodLabel = (p: SummaryPeriod) =>
    t(p === 'work' ? 'calendar.work' : p === 'personal' ? 'calendar.personal' : 'calendar.daily');
  const [summaries, setSummaries] = useState<DailySummary[]>([]);
  const [taskProgress, setTaskProgress] = useState<TaskProgress[]>([]);
  const [fileDateCounts, setFileDateCounts] = useState<Map<string, number>>(new Map());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dayDetail, setDayDetail] = useState<DaySummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState('');
  const [confirm, setConfirm] = useState<ConfirmAction>(null);
  const rangeRef = useRef<{ from: string; to: string } | null>(null);
  const calendarRef = useRef<FullCalendar>(null);
  const calendarMainRef = useRef<HTMLDivElement>(null);

  // Detail panel width — drag-resizable. Persisted across sessions.
  const DETAIL_W_KEY = 'gemvis.calendarDetailWidth';
  const DETAIL_W_MIN = 320;
  const DETAIL_W_MAX = 720;
  const [detailWidth, setDetailWidth] = useState<number>(() => {
    try {
      const raw = window.localStorage.getItem(DETAIL_W_KEY);
      const n = raw ? Number(raw) : 460;
      return Number.isFinite(n) ? Math.min(DETAIL_W_MAX, Math.max(DETAIL_W_MIN, n)) : 460;
    } catch {
      return 460;
    }
  });

  const calendarLayoutRef = useRef<HTMLDivElement>(null);

  const startResize = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = detailWidth;
    let latest = startW;
    let frame = 0;
    const layout = calendarLayoutRef.current;
    layout?.classList.add('resizing');
    const apply = () => {
      frame = 0;
      if (layout) layout.style.setProperty('--detail-w', `${latest}px`);
    };
    const onMove = (ev: MouseEvent) => {
      // Dragging left = wider detail (since panel is on the right).
      // Mutate the CSS variable directly via ref + rAF so FullCalendar
      // doesn't re-render on every pixel. React state is committed once
      // on mouseup so the value persists.
      latest = Math.min(DETAIL_W_MAX, Math.max(DETAIL_W_MIN, startW - (ev.clientX - startX)));
      if (!frame) frame = requestAnimationFrame(apply);
    };
    const onUp = () => {
      if (frame) cancelAnimationFrame(frame);
      layout?.classList.remove('resizing');
      setDetailWidth(latest);
      try { window.localStorage.setItem(DETAIL_W_KEY, String(latest)); } catch { /* ignore */ }
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.body.style.cursor = 'col-resize';
  };

  // Keep latest width in a ref so the mouseup handler reads the final value
  const detailWidthRef = useRef(detailWidth);
  useEffect(() => { detailWidthRef.current = detailWidth; }, [detailWidth]);
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth()); // 0-11

  // Build a year list: ±5 years around current year (extend if needed)
  const yearOptions = useMemo(() => {
    const base = new Date().getFullYear();
    const years: number[] = [];
    for (let y = 1990; y <= base + 10; y += 1) years.push(y);
    if (!years.includes(viewYear)) years.unshift(viewYear);
    return years.sort((a, b) => a - b);
  }, [viewYear]);

  const goTo = (y: number, m: number) => {
    const api = calendarRef.current?.getApi();
    if (api) api.gotoDate(new Date(y, m, 1));
    setViewYear(y);
    setViewMonth(m);
  };
  const goPrev = () => {
    const api = calendarRef.current?.getApi();
    if (api) api.prev();
  };
  const goNext = () => {
    const api = calendarRef.current?.getApi();
    if (api) api.next();
  };
  const goToday = () => {
    const api = calendarRef.current?.getApi();
    if (api) api.today();
  };

  const showToast = (text: string) => {
    setToast(text);
    setTimeout(() => setToast(''), 3500);
  };

  // Local-time YYYY-MM-DD (FullCalendar gives Date objects; toISOString would
  // shift across midnight in non-UTC zones).
  const toLocalISODate = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  const fetchRange = async (from: string, to: string) => {
    rangeRef.current = { from, to };
    try {
      const [res, prog] = await Promise.all([
        api.listSummaries(from, to),
        api.tasks.progress(from, to).catch(() => ({ progress: [] as TaskProgress[] })),
      ]);
      setSummaries(res.summaries);
      setTaskProgress(prog.progress);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t('calendar.fetchListError'));
    }
  };

  const fetchDay = async (date: string) => {
    setLoading(true);
    try {
      const detail = await api.getDaySummary(date);
      setDayDetail(detail);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t('calendar.fetchDayError'));
      setDayDetail(null);
    } finally {
      setLoading(false);
    }
  };

  // FullCalendar visible range changed (also syncs year/month state)
  const handleDatesSet = (arg: DatesSetArg) => {
    const from = arg.startStr.slice(0, 10);
    const to = new Date(arg.end.getTime() - 1).toISOString().slice(0, 10);
    fetchRange(from, to);
    // Use the middle of the visible range as the "current" month indicator
    const mid = new Date((arg.start.getTime() + arg.end.getTime()) / 2);
    if (mid.getFullYear() !== viewYear) setViewYear(mid.getFullYear());
    if (mid.getMonth() !== viewMonth) setViewMonth(mid.getMonth());
  };

  const handleDateClick = (arg: DateClickArg) => {
    setSelectedDate(arg.dateStr);
    fetchDay(arg.dateStr);
  };

  // FullCalendar nests dayCellContent inside .fc-daygrid-day-top (a small box
  // around the date number), so absolutely-positioned children there are
  // anchored to the top of the cell, not the whole cell. Bypass that by
  // injecting the donut directly into .fc-daygrid-day-frame from a post-render
  // sync pass — that way `bottom:4px` lands at the cell's actual bottom.
  const buildDonutHTML = useCallback((done: number, total: number): string => {
    const pct = Math.max(0, Math.min(1, done / total));
    const complete = pct >= 1;
    const tone = complete ? 'task-donut-full' : pct > 0 ? 'task-donut-partial' : 'task-donut-none';
    const radius = 9;
    const circ = 2 * Math.PI * radius;
    const offset = (circ * (1 - pct)).toFixed(3);
    const trophy = `<svg class="task-donut-trophy" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>`;
    // When complete: skip the ring entirely, show only the trophy.
    if (complete) {
      return `<div class="task-donut ${tone}" title="${done} / ${total}">${trophy}</div>`;
    }
    return `<div class="task-donut ${tone}" title="${done} / ${total}"><svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="${radius}" fill="none" class="task-donut-track" stroke-width="2.5"></circle><circle cx="12" cy="12" r="${radius}" fill="none" class="task-donut-fill" stroke-width="2.5" stroke-dasharray="${circ.toFixed(3)}" stroke-dashoffset="${offset}" stroke-linecap="round" transform="rotate(-90 12 12)"></circle></svg><span class="task-donut-text">${done}/${total}</span></div>`;
  }, []);

  // Index task progress by date for O(1) cell lookups.
  const progressByDate = useMemo(() => {
    const m = new Map<string, TaskProgress>();
    taskProgress.forEach((p) => m.set(p.date, p));
    return m;
  }, [taskProgress]);

  // Per-date file counts for the inline day-top chip (🗂️ N 🏠 M). Only
  // work/personal contribute — 'daily' is a separate one-sentence summary.
  const countsByDate = useMemo(() => {
    const m = new Map<string, { work: number; personal: number }>();
    summaries.forEach((s) => {
      if (s.period !== 'work' && s.period !== 'personal') return;
      const cur = m.get(s.date) ?? { work: 0, personal: 0 };
      cur[s.period] = s.file_count;
      m.set(s.date, cur);
    });
    // If no summaries exist for a date but files were created that day,
    // show the file count as "work" activity so the cell isn't empty.
    fileDateCounts.forEach((count, date) => {
      if (!m.has(date) && count > 0) {
        m.set(date, { work: count, personal: 0 });
      }
    });
    return m;
  }, [summaries, fileDateCounts]);

  // Per-date one-line daily summary rendered in the cell body.
  const dailyByDate = useMemo(() => {
    const m = new Map<string, string>();
    summaries.forEach((s) => {
      if (s.period === 'daily' && s.summary) m.set(s.date, s.summary);
    });
    return m;
  }, [summaries]);

  const runRegenerate = async (date: string, period: SummaryPeriod) => {
    setBusy(true);
    try {
      const existed =
        period === 'work' ? !!dayDetail?.work
        : period === 'personal' ? !!dayDetail?.personal
        : !!dayDetail?.daily;
      await api.generateSummary(date, period);
      const msgKey = existed ? 'calendar.summaryRegenerated' : 'calendar.summaryGenerated';
      showToast(t(msgKey, { label: periodLabel(period) }));
      await fetchDay(date);
      const r = rangeRef.current;
      if (r) await fetchRange(r.from, r.to);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t('calendar.generateFailed'));
    } finally {
      setBusy(false);
    }
  };

  const runDelete = async (date: string, period: SummaryPeriod) => {
    setBusy(true);
    try {
      await api.deleteSummary(date, period);
      showToast(t('calendar.summaryDeleted', { label: periodLabel(period) }));
      await fetchDay(date);
      const r = rangeRef.current;
      if (r) await fetchRange(r.from, r.to);
    } catch (e) {
      showToast(e instanceof Error ? e.message : t('calendar.deleteFailed'));
    } finally {
      setBusy(false);
    }
  };

  // Initial load: fetch all (range will be set by handleDatesSet)
  useEffect(() => {
    if (!summaries.length) {
      api.listSummaries().then((r) => setSummaries(r.summaries)).catch(() => {});
    }
    // Fetch file dates to show activity counts even when no summaries exist
    api.files({ limit: 10000 }).then((r) => {
      const counts = new Map<string, number>();
      r.files.forEach((f) => {
        if (!f.file_ctime) return;
        const date = f.file_ctime.slice(0, 10);
        counts.set(date, (counts.get(date) || 0) + 1);
      });
      setFileDateCounts(counts);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync per-day task donuts to the calendar DOM whenever progress changes
  // (and after FullCalendar re-renders cells for a new month). Runs on the
  // next tick so FullCalendar has finished mounting its day cells first.
  useEffect(() => {
    const calEl = calendarMainRef.current;
    if (!calEl) return;
    const tid = window.setTimeout(() => {
      calEl.querySelectorAll('.fc-daygrid-day-frame > .task-donut').forEach((n) => n.remove());
      calEl.querySelectorAll<HTMLElement>('.fc-daygrid-day').forEach((cell) => {
        const dateStr = cell.dataset.date;
        if (!dateStr) return;
        const p = progressByDate.get(dateStr);
        if (!p || p.total === 0) return;
        const frame = cell.querySelector('.fc-daygrid-day-frame');
        if (!frame) return;
        frame.insertAdjacentHTML('beforeend', buildDonutHTML(p.done, p.total));
      });
    }, 0);
    return () => window.clearTimeout(tid);
  }, [progressByDate, viewYear, viewMonth, buildDonutHTML]);

  // Inject a compact "🗂️ N 🏠 M" chip into each cell's day-top row (next to
  // the date number). Replaces the old per-summary FullCalendar event bars.
  useEffect(() => {
    const calEl = calendarMainRef.current;
    if (!calEl) return;
    const tid = window.setTimeout(() => {
      calEl.querySelectorAll('.fc-daygrid-day-top > .day-counts-chip').forEach((n) => n.remove());
      calEl.querySelectorAll<HTMLElement>('.fc-daygrid-day').forEach((cell) => {
        const dateStr = cell.dataset.date;
        if (!dateStr) return;
        const c = countsByDate.get(dateStr);
        if (!c || (c.work === 0 && c.personal === 0)) return;
        const top = cell.querySelector('.fc-daygrid-day-top');
        if (!top) return;
        const parts: string[] = [];
        if (c.work) parts.push(`<span class="day-counts-work">🗂️ ${c.work}</span>`);
        if (c.personal) parts.push(`<span class="day-counts-personal">🏠 ${c.personal}</span>`);
        top.insertAdjacentHTML('afterbegin', `<span class="day-counts-chip">${parts.join('')}</span>`);
      });
    }, 0);
    return () => window.clearTimeout(tid);
  }, [countsByDate, viewYear, viewMonth]);

  // Inject the one-line daily summary into each cell body, below the day-top.
  useEffect(() => {
    const calEl = calendarMainRef.current;
    if (!calEl) return;
    const tid = window.setTimeout(() => {
      calEl.querySelectorAll('.fc-daygrid-day-frame > .day-summary-line').forEach((n) => n.remove());
      calEl.querySelectorAll<HTMLElement>('.fc-daygrid-day').forEach((cell) => {
        const dateStr = cell.dataset.date;
        if (!dateStr) return;
        const summary = dailyByDate.get(dateStr);
        if (!summary) return;
        const frame = cell.querySelector('.fc-daygrid-day-frame');
        if (!frame) return;
        const top = frame.querySelector('.fc-daygrid-day-top');
        const div = document.createElement('div');
        div.className = 'day-summary-line';
        div.title = summary;
        div.textContent = summary;
        if (top && top.nextSibling) frame.insertBefore(div, top.nextSibling);
        else frame.appendChild(div);
      });
    }, 0);
    return () => window.clearTimeout(tid);
  }, [dailyByDate, viewYear, viewMonth]);

  // FullCalendar caches its inner column widths and won't reflow when the
  // outer grid shrinks (which happens whenever the detail pane opens/closes).
  // Watch the container with a ResizeObserver and force a remeasure every
  // frame the transition is running — that way the calendar tracks the
  // shrinking width instead of clipping Fri/Sat off-screen.
  useEffect(() => {
    const main = calendarMainRef.current;
    if (!main) return;
    const ro = new ResizeObserver(() => {
      calendarRef.current?.getApi().updateSize();
    });
    ro.observe(main);
    return () => ro.disconnect();
  }, []);

  // Restore selected date from URL (?date=YYYY-MM-DD) on mount,
  // so "← 캘린더" from GraphView returns the user to where they were.
  useEffect(() => {
    const dateParam = searchParams.get('date');
    if (dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam)) {
      setSelectedDate(dateParam);
      fetchDay(dateParam);
      const [y, m] = dateParam.split('-').map(Number);
      goTo(y, m - 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page calendar-page">
      {toast && <div className="toast">{toast}</div>}

      <div
        ref={calendarLayoutRef}
        className={`calendar-layout${selectedDate ? ' has-detail' : ''}`}
        style={{ ['--detail-w' as string]: `${detailWidth}px` }}
      >
        <div className="calendar-main" ref={calendarMainRef}>
          <div className="calendar-toolbar">
            <div className="calendar-toolbar-pickers">
              <select
                className="calendar-select"
                value={viewYear}
                onChange={(e) => goTo(Number(e.target.value), viewMonth)}
                aria-label={t('calendar.yearSelect')}
              >
                {yearOptions.map((y) => (
                  <option key={y} value={y}>{t('calendar.yearLabel', { n: y })}</option>
                ))}
              </select>
              <select
                className="calendar-select"
                value={viewMonth}
                onChange={(e) => goTo(viewYear, Number(e.target.value))}
                aria-label={t('calendar.monthSelect')}
              >
                {months.map((label, i) => (
                  <option key={i} value={i}>{label}</option>
                ))}
              </select>
            </div>
            <div className="calendar-toolbar-nav">
              <button className="btn btn-icon btn-ghost" onClick={goPrev} aria-label={t('calendar.prevMonth')}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="15 6 9 12 15 18" />
                </svg>
              </button>
              <button className="btn btn-ghost" onClick={goToday}>{t('calendar.today')}</button>
              <button className="btn btn-icon btn-ghost" onClick={goNext} aria-label={t('calendar.nextMonth')}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polyline points="9 6 15 12 9 18" />
                </svg>
              </button>
            </div>
          </div>

          <div className="calendar-fc-wrap" style={{ fontSize: `${fontSize}px` }}>
            <FullCalendar
              ref={calendarRef}
              plugins={[dayGridPlugin, interactionPlugin]}
              initialView="dayGridMonth"
              firstDay={0}
              height="100%"
              locale={i18n.resolvedLanguage || 'ko'}
              headerToolbar={false}
              datesSet={handleDatesSet}
              dateClick={handleDateClick}
              dayCellClassNames={(arg) =>
                selectedDate && toLocalISODate(arg.date) === selectedDate ? ['gv-selected'] : []
              }
              fixedWeekCount={true}
            />
          </div>

          <div className="calendar-fontsize-bar">
            <span className="calendar-fontsize-label">A</span>
            <input
              type="range"
              min={10}
              max={18}
              step={1}
              value={fontSize}
              onChange={(e) => {
                const v = Number(e.target.value);
                setFontSize(v);
                try { window.localStorage.setItem(CAL_FONTSIZE_KEY, String(v)); } catch { /* */ }
              }}
              aria-label={t('calendar.fontSizeLabel', { defaultValue: '텍스트 크기' })}
            />
            <span className="calendar-fontsize-label lg">A</span>
          </div>
        </div>

        {selectedDate && (
          <div
            className="calendar-resizer"
            onMouseDown={startResize}
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize detail panel"
            title="Drag to resize"
          >
            <span className="calendar-resizer-grip" aria-hidden="true" />
          </div>
        )}
        <aside className="calendar-detail">
          {!selectedDate ? (
            <div className="calendar-detail-empty">
              {t('calendar.detailEmpty')}
            </div>
          ) : (
            <DayDetail
              date={selectedDate}
              detail={dayDetail}
              loading={loading}
              busy={busy}
              onRegenerate={(period) => setConfirm({ kind: 'regenerate', date: selectedDate, period })}
              onDelete={(period) => setConfirm({ kind: 'delete', date: selectedDate, period })}
              onClose={() => {
                setSelectedDate(null);
                setDayDetail(null);
              }}
              onTasksChanged={() => {
                const r = rangeRef.current;
                if (r) fetchRange(r.from, r.to);
              }}
            />
          )}
        </aside>
      </div>

      {confirm && (
        <ConfirmModal
          action={confirm}
          busy={busy}
          onCancel={() => setConfirm(null)}
          onConfirm={async () => {
            const c = confirm;
            setConfirm(null);
            if (c.kind === 'regenerate') await runRegenerate(c.date, c.period);
            else await runDelete(c.date, c.period);
          }}
        />
      )}
    </div>
  );
}

interface DayDetailProps {
  date: string;
  detail: DaySummaryResponse | null;
  loading: boolean;
  busy: boolean;
  onRegenerate: (period: SummaryPeriod) => void;
  onDelete: (period: SummaryPeriod) => void;
  onClose: () => void;
  onTasksChanged: () => void;
}

function DayDetail({ date, detail, loading, busy, onRegenerate, onDelete, onClose, onTasksChanged }: DayDetailProps) {
  const { t } = useTranslation();
  if (loading) return <div className="loading">{t('calendar.loadingDay')}</div>;
  return (
    <div>
      <div className="calendar-detail-head">
        <div className="calendar-detail-date">{date}</div>
        <button
          type="button"
          className="btn btn-icon btn-ghost calendar-detail-close"
          onClick={onClose}
          aria-label={t('calendar.closeDetail')}
          title={t('calendar.closeDetail')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
      <TaskSection date={date} onChanged={onTasksChanged} />
      <SummaryBlock
        date={date}
        title={t('calendar.daily')}
        period="daily"
        emoji="📆"
        summary={detail?.daily ?? null}
        busy={busy}
        onRegenerate={onRegenerate}
        onDelete={onDelete}
      />
      <SummaryBlock
        date={date}
        title={t('calendar.work')}
        period="work"
        emoji="🗂️"
        summary={detail?.work ?? null}
        busy={busy}
        onRegenerate={onRegenerate}
        onDelete={onDelete}
      />
      <SummaryBlock
        date={date}
        title={t('calendar.personal')}
        period="personal"
        emoji="🏠"
        summary={detail?.personal ?? null}
        busy={busy}
        onRegenerate={onRegenerate}
        onDelete={onDelete}
      />
    </div>
  );
}

interface SummaryBlockProps {
  date: string;
  title: string;
  period: SummaryPeriod;
  emoji: string;
  summary: DailySummary | null;
  busy: boolean;
  onRegenerate: (period: SummaryPeriod) => void;
  onDelete: (period: SummaryPeriod) => void;
}

function SummaryBlock({ date, title, period, emoji, summary, busy, onRegenerate, onDelete }: SummaryBlockProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const showInGraph = (id: string) => {
    navigate(`/graph?focus=${encodeURIComponent(id)}&from=calendar&date=${encodeURIComponent(date)}`);
  };

  const openInExplorer = async (path: string) => {
    try {
      await api.openFolder(path);
    } catch (err) {
      console.error('openFolder failed:', err);
    }
  };

  return (
    <section className={`summary-block summary-${period}`}>
      <header className="summary-block-head">
        <h3>
          <span>{emoji}</span> {t('calendar.summaryHeading', { label: title })}
          <span
            className="summary-block-info"
            tabIndex={0}
            role="button"
            aria-label={t(`calendar.summaryHint.${period}`)}
          >
            ⓘ
            <span className="summary-block-info-popup" role="tooltip">
              {t(`calendar.summaryHint.${period}`)}
            </span>
          </span>
          {period !== 'daily' && summary?.work_hours && (
            <span className="summary-block-hours">· {summary.work_hours}</span>
          )}
        </h3>
        <div className="btn-group">
          <button
            className="btn"
            disabled={busy}
            onClick={() => onRegenerate(period)}
          >
            {summary ? t('calendar.regenerate') : t('calendar.generate')}
          </button>
          {summary && (
            <button className="btn btn-danger" disabled={busy} onClick={() => onDelete(period)}>
              {t('common.delete')}
            </button>
          )}
        </div>
      </header>

      {!summary ? (
        <div className="summary-block-empty">
          {t('calendar.summaryEmpty')}
        </div>
      ) : (
        <>
          <div className="summary-block-stats">
            <span>📄 {summary.file_count} files</span>
            {summary.created_count > 0 && <span className="stat-create">+ {summary.created_count}</span>}
            {summary.modified_count > 0 && <span className="stat-modify">~ {summary.modified_count}</span>}
            {summary.deleted_count > 0 && <span className="stat-delete">− {summary.deleted_count}</span>}
          </div>
          <div className="summary-block-body">
            <Markdown>{summary.summary}</Markdown>
          </div>
          {summary.files && summary.files.length > 0 && (
            <details className="summary-block-files">
              <summary>{t('calendar.relatedFiles', { count: summary.files.length })}</summary>
              <ul>
                {summary.files.map((f) => {
                  const basename = f.name.split(/[\\/]/).pop() || f.name;
                  return (
                    <li key={f.id}>
                      <button
                        type="button"
                        className="summary-file-name"
                        onClick={() => showInGraph(f.id)}
                        title={t('calendar.showInGraphTitle')}
                      >
                        {basename}
                      </button>
                      <button
                        type="button"
                        className="summary-file-open"
                        onClick={() => openInExplorer(f.name)}
                        title={t('calendar.openFolderTitle')}
                        aria-label={t('calendar.openFolderTitle')}
                      >
                        📂
                      </button>
                    </li>
                  );
                })}
              </ul>
            </details>
          )}
          {summary.generated_at && (
            <div className="summary-block-meta">
              {t('calendar.generatedAt')}: {new Date(summary.generated_at).toLocaleString()}
            </div>
          )}
        </>
      )}
    </section>
  );
}

interface ConfirmModalProps {
  action: NonNullable<ConfirmAction>;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

function ConfirmModal({ action, busy, onCancel, onConfirm }: ConfirmModalProps) {
  const { t } = useTranslation();
  const isDelete = action.kind === 'delete';
  const periodLabel = t(
    action.period === 'work' ? 'calendar.work'
    : action.period === 'personal' ? 'calendar.personal'
    : 'calendar.daily',
  );
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{isDelete ? t('calendar.confirmDeleteTitle') : t('calendar.confirmRegenerateTitle')}</h3>
        <p>
          <code>{action.date}</code> · {t('calendar.confirmContext', { label: periodLabel })}
        </p>
        <p className="modal-desc">
          {isDelete ? t('calendar.deleteDesc') : t('calendar.regenerateDesc')}
        </p>
        <div className="modal-actions">
          <button className="btn" disabled={busy} onClick={onCancel}>{t('common.cancel')}</button>
          <button
            className={isDelete ? 'btn btn-danger' : 'btn btn-primary'}
            disabled={busy}
            onClick={onConfirm}
          >
            {isDelete ? t('common.delete') : t('calendar.regenerate')}
          </button>
        </div>
      </div>
    </div>
  );
}
