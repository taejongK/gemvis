import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from './api';

/**
 * Lightweight floating toast that fires when the most recent extraction
 * request had nothing to do (everything already analyzed / no new files
 * matched). Distinct from ScanToast (which tracks a *running* scan), and
 * mounted at the App level so it works on every tab — including /settings,
 * where ScanToast itself is suppressed.
 *
 * Polling is shared in spirit with ScanToast (1.5s) but we ack as soon as
 * we display, so the backend flag never triggers twice for the same event.
 */

const AUTO_DISMISS_MS = 5_000;

export default function NoopToast() {
  const { t } = useTranslation();
  const [message, setMessage] = useState<string | null>(null);
  const acked = useRef(false);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let active = true;
    const poll = async () => {
      if (!active || document.hidden || acked.current) {
        timer = setTimeout(poll, 8000);
        return;
      }
      try {
        const p = await api.scanProgress();
        if (!p.last_no_op_mode) {
          timer = setTimeout(poll, 8000);
          return;
        }
        acked.current = true;
        api.scanAckNoop().catch(() => { /* silent */ });

        const key =
          p.last_no_op_mode === 'documents' ? 'scan.noopDocuments' :
          p.last_no_op_mode === 'images'    ? 'scan.noopImages'    :
          p.last_no_op_mode === 'skeleton'  ? 'scan.noopSkeleton'  :
                                              'scan.noopAll';
        setMessage(t(key));

        setTimeout(() => {
          setMessage(null);
          acked.current = false;
        }, AUTO_DISMISS_MS);
      } catch { /* silent */ }
      timer = setTimeout(poll, 8000);
    };
    poll();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [t]);

  if (!message) return null;

  return (
    <div className="noop-toast" role="status" aria-live="polite">
      <span className="noop-toast-icon" aria-hidden="true">ⓘ</span>
      <span className="noop-toast-text">{message}</span>
      <button
        type="button"
        className="noop-toast-close"
        aria-label={t('scan.dismiss', { defaultValue: '닫기' })}
        onClick={() => {
          setMessage(null);
          acked.current = false;
        }}
      >
        ×
      </button>
    </div>
  );
}
