import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { api } from './api';
import type { ScanProgress } from './types';

/**
 * Inline scan-progress monitor. Lives in the Settings page just below the
 * hero. Hidden when status==='idle' and no recent finish is being shown.
 *
 * Behavior:
 *   - just requested     → render a short "preparing" state immediately
 *   - scanning / paused → always rendered
 *   - done / error      → rendered for 30s after the transition, then hides
 *   - idle              → not rendered (saves vertical space)
 *
 * Uses the same /api/watcher/progress endpoint as ScanToast (1.5s poll).
 */

const HIDE_AFTER_DONE_MS = 30_000;
const PENDING_VISIBLE_MS = 5_000;

interface ScanMonitorProps {
  requestToken?: number;
  requestedMode?: string;
}

function formatTime(sec: number, t: TFunction): string {
  if (sec <= 0) return '—';
  if (sec < 60) return t('scan.timeSeconds', { n: Math.round(sec) });
  if (sec < 3600) return t('scan.timeMinSec', { m: Math.floor(sec / 60), s: Math.round(sec % 60) });
  const h = Math.floor(sec / 3600);
  const m = Math.round((sec % 3600) / 60);
  return t('scan.timeHourMin', { h, m });
}

function modeLabel(mode: string | undefined, t: TFunction): string {
  switch (mode) {
    case 'all':       return t('settings.extractAll',       { defaultValue: '전체 추출' });
    case 'documents': return t('settings.extractDocuments', { defaultValue: '문서만 추출' });
    case 'images':    return t('settings.extractImages',    { defaultValue: '이미지만 추출' });
    case 'skeleton':  return t('settings.scanSkeleton',     { defaultValue: '디스크 다시 스캔' });
    default:          return '—';
  }
}

