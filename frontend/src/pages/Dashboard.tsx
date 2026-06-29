import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api';
import type { FileListResponse, AnalysisStatus } from '../types';

const NODE_COLORS: Record<string, string> = {
  file: 'var(--node-file)',
  person: 'var(--node-person)',
  place: 'var(--node-place)',
  project: 'var(--node-project)',
  event: 'var(--node-event)',
  date: 'var(--node-date)',
  tag: 'var(--node-tag)',
};

const CATEGORY_ICONS: Record<string, string> = {
  memo: '📝', photo: '📸', screenshot: '🖼️', document: '📄',
  voice_memo: '🎤', code: '⌨️', data: '📊', other: '📎',
};

const STATUS_META: Record<AnalysisStatus, { icon: string; key: string; color: string }> = {
  pending:    { icon: '⏳', key: 'dashboard.statusPending',    color: 'var(--text-muted)' },
  processing: { icon: '⚙️', key: 'dashboard.statusProcessing', color: 'var(--accent-1)' },
  completed:  { icon: '✅', key: 'dashboard.statusCompleted',  color: 'var(--node-file)' },
  failed:     { icon: '❌', key: 'dashboard.statusFailed',     color: 'var(--node-event)' },
};

export default function Dashboard() {
  const { t } = useTranslation();
  const [data, setData] = useState<FileListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<string>('file_mtime');
  const [order, setOrder] = useState<string>('desc');
  const [statusFilter, setStatusFilter] = useState<AnalysisStatus | undefined>(undefined);
  const [expandedSummaries, setExpandedSummaries] = useState<Set<string>>(new Set());

  const toggleSummary = (fileId: string) => {
    setExpandedSummaries((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  };

  const load = () => {
    setLoading(true);
    api.files({
      page,
      limit: 50,
      sort_by: sortBy,
      order,
      status: statusFilter,
      include_stats: true,
    }).then(setData).finally(() => setLoading(false));
  };

  useEffect(load, [page, sortBy, order, statusFilter]);

  if (!data && !loading) return <p className="empty-state">{t('dashboard.loadError')}</p>;

  const { files = [], pagination = { total: 0, page: 1, total_pages: 1 }, stats, status_counts } = data ?? {};
  const maxTypeCount = stats ? Math.max(...Object.values(stats.node_types), 1) : 1;
  // 통일된 정의: "분석 완료" = analysis_status === 'completed'.
  // stats.node_types.file은 skeleton 포함 전체 file 노드 수라 완료 건수와 다름.
  const completedCount = status_counts?.completed ?? 0;
  const totalFileCount = pagination.total;

  const catCounts: Record<string, number> = {};
  for (const f of files) {
    const c = f.category || 'other';
    catCounts[c] = (catCounts[c] || 0) + 1;
  }
  const categories = Object.entries(catCounts).sort(([, a], [, b]) => b - a);
  const statusCounts: Record<AnalysisStatus, number> = status_counts ?? {
    pending: 0, processing: 0, completed: 0, failed: 0,
  };

  const formatDate = (isoStr: string) => {
    if (!isoStr) return '-';
    const d = new Date(isoStr);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(order === 'desc' ? 'asc' : 'desc');
    } else {
      setSortBy(field);
      setOrder('desc');
    }
    setPage(1);
  };

  const renderSortIcon = (field: string) => {
    if (sortBy !== field) return ' ⇅';
    return order === 'desc' ? ' ↓' : ' ↑';
  };

  const completionPct = totalFileCount > 0
    ? Math.round((completedCount / totalFileCount) * 100)
    : 0;

  return (
    <div className="page dashboard-page">
      {/* KPI strip — primary stats at a glance */}
      <div className="kpi-strip">
        <div className="kpi kpi-hero">
          <div className="kpi-label">{t('nav.graph')}</div>
          <div className={`kpi-value kpi-value-grad${loading && !data ? ' skeleton' : ''}`}>
            {loading && !data ? '—' : (stats?.total_nodes ?? 0).toLocaleString()}
          </div>
          <div className="kpi-sub">
            {loading && !data ? '—' : (stats?.total_edges ?? 0).toLocaleString()} relations
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">{t('dashboard.analyzedLabel')}</div>
          <div className={`kpi-value${loading && !data ? ' skeleton' : ''}`}>
            {loading && !data ? '—' : completedCount.toLocaleString()}
            <span className="kpi-fraction">
              / {loading && !data ? '—' : totalFileCount.toLocaleString()}
            </span>
          </div>
          <div className="kpi-progress" aria-hidden="true">
            <div className="kpi-progress-fill" style={{ width: `${completionPct}%` }} />
          </div>
          <div className="kpi-sub">{loading && !data ? '—' : completionPct}%</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">{t('dashboard.statusProcessing')}</div>
          <div className={`kpi-value kpi-value-accent${loading && !data ? ' skeleton' : ''}`}>
            {loading && !data ? '—' : (statusCounts.processing ?? 0).toLocaleString()}
          </div>
          <div className="kpi-sub">
            {loading && !data ? '—' : statusCounts.pending ?? 0} {t('dashboard.statusPending').toLowerCase()}
          </div>
        </div>
        <div className="kpi kpi-privacy">
          <div className="kpi-privacy-icon" aria-hidden="true">🔒</div>
          <div>
            <div className="kpi-privacy-title">{t('dashboard.privacyTitle')}</div>
            <div className="kpi-privacy-desc">{t('dashboard.privacyDesc')}</div>
          </div>
        </div>
      </div>

      {/* Distribution row — node types + file categories, side-by-side */}
      <div className="distribution-row">
        <div className="bento">
          <div className="bento-label">
            <span className="bento-label-icon">▦</span>
            {t('dashboard.nodeTypeDist')}
          </div>
          {loading && !data ? (
            <div className="bento-sub">{t('common.loading')}</div>
          ) : (
            <div className="type-bars">
              {Object.entries(stats?.node_types ?? {})
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <div key={type} className="type-bar-row">
                    <span
                      className="type-bar-label"
                      style={{ color: NODE_COLORS[type] ?? 'var(--text-dim)' }}
                    >
                      {type}
                    </span>
                    <div className="type-bar-track">
                      <div
                        className="type-bar-fill"
                        style={{
                          width: `${(count / maxTypeCount) * 100}%`,
                          background: NODE_COLORS[type] ?? 'var(--accent-1)',
                        }}
                      />
                    </div>
                    <span className="type-bar-count">{count}</span>
                  </div>
                ))}
            </div>
          )}
        </div>

        <div className="bento">
          <div className="bento-label">
            <span className="bento-label-icon">▣</span>
            {t('dashboard.fileCategory')}
          </div>
          {loading && !data ? (
            <div className="bento-sub">{t('common.loading')}</div>
          ) : categories.length === 0 ? (
            <div className="bento-sub">{t('dashboard.noAnalyzedYet')}</div>
          ) : (
            <div className="type-bars">
              {categories.map(([cat, count]) => (
                <div key={cat} className="type-bar-row">
                  <span className="type-bar-label">
                    {CATEGORY_ICONS[cat] ?? '📎'} {cat}
                  </span>
                  <div className="type-bar-track">
                    <div
                      className="type-bar-fill"
                      style={{
                        width: `${(count / Math.max(...Object.values(catCounts))) * 100}%`,
                        background: 'var(--accent-grad)',
                      }}
                    />
                  </div>
                  <span className="type-bar-count">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bento-grid">
        <div className="bento bento-col-12 bento-files">
          <div className="files-card-header">
            <div className="bento-label files-card-title">
              <span className="bento-label-icon">📋</span>
              {t('dashboard.fileList', { total: pagination.total })}
              <button
                type="button"
                className="files-refresh"
                onClick={load}
                aria-label={t('common.refresh')}
                title={t('common.refresh')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 12a9 9 0 1 1-3-6.7" />
                  <polyline points="21 4 21 12 13 12" />
                </svg>
              </button>
            </div>

            <div className="status-filter-chips" role="tablist" aria-label={t('dashboard.colStatus')}>
              <button
                role="tab"
                aria-selected={statusFilter === undefined}
                className={`status-chip${statusFilter === undefined ? ' active' : ''}`}
                onClick={() => { setStatusFilter(undefined); setPage(1); }}
              >
                {t('common.all')}
                <span className="status-chip-count">{totalFileCount}</span>
              </button>
              {(['pending', 'processing', 'completed', 'failed'] as AnalysisStatus[]).map((s) => {
                const meta = STATUS_META[s];
                const label = t(meta.key);
                const count = statusCounts[s] ?? 0;
                return (
                  <button
                    key={s}
                    role="tab"
                    aria-selected={statusFilter === s}
                    className={`status-chip status-chip-${s}${statusFilter === s ? ' active' : ''}`}
                    onClick={() => { setStatusFilter(s); setPage(1); }}
                    title={label}
                  >
                    <span className="status-chip-icon">{meta.icon}</span>
                    {label}
                    <span className="status-chip-count">{count}</span>
                  </button>
                );
              })}
            </div>

            <div className="pagination-row">
              {pagination.total_pages > 1 && (
                <>
                  <button
                    className="btn btn-ghost btn-icon"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                    aria-label={t('common.prev')}
                  >
                    ‹
                  </button>
                  <span className="pagination-status">
                    {page} / {pagination.total_pages}
                  </span>
                  <button
                    className="btn btn-ghost btn-icon"
                    disabled={page === pagination.total_pages}
                    onClick={() => setPage(page + 1)}
                    aria-label={t('common.next')}
                  >
                    ›
                  </button>
                </>
              )}
            </div>
          </div>

          {loading && !data ? (
            <div className="empty-state files-empty loading">
              {t('common.loading')}
            </div>
          ) : files.length === 0 ? (
            <div className="empty-state files-empty">
              {t('dashboard.emptyHint')}
            </div>
          ) : (
            <div className="files-table-scroll">
            <table className="files-table">
              <thead>
                <tr>
                  <th>{t('dashboard.colStatus')}</th>
                  <th>{t('dashboard.colFile')}</th>
                  <th>{t('dashboard.colCategory')}</th>
                  <th>{t('dashboard.colSummary')}</th>
                  <th className="th-sortable" onClick={() => toggleSort('file_ctime')}>
                    {t('dashboard.colCreated')}{renderSortIcon('file_ctime')}
                  </th>
                  <th className="th-sortable" onClick={() => toggleSort('file_mtime')}>
                    {t('dashboard.colModified')}{renderSortIcon('file_mtime')}
                  </th>
                  <th className="th-sortable" onClick={() => toggleSort('added_at')}>
                    {t('dashboard.colAdded')}{renderSortIcon('added_at')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => {
                  const meta = STATUS_META[f.analysis_status];
                  const label = t(meta.key);
                  return (
                    <tr key={f.file_id}>
                      <td>
                        <span
                          className={`status-badge status-badge-${f.analysis_status}`}
                          title={f.error ?? label}
                        >
                          <span aria-hidden="true">{meta.icon}</span> {label}
                        </span>
                      </td>
                      <td className="file-name-cell">
                        <div className="file-name-primary">{f.file_name}</div>
                        <div className="file-name-secondary">{f.file_id}</div>
                      </td>
                      <td>
                        {f.category ? (
                          <span className="badge">
                            {CATEGORY_ICONS[f.category] ?? '📎'} {f.category}
                          </span>
                        ) : (
                          <span className="cell-muted">—</span>
                        )}
                      </td>
                      <td className="summary-cell">
                        {(() => {
                          const hasSummary = !!f.summary;
                          const text = f.summary || (f.analysis_status === 'pending' ? t('dashboard.summaryPending') : f.analysis_status === 'processing' ? t('dashboard.summaryProcessing') : f.error ? `⚠ ${f.error}` : '-');
                          if (!hasSummary) {
                            return <div className="summary-text" title={text}>{text}</div>;
                          }
                          return (
                            <ExpandableSummary
                              text={text}
                              fileId={f.file_id}
                              expanded={expandedSummaries.has(f.file_id)}
                              onToggle={toggleSummary}
                            />
                          );
                        })()}
                      </td>
                      <td className="date">{formatDate(f.file_ctime)}</td>
                      <td className="date">{formatDate(f.file_mtime)}</td>
                      <td className="date">{formatDate(f.added_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface ExpandableSummaryProps {
  text: string;
  fileId: string;
  expanded: boolean;
  onToggle: (id: string) => void;
}

function ExpandableSummary({ text, fileId, expanded, onToggle }: ExpandableSummaryProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [truncated, setTruncated] = useState(false);

  // Measure after layout. Only meaningful when the clamp is active —
  // when expanded, scrollHeight equals clientHeight and the result would
  // be wrong, so we skip the measurement in that case and keep the prior
  // truncated state.
  useLayoutEffect(() => {
    if (expanded) return;
    const el = ref.current;
    if (!el) return;
    // +1 guards against sub-pixel rounding making short text look truncated.
    setTruncated(el.scrollHeight > el.clientHeight + 1);
  }, [text, expanded]);

  const isInteractive = truncated || expanded;
  const handleClick = isInteractive ? () => onToggle(fileId) : undefined;

  return (
    <div
      ref={ref}
      className={`summary-text${isInteractive ? ' expandable' : ''}${expanded ? ' expanded' : ''}`}
      role={isInteractive ? 'button' : undefined}
      tabIndex={isInteractive ? 0 : -1}
      title={expanded || !truncated ? '' : text}
      onClick={handleClick}
      onKeyDown={isInteractive ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onToggle(fileId);
        }
      } : undefined}
    >
      <span className="summary-text-body">{text}</span>
      {isInteractive && (
        <svg
          className={`summary-chevron${expanded ? ' rotated' : ''}`}
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      )}
    </div>
  );
}
