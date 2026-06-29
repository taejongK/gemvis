import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { api } from './api';
import type { ScanProgress } from './types';

function formatTime(sec: number, t: TFunction): string {
  if (sec <= 0) return '-';
  if (sec < 60) return t('scan.timeSeconds', { n: Math.round(sec) });
  if (sec < 3600) return t('scan.timeMinSec', { m: Math.floor(sec / 60), s: Math.round(sec % 60) });
  const h = Math.floor(sec / 3600);
  const m = Math.round((sec % 3600) / 60);
  return t('scan.timeHourMin', { h, m });
}

export default function ScanToast() {
  const { t } = useTranslation();
  const location = useLocation();
  const [scan, setScan] = useState<ScanProgress | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // Pages with an inline ScanMonitor use the same data, so hide the floating
  // toast there to avoid double UI.
  const hasInlineScanMonitor =
    location.pathname.startsWith('/settings') ||
    location.pathname.startsWith('/graph');

  useEffect(() => {
    if (hasInlineScanMonitor) {
      setScan(null);
      return;
    }
    let timer: ReturnType<typeof setTimeout> | null = null;
    let active = true;
    const poll = async () => {
      if (!active || document.hidden) {
        timer = setTimeout(poll, 5000);
        return;
      }
      try {
        const p = await api.scanProgress();
        setScan(p);
        if (p.status === 'scanning' || p.status === 'paused') {
          setDismissed(false);
          timer = setTimeout(poll, 1500);
        } else {
          timer = setTimeout(poll, 15_000);
        }
      } catch {
        timer = setTimeout(poll, 15_000);
      }
    };
    poll();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [hasInlineScanMonitor]);

  if (hasInlineScanMonitor) return null;
  if (!scan || scan.status === 'idle' || dismissed) return null;
  // Don't pop a toast for a no-op scan — e.g. skeleton-only mode finished
  // immediately, or "everything already analyzed" both produce
  // total=0/processed=0 in a 'done' state, which reads as misleading garbage
  // ("0개 파일 분석 완료 (소요: -)").
  if (scan.status === 'done' && scan.total === 0) return null;

  const pct = scan.total > 0 ? Math.round((scan.processed / scan.total) * 100) : 0;
  const isActive = scan.status === 'scanning' || scan.status === 'paused';

  return (
    <div style={{
      position: 'fixed',
      bottom: 36,
      right: 16,
      width: 340,
      background: 'var(--bg-elev)',
      border: '1px solid var(--border-hi)',
      borderRadius: 10,
      padding: '14px 16px',
      zIndex: 9000,
      boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
    }}>
      {/* header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
          {scan.status === 'scanning' && t('scan.statusScanning')}
          {scan.status === 'paused' && t('scan.statusPaused')}
          {scan.status === 'done' && t('scan.statusDone')}
          {scan.status === 'error' && t('scan.statusError')}
        </span>
        {!isActive && (
          <button
            onClick={() => setDismissed(true)}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 16 }}
          >
            ×
          </button>
        )}
      </div>

      {isActive && (
        <>
          {/* progress bar */}
          <div style={{ background: 'var(--surface-2)', borderRadius: 4, height: 6, overflow: 'hidden', marginBottom: 10 }}>
            <div style={{
              width: `${pct}%`,
              height: '100%',
              background: scan.status === 'paused' ? 'var(--warning)' : 'var(--accent-1)',
              borderRadius: 4,
              transition: 'width 0.4s ease',
            }} />
          </div>

          {/* stats */}
          <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7 }}>
            <div>
              <span style={{ color: 'var(--text-muted)', marginRight: 6 }}>{t('scan.analyzingLabel')}:</span>
              {scan.processed} / {scan.total}  ({pct}%)
            </div>
            {scan.current_file && (
              <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <span style={{ color: 'var(--text-muted)', marginRight: 6 }}>{t('scan.currentFile')}:</span>
                {scan.current_file}
              </div>
            )}
            <div>
              <span style={{ color: 'var(--text-muted)', marginRight: 6 }}>{t('scan.etaLabel')}:</span>
              {formatTime(scan.eta_sec, t)}
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)', marginRight: 6 }}>{t('scan.speedLabel')}:</span>
              {t('scan.speedAvg', { n: scan.avg_sec_per_file })}
            </div>
          </div>

          {/* buttons */}
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            {scan.status === 'scanning' ? (
              <button
                onClick={() => api.scanPause()}
                style={{
                  flex: 1, padding: '5px 0', fontSize: 12, borderRadius: 5, cursor: 'pointer',
                  background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-dim)',
                }}
              >
                {t('scan.pause')}
              </button>
            ) : (
              <button
                onClick={() => api.scanResume()}
                style={{
                  flex: 1, padding: '5px 0', fontSize: 12, borderRadius: 5, cursor: 'pointer',
                  background: 'var(--accent-soft)', border: '1px solid var(--accent-border)', color: 'var(--accent-1)',
                }}
              >
                {t('scan.resume')}
              </button>
            )}
          </div>
        </>
      )}

      {scan.status === 'done' && (
        <div style={{ fontSize: 12, color: 'var(--success)' }}>
          {t('scan.completedCount', { count: scan.processed, time: formatTime(scan.elapsed_sec, t) })}
        </div>
      )}

      {scan.status === 'error' && (
        <div style={{ fontSize: 12, color: 'var(--danger)' }}>
          {scan.error}
        </div>
      )}
    </div>
  );
}