export default function ScanMonitor({ requestToken = 0, requestedMode }: ScanMonitorProps) {
  const { t } = useTranslation();
  const [scan, setScan] = useState<ScanProgress | null>(null);
  const [hideAfter, setHideAfter] = useState<number | null>(null);
  const [pendingRequest, setPendingRequest] = useState<{
    token: number;
    mode?: string;
    startedAt: number;
  } | null>(null);
  const lastStatusRef = useRef<string>('');

  const refreshProgress = useCallback(async () => {
    try {
      const p = await api.scanProgress();
      setScan(p);
      // When status flips from a live state into a terminal state, schedule
      // a hide 30s later so the user can read the result without dismissing.
      if (
        (p.status === 'done' || p.status === 'error') &&
        (lastStatusRef.current === 'scanning' || lastStatusRef.current === 'paused')
      ) {
        setHideAfter(Date.now() + HIDE_AFTER_DONE_MS);
      }
      // Conversely, a new scan starts → cancel any pending hide.
      if (p.status === 'scanning') {
        setHideAfter(null);
      }
      if (
        p.status === 'scanning' ||
        p.status === 'paused' ||
        !!p.last_no_op_mode
      ) {
        setPendingRequest(null);
      }
      lastStatusRef.current = p.status;
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    refreshProgress();
    const tick = setInterval(refreshProgress, 1500);
    return () => clearInterval(tick);
  }, [refreshProgress]);

  useEffect(() => {
    if (!requestToken) return;
    setPendingRequest({ token: requestToken, mode: requestedMode, startedAt: Date.now() });
    refreshProgress();
  }, [requestToken, requestedMode, refreshProgress]);

  const pendingActive =
    pendingRequest !== null && Date.now() - pendingRequest.startedAt < PENDING_VISIBLE_MS;

  const pendingPanel = pendingActive ? (
    <section className="scan-monitor scan-monitor-pending" aria-live="polite">
      <header className="scan-monitor-head">
        <span className="scan-monitor-led scanning" aria-hidden="true" />
        <span className="scan-monitor-title">
          {t('scan.statusStarting', { defaultValue: '분석 준비 중' })}
        </span>
        <span className="scan-monitor-mode">{modeLabel(pendingRequest.mode, t)}</span>
      </header>
      <div
        className="scan-monitor-bar scan-monitor-bar-indeterminate"
        role="progressbar"
        aria-label={t('scan.statusStarting', { defaultValue: '분석 준비 중' })}
      >
        <div className="scan-monitor-bar-fill indeterminate" />
      </div>
      <div className="scan-monitor-summary">
        {t('scan.startingHint', { defaultValue: '파일 목록을 확인하고 분석 대상을 준비하고 있습니다.' })}
      </div>
    </section>
  ) : null;

  if (!scan) return pendingPanel;
  if (scan.status === 'idle') return pendingPanel;
  if (scan.status === 'done' && scan.total === 0) return pendingPanel; // no-op skeleton scan
  if (
    pendingActive &&
    (scan.status === 'done' || scan.status === 'error') &&
    pendingRequest?.startedAt &&
    (!scan.started_at || Date.parse(scan.started_at) < pendingRequest.startedAt - 2_000)
  ) {
    return pendingPanel;
  }
  if ((scan.status === 'done' || scan.status === 'error') && hideAfter !== null && Date.now() > hideAfter) {
    return null;
  }

  const isActive = scan.status === 'scanning' || scan.status === 'paused';
  const pct = scan.total > 0 ? Math.round((scan.processed / scan.total) * 100) : 0;
  const remaining = Math.max(scan.total - scan.processed, 0);

  let indicatorClass = 'scan-monitor-led';
  let headTitle: string;
  if (scan.status === 'scanning') {
    indicatorClass += ' scanning';
    headTitle = t('scan.statusScanning', { defaultValue: '분석 진행 중' });
  } else if (scan.status === 'paused') {
    indicatorClass += ' paused';
    headTitle = t('scan.statusPaused', { defaultValue: '일시정지됨' });
  } else if (scan.status === 'done') {
    indicatorClass += ' done';
    headTitle = t('scan.statusDone', { defaultValue: '분석 완료' });
  } else {
    indicatorClass += ' error';
    headTitle = t('scan.statusError', { defaultValue: '오류' });
  }

  // Filename-only display (drop the path)
  const fileBasename = scan.current_file
    ? scan.current_file.split('/').pop()?.split('\\').pop() ?? scan.current_file
    : '';

  return (
    <section className={`scan-monitor scan-monitor-${scan.status}`} aria-live="polite">
      <header className="scan-monitor-head">
        <span className={indicatorClass} aria-hidden="true" />
        <span className="scan-monitor-title">{headTitle}</span>
        <span className="scan-monitor-mode">{modeLabel(scan.mode, t)}</span>
        <span className="scan-monitor-spacer" />
        {scan.status === 'scanning' && (
          <button
            type="button"
            className="scan-monitor-action"
            onClick={() => api.scanPause().catch(() => { /* silent */ })}
          >
            {t('scan.pause', { defaultValue: '일시정지' })}
          </button>
        )}
        {scan.status === 'paused' && (
          <button
            type="button"
            className="scan-monitor-action"
            onClick={() => api.scanResume().catch(() => { /* silent */ })}
          >
            {t('scan.resume', { defaultValue: '재개' })}
          </button>
        )}
        {(scan.status === 'done' || scan.status === 'error') && (
          <button
            type="button"
            className="scan-monitor-action subtle"
            aria-label={t('scan.dismiss', { defaultValue: '닫기' })}
            onClick={() => setHideAfter(0)}
          >
            ×
          </button>
        )}
      </header>

      {isActive && (
        <>
          <div
            className="scan-monitor-bar"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div className="scan-monitor-bar-fill" style={{ width: `${pct}%` }} />
          </div>

          <div className="scan-monitor-grid">
            <div className="scan-monitor-cell scan-monitor-cell-wide">
              <span className="scan-monitor-cell-label">
                {t('scan.currentFile', { defaultValue: '현재 파일' })}
              </span>
              <span className="scan-monitor-cell-value mono" title={scan.current_file}>
                {fileBasename || '—'}
              </span>
            </div>
            <div className="scan-monitor-cell">
              <span className="scan-monitor-cell-label">
                {t('scan.progressLabel', { defaultValue: '진행' })}
              </span>
              <span className="scan-monitor-cell-value">
                {scan.processed} / {scan.total}
                <span className="scan-monitor-cell-sub">  ({pct}%)</span>
              </span>
            </div>
            <div className="scan-monitor-cell">
              <span className="scan-monitor-cell-label">
                {t('scan.remainingLabel', { defaultValue: '남음' })}
              </span>
              <span className="scan-monitor-cell-value">
                {remaining}
              </span>
            </div>
            <div className="scan-monitor-cell">
              <span className="scan-monitor-cell-label">
                {t('scan.elapsedLabel', { defaultValue: '경과' })}
              </span>
              <span className="scan-monitor-cell-value">{formatTime(scan.elapsed_sec, t)}</span>
            </div>
            <div className="scan-monitor-cell">
              <span className="scan-monitor-cell-label">
                {t('scan.etaLabel', { defaultValue: '남은 시간' })}
              </span>
              <span className="scan-monitor-cell-value">{formatTime(scan.eta_sec, t)}</span>
            </div>
            <div className="scan-monitor-cell">
              <span className="scan-monitor-cell-label">
                {t('scan.speedLabel', { defaultValue: '평균' })}
              </span>
              <span className="scan-monitor-cell-value">
                {scan.avg_sec_per_file > 0
                  ? t('scan.speedAvg', { n: scan.avg_sec_per_file })
                  : '—'}
              </span>
            </div>
          </div>
        </>
      )}

      {scan.status === 'done' && (
        <div className="scan-monitor-summary">
          {t('scan.completedCount', {
            count: scan.processed,
            time: formatTime(scan.elapsed_sec, t),
            defaultValue: `${scan.processed}개 파일 분석 완료 (소요: ${formatTime(scan.elapsed_sec, t)})`,
          })}
        </div>
      )}

      {scan.status === 'error' && (
        <div className="scan-monitor-summary scan-monitor-error">
          {scan.error || t('scan.statusError', { defaultValue: '오류' })}
        </div>
      )}
    </section>
  );
}
