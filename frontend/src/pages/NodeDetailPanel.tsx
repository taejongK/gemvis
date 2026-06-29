import { useEffect, useState } from 'react';
import type { RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api';
import type { GraphNode, FileRecord, NodeInsights } from '../types';

interface Props {
  node: GraphNode;
  adjacency: Map<string, Set<string>>;
  graphNodes: GraphNode[];
  onNavigate: (nodeId: string) => void;
  onClose: () => void;
  width?: number;
  asideRef?: RefObject<HTMLElement | null>;
  onResizeStart?: (e: React.MouseEvent) => void;
}

const TYPE_LABELS: Record<string, string> = {
  file: '📄', person: '👤', place: '📍', project: '📁',
  event: '📅', date: '🕐', tag: '🏷',
};

const ENTITY_KEYS = ['people', 'places', 'projects', 'dates', 'events'] as const;
const ENTITY_TYPE_MAP: Record<string, string> = {
  people: 'person', places: 'place', projects: 'project',
  dates: 'date', events: 'event',
};

export default function NodeDetailPanel({ node, adjacency, graphNodes, onNavigate, onClose, width, asideRef, onResizeStart }: Props) {
  const { t } = useTranslation();
  const isFile = node.type === 'file';

  const [fileDetail, setFileDetail] = useState<FileRecord | null>(null);
  const [insights, setInsights] = useState<NodeInsights | null>(null);
  const [loadingFile, setLoadingFile] = useState(false);
  const [loadingInsights, setLoadingInsights] = useState(false);

  useEffect(() => {
    setFileDetail(null);
    setInsights(null);

    if (isFile) {
      const fileId = node.id.replace(/^file:/, '');
      setLoadingFile(true);
      api.file(fileId).then(setFileDetail).catch(() => {}).finally(() => setLoadingFile(false));
    }

    setLoadingInsights(true);
    api.nodeInsights(node.id).then(setInsights).catch(() => {}).finally(() => setLoadingInsights(false));
  }, [node.id, isFile]);

  const neighbors = adjacency.get(node.id);
  const nodeMap = new Map(graphNodes.map((n) => [n.id, n]));

  const connectedFiles = neighbors
    ? [...neighbors].filter((id) => nodeMap.get(id)?.type === 'file').map((id) => nodeMap.get(id)!)
    : [];
  const connectedEntities = neighbors
    ? [...neighbors].filter((id) => {
        const t = nodeMap.get(id)?.type;
        return t && t !== 'file';
      }).map((id) => nodeMap.get(id)!)
    : [];

  return (
    <aside
      ref={asideRef as RefObject<HTMLElement>}
      className="graph-detail"
      style={width ? { width } : undefined}
    >
      {onResizeStart && (
        <div
          className="graph-detail-resizer"
          onMouseDown={onResizeStart}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize detail panel"
          title="Drag to resize"
        />
      )}
      <div className="graph-detail-header">
        <span className="graph-detail-type-icon">{TYPE_LABELS[node.type] || '◈'}</span>
        <div className="graph-detail-title-wrap">
          <span className="graph-detail-type-badge">{node.type}</span>
          <h3 className="graph-detail-title">{node.name}</h3>
        </div>
        <button className="graph-detail-close" onClick={onClose} aria-label={t('graph.panel.close')}>×</button>
      </div>

      {isFile && loadingFile && <p className="graph-detail-loading">{t('graph.panel.loading')}</p>}

      {isFile && fileDetail && (
        <div className="graph-detail-section">
          {fileDetail.category && (
            <div className="graph-detail-meta">
              <span className="graph-detail-category">{fileDetail.category}</span>
              {fileDetail.risk_level === 'review_first' && (
                <span className="graph-detail-risk">⚠</span>
              )}
            </div>
          )}
          {fileDetail.summary && (
            <>
              <h4 className="graph-detail-label">{t('graph.panel.summary')}<span className="graph-detail-label-desc">{t('graph.panel.summaryDesc')}</span></h4>
              <p className="graph-detail-summary">{fileDetail.summary}</p>
            </>
          )}
          {fileDetail.tags.length > 0 && (
            <>
              <h4 className="graph-detail-label">{t('graph.panel.tags')}<span className="graph-detail-label-desc">{t('graph.panel.tagsDesc')}</span></h4>
              <div className="graph-detail-tags">
                {fileDetail.tags.map((tag) => (
                  <button
                    key={tag}
                    className="graph-detail-tag"
                    onClick={() => onNavigate(`tag:${tag}`)}
                  >{tag}</button>
                ))}
              </div>
            </>
          )}
          {ENTITY_KEYS.some((k) => (fileDetail.entities[k]?.length ?? 0) > 0) && (
            <>
              <h4 className="graph-detail-label">{t('graph.panel.entities')}<span className="graph-detail-label-desc">{t('graph.panel.entitiesDesc')}</span></h4>
              <div className="graph-detail-entities">
                {ENTITY_KEYS.map((key) => {
                  const items = fileDetail.entities[key];
                  if (!items?.length) return null;
                  const nodeType = ENTITY_TYPE_MAP[key];
                  return items.map((name) => (
                    <button
                      key={`${key}-${name}`}
                      className="graph-detail-entity"
                      onClick={() => onNavigate(`${nodeType}:${name}`)}
                    >
                      <span className="graph-detail-entity-icon">{TYPE_LABELS[nodeType]}</span>
                      {name}
                    </button>
                  ));
                })}
              </div>
            </>
          )}
        </div>
      )}

      {!isFile && (
        <div className="graph-detail-section">
          {connectedFiles.length > 0 && (
            <>
              <h4 className="graph-detail-label">
                {t('graph.panel.connectedFiles')}
                <span className="graph-detail-count">{connectedFiles.length}</span>
                <span className="graph-detail-label-desc">{t('graph.panel.connectedFilesDesc')}</span>
              </h4>
              <ul className="graph-detail-file-list">
                {connectedFiles.map((f) => (
                  <li key={f.id}>
                    <button className="graph-detail-file-btn" onClick={() => onNavigate(f.id)}>
                      <span className="graph-detail-file-name">{f.name}</span>
                      {typeof f.summary === 'string' && f.summary && (
                        <span className="graph-detail-file-summary">{f.summary}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          {connectedEntities.length > 0 && (
            <>
              <h4 className="graph-detail-label">{t('graph.panel.relatedEntities')}<span className="graph-detail-label-desc">{t('graph.panel.relatedEntitiesDesc')}</span></h4>
              <div className="graph-detail-entities">
                {connectedEntities.map((e) => (
                  <button
                    key={e.id}
                    className="graph-detail-entity"
                    onClick={() => onNavigate(e.id)}
                  >
                    <span className="graph-detail-entity-icon">{TYPE_LABELS[e.type] || '◈'}</span>
                    {e.name}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {loadingInsights && <p className="graph-detail-loading">{t('graph.panel.loading')}</p>}

      {insights && !loadingInsights && (
        <div className="graph-detail-section graph-detail-insights">
          {insights.bridge_score != null && insights.bridge_score > 0 && (
            <div className="graph-detail-bridge">
              <span className="graph-detail-bridge-badge">🔗 {t('graph.panel.bridgeNode')}</span>
              <p className="graph-detail-bridge-desc">{t('graph.panel.bridgeDesc')}</p>
            </div>
          )}

          {insights.co_occurrences && insights.co_occurrences.length > 0 && (
            <>
              <h4 className="graph-detail-label">{t('graph.panel.coOccurrence')}<span className="graph-detail-label-desc">{t('graph.panel.coOccurrenceDesc')}</span></h4>
              <div className="graph-detail-entities">
                {insights.co_occurrences.map((co) => (
                  <button
                    key={co.entity_id}
                    className="graph-detail-entity"
                    onClick={() => onNavigate(co.entity_id)}
                  >
                    <span className="graph-detail-entity-icon">{TYPE_LABELS[co.entity_type] || '◈'}</span>
                    {co.entity_name}
                    <span className="graph-detail-co-count">
                      {t('graph.panel.filesCount', { count: co.shared_count })}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          {insights.timeline && insights.timeline.length > 0 && (
            <>
              <h4 className="graph-detail-label">{t('graph.panel.timeline')}<span className="graph-detail-label-desc">{t('graph.panel.timelineDesc')}</span></h4>
              <ul className="graph-detail-timeline">
                {insights.timeline.map((entry, i) => (
                  <li key={i} className="graph-detail-timeline-item">
                    <span className="graph-detail-timeline-date">
                      {entry.date ? new Date(entry.date).toLocaleDateString() : '—'}
                    </span>
                    <button
                      className="graph-detail-timeline-file"
                      onClick={() => onNavigate(entry.file_id)}
                    >
                      {entry.file_name}
                    </button>
                    {entry.summary && (
                      <span className="graph-detail-timeline-summary">{entry.summary}</span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}

          {insights.related_files && insights.related_files.length > 0 && (
            <>
              <h4 className="graph-detail-label">{t('graph.panel.relatedFiles')}<span className="graph-detail-label-desc">{t('graph.panel.relatedFilesDesc')}</span></h4>
              <ul className="graph-detail-file-list">
                {insights.related_files.map((rf) => (
                  <li key={rf.file_id}>
                    <button className="graph-detail-file-btn" onClick={() => onNavigate(rf.file_id)}>
                      <span className="graph-detail-file-name">{rf.file_name}</span>
                      <span className="graph-detail-file-shared">
                        {rf.shared_entities.join(', ')}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
