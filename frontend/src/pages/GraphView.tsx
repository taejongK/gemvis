import { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ForceGraph2D from 'react-force-graph-2d';
import { api } from '../api';
import type { GraphData, GraphNode } from '../types';
import NodeDetailPanel from './NodeDetailPanel';
import ScanMonitor from '../ScanMonitor';
import { useGraphTheme } from '../theme/useGraphTheme';
import { GRAPH_THEME_IDS, GRAPH_THEMES, CATEGORY_KEYS } from '../theme/graphThemes';
import type { GraphTheme, GraphNodeVisual } from '../theme/graphThemes';

/**
 * Pick the visual for a node. File nodes are colored by their GemInsight
 * `category` (memo/photo/document/...) so the user can tell file kinds
 * apart at a glance. Non-file types or pending files fall back to the
 * base type color.
 */
const pickNodeVisual = (
  node: { type?: string; category?: unknown },
  theme: GraphTheme,
): GraphNodeVisual => {
  if (node.type === 'file') {
    const cat = typeof node.category === 'string' ? node.category : '';
    const byCat = cat ? theme.fileCategories[cat] : undefined;
    if (byCat) return byCat;
  }
  return theme.nodeTypes[String(node.type)] || DEFAULT_NODE;
};

const DEFAULT_NODE = { color: '#999999', glow: 'rgba(153, 153, 153, 0.45)' };

// roundRect polyfill for older WebView (WebView2 <94 etc.)
const drawRoundRect = (
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) => {
  const radius = Math.min(r, w / 2, h / 2);
  if (typeof (ctx as any).roundRect === 'function') {
    ctx.beginPath();
    (ctx as any).roundRect(x, y, w, h, radius);
    return;
  }
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
};

// localStorage keys for graph view UI state
const LINK_DISTANCE_KEY = 'gemvis.graph.linkDistance';
const HIGHLIGHT_TYPES_KEY = 'gemvis.graph.highlightTypes';
const DEGREE_WEIGHT_KEY = 'gemvis.graph.degreeWeight';
const HIDE_UNANALYZED_KEY = 'gemvis.graph.hideUnanalyzed';
const FILTER_W_KEY = 'gemvis.graph.filterWidth';
const DETAIL_W_KEY = 'gemvis.graph.detailWidth';
const DEFAULT_LINK_DISTANCE = 60;
const MIN_LINK_DISTANCE = 20;
const MAX_LINK_DISTANCE = 200;
// Degree weight: 0 = no size differentiation, 1 = subtle, 3 = aggressive.
const DEFAULT_DEGREE_WEIGHT = 1.4;
const MIN_DEGREE_WEIGHT = 0;
const MAX_DEGREE_WEIGHT = 3;
const FILTER_W_DEFAULT = 260;
const FILTER_W_MIN = 220;
const FILTER_W_MAX = 480;
const DETAIL_W_DEFAULT = 460;
const DETAIL_W_MIN = 320;
const DETAIL_W_MAX = 720;

let cachedGraphData: GraphData | null = null;

const readStoredWidth = (key: string, def: number, min: number, max: number): number => {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw) {
      const n = Number(raw);
      if (Number.isFinite(n) && n >= min && n <= max) return n;
    }
  } catch { /* ignore */ }
  return def;
};

const readLinkDistance = (): number => {
  try {
    const raw = window.localStorage.getItem(LINK_DISTANCE_KEY);
    if (raw) {
      const n = Number(raw);
      if (Number.isFinite(n) && n >= MIN_LINK_DISTANCE && n <= MAX_LINK_DISTANCE) return n;
    }
  } catch { /* ignore */ }
  return DEFAULT_LINK_DISTANCE;
};

const readDegreeWeight = (): number => {
  try {
    const raw = window.localStorage.getItem(DEGREE_WEIGHT_KEY);
    if (raw) {
      const n = Number(raw);
      if (Number.isFinite(n) && n >= MIN_DEGREE_WEIGHT && n <= MAX_DEGREE_WEIGHT) return n;
    }
  } catch { /* ignore */ }
  return DEFAULT_DEGREE_WEIGHT;
};

const readHideUnanalyzed = (): boolean => {
  try {
    return window.localStorage.getItem(HIDE_UNANALYZED_KEY) === 'true';
  } catch {
    return false;
  }
};

const readHighlightTypes = (): Set<string> => {
  try {
    const raw = window.localStorage.getItem(HIGHLIGHT_TYPES_KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) return new Set(arr.filter((x) => typeof x === 'string'));
    }
  } catch { /* ignore */ }
  return new Set();
};

export default function GraphView() {
  const { t } = useTranslation();
  const { theme, themeId, cycleTheme } = useGraphTheme();
  const [data, setData] = useState<GraphData | null>(() => cachedGraphData);
  const [loading, setLoading] = useState(() => cachedGraphData === null);
  const [loadError, setLoadError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [dims, setDims] = useState({ w: 800, h: 600 });
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const focusId = searchParams.get('focus');
  const focusFrom = searchParams.get('from');
  const focusDate = searchParams.get('date');
  const focusAppliedRef = useRef<string | null>(null);
  const engineStoppedRef = useRef(false);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  // Type-based highlight: empty Set = nothing pinned, all visible normally.
  // Non-empty = those types are emphasized, others dimmed (Obsidian filter feel).
  const [highlightTypes, setHighlightTypes] = useState<Set<string>>(readHighlightTypes);
  const [linkDistance, setLinkDistance] = useState<number>(readLinkDistance);
  const [degreeWeight, setDegreeWeight] = useState<number>(readDegreeWeight);
  const [hideUnanalyzed, setHideUnanalyzed] = useState<boolean>(readHideUnanalyzed);
  const [filterWidth, setFilterWidth] = useState<number>(() =>
    readStoredWidth(FILTER_W_KEY, FILTER_W_DEFAULT, FILTER_W_MIN, FILTER_W_MAX),
  );
  const [detailWidth, setDetailWidth] = useState<number>(() =>
    readStoredWidth(DETAIL_W_KEY, DETAIL_W_DEFAULT, DETAIL_W_MIN, DETAIL_W_MAX),
  );
  const filterRef = useRef<HTMLElement>(null);
  const detailRef = useRef<HTMLElement>(null);

  const startResize = (
    el: HTMLElement | null,
    startVal: number,
    direction: 'right' | 'left' | 'up' | 'down',
    min: number,
    max: number,
    storageKey: string,
    commit: (n: number) => void,
  ) => (e: React.MouseEvent) => {
    e.preventDefault();
    const axis: 'x' | 'y' = direction === 'right' || direction === 'left' ? 'x' : 'y';
    const cssProp: 'width' | 'height' = axis === 'x' ? 'width' : 'height';
    const startCoord = axis === 'x' ? e.clientX : e.clientY;
    let latest = startVal;
    let frame = 0;
    el?.classList.add('resizing');
    const apply = () => {
      frame = 0;
      if (el) el.style[cssProp] = `${latest}px`;
    };
    const onMove = (ev: MouseEvent) => {
      const cur = axis === 'x' ? ev.clientX : ev.clientY;
      const raw = cur - startCoord;
      // 'right'/'down': grow when coord increases. 'left'/'up': grow when coord decreases.
      const delta = direction === 'right' || direction === 'down' ? raw : -raw;
      latest = Math.min(max, Math.max(min, startVal + delta));
      if (!frame) frame = requestAnimationFrame(apply);
    };
    const onUp = () => {
      if (frame) cancelAnimationFrame(frame);
      el?.classList.remove('resizing');
      commit(latest);
      try { window.localStorage.setItem(storageKey, String(latest)); } catch { /* ignore */ }
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    document.body.style.cursor = axis === 'x' ? 'col-resize' : 'row-resize';
  };

  const load = useCallback(() => {
    setLoading(true);
    setLoadError(false);
    focusAppliedRef.current = null;
    engineStoppedRef.current = false;
    api.graphData()
      .then((next) => {
        cachedGraphData = next;
        setData(next);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) setDims({ w: r.width, h: r.height });
    };
    update();
    const obs = new ResizeObserver(update);
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Adjacency map: node id → connected node ids. Used for hover-neighbor halo.
  const adjacency = useMemo(() => {
    const m = new Map<string, Set<string>>();
    if (!data) return m;
    data.edges.forEach((e) => {
      const s = typeof e.source === 'string' ? e.source : (e.source as any).id;
      const t = typeof e.target === 'string' ? e.target : (e.target as any).id;
      if (!m.has(s)) m.set(s, new Set());
      if (!m.has(t)) m.set(t, new Set());
      m.get(s)!.add(t);
      m.get(t)!.add(s);
    });
    return m;
  }, [data]);

  // Per-node degree (number of unique neighbors). Drives node radius so that
  // well-connected hubs feel weightier — like Obsidian's "important note" dots.
  const degree = useMemo(() => {
    const m = new Map<string, number>();
    adjacency.forEach((neighbors, id) => m.set(id, neighbors.size));
    return m;
  }, [adjacency]);

  // Min / max degree used to normalize the radius scale.
  const degreeRange = useMemo(() => {
    let min = Infinity;
    let max = 0;
    degree.forEach((d) => {
      if (d < min) min = d;
      if (d > max) max = d;
    });
    if (!Number.isFinite(min)) min = 0;
    return { min, max };
  }, [degree]);

  const radiusForDegree = useCallback((d: number, base: number): number => {
    const { max } = degreeRange;
    if (degreeWeight <= 0 || max <= 1) return base;
    const norm = Math.log(1 + d) / Math.log(1 + max);
    return base * (1 + norm * degreeWeight);
  }, [degreeRange, degreeWeight]);

  // Focus mode (from ?focus=<id>): highlight node + neighbors via query param.
  const { highlightedNodes, highlightedLinks } = useMemo(() => {
    if (!focusId || !data) return { highlightedNodes: new Set<string>(), highlightedLinks: new Set<string>() };
    const nodes = new Set<string>([focusId]);
    const links = new Set<string>();
    data.edges.forEach((e) => {
      const src = typeof e.source === 'string' ? e.source : (e.source as any).id;
      const tgt = typeof e.target === 'string' ? e.target : (e.target as any).id;
      if (src === focusId || tgt === focusId) {
        nodes.add(src);
        nodes.add(tgt);
        links.add(`${src}->${tgt}`);
      }
    });
    return { highlightedNodes: nodes, highlightedLinks: links };
  }, [focusId, data]);

  // Hover neighborhood (1-hop set). null when nothing is hovered.
  const hoverSet = useMemo(() => {
    if (!hoveredNode) return null;
    const s = new Set<string>([hoveredNode]);
    const nb = adjacency.get(hoveredNode);
    if (nb) nb.forEach((n) => s.add(n));
    return s;
  }, [hoveredNode, adjacency]);

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    if (!hideUnanalyzed) {
      return {
        nodes: data.nodes.map((n) => ({ ...n })),
        links: data.edges.map((e) => ({ ...e })),
      };
    }
    // Step 1: drop file nodes that haven't finished analysis.
    const fileFilteredIds = new Set<string>();
    for (const n of data.nodes) {
      if (n.type !== 'file' || (n as { analysis_status?: string }).analysis_status === 'completed') {
        fileFilteredIds.add(n.id);
      }
    }
    // Step 2: drop edges incident to removed file nodes.
    const survivingEdges = data.edges.filter((e) => {
      const s = typeof e.source === 'string' ? e.source : (e.source as { id: string }).id;
      const t = typeof e.target === 'string' ? e.target : (e.target as { id: string }).id;
      return fileFilteredIds.has(s) && fileFilteredIds.has(t);
    });
    // Step 3: drop entity nodes that have no edges left (would float as
    // isolated dots — exactly what the user wanted to remove).
    const degree = new Map<string, number>();
    for (const e of survivingEdges) {
      const s = typeof e.source === 'string' ? e.source : (e.source as { id: string }).id;
      const t = typeof e.target === 'string' ? e.target : (e.target as { id: string }).id;
      degree.set(s, (degree.get(s) ?? 0) + 1);
      degree.set(t, (degree.get(t) ?? 0) + 1);
    }
    const nodes = data.nodes
      .filter((n) => {
        if (!fileFilteredIds.has(n.id)) return false;
        if (n.type === 'file') return true;
        return (degree.get(n.id) ?? 0) > 0;
      })
      .map((n) => ({ ...n }));
    const links = survivingEdges.map((e) => ({ ...e }));
    return { nodes, links };
  }, [data, hideUnanalyzed]);

  useEffect(() => {
    focusAppliedRef.current = null;
  }, [focusId]);

  const applyFocus = useCallback(() => {
    if (!focusId || !fgRef.current) return;
    if (focusAppliedRef.current === focusId) return;
    const node: any = graphData.nodes.find((n: any) => n.id === focusId);
    if (!node) return;
    if (typeof node.x !== 'number' || typeof node.y !== 'number') return;
    const targetZoom = 3;
    // When the detail panel is visible (top-right overlay, ~380px wide + 16px
    // gutter), shift the camera target right by half the panel area so the
    // node lands at the center of the visible (non-panel) region instead of
    // the raw canvas center.
    const panelArea = 460 + 32; // panel width + horizontal margins
    const xOffset = selectedNode ? panelArea / 2 / targetZoom : 0;
    fgRef.current.centerAt(node.x + xOffset, node.y, 800);
    fgRef.current.zoom(targetZoom, 800);
    focusAppliedRef.current = focusId;
  }, [focusId, graphData, selectedNode]);

  useEffect(() => {
    if (!focusId || !data) return;
    if (!engineStoppedRef.current) return;
    const id = setTimeout(applyFocus, 300);
    return () => clearTimeout(id);
  }, [focusId, data, dims, applyFocus]);

  const clearFocus = () => {
    searchParams.delete('focus');
    setSearchParams(searchParams);
    setSelectedNode(null);
  };

  // Legend click: toggle that type into the highlight set. Empty set = no filter.
  const toggleType = useCallback((type: string, additive: boolean) => {
    setHighlightTypes((prev) => {
      const next = new Set(additive ? prev : []);
      if (prev.has(type) && !additive) {
        next.clear();
      } else if (prev.has(type) && additive) {
        next.delete(type);
      } else {
        next.add(type);
      }
      try {
        window.localStorage.setItem(HIGHLIGHT_TYPES_KEY, JSON.stringify(Array.from(next)));
      } catch { /* ignore */ }
      return next;
    });
  }, []);

  // Density slider — feeds d3-force link distance live.
  const onLinkDistanceChange = useCallback((value: number) => {
    setLinkDistance(value);
    try {
      window.localStorage.setItem(LINK_DISTANCE_KEY, String(value));
    } catch { /* ignore */ }
  }, []);

  const onDegreeWeightChange = useCallback((value: number) => {
    setDegreeWeight(value);
    try {
      window.localStorage.setItem(DEGREE_WEIGHT_KEY, String(value));
    } catch { /* ignore */ }
  }, []);

  const onHideUnanalyzedChange = useCallback((value: boolean) => {
    setHideUnanalyzed(value);
    try {
      window.localStorage.setItem(HIDE_UNANALYZED_KEY, String(value));
    } catch { /* ignore */ }
  }, []);

  // Apply linkDistance to the live d3-force simulation whenever it changes.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    const linkForce = fg.d3Force('link');
    if (linkForce && typeof linkForce.distance === 'function') {
      linkForce.distance(linkDistance);
      fg.d3ReheatSimulation();
    }
  }, [linkDistance, graphData]);

  const legendEntries = useMemo(
    () => Object.entries(theme.nodeTypes).map(([type, v]) => [type, v.color] as const),
    [theme],
  );

  // Categories that actually appear in the current graph — keeps the legend
  // honest (no swatches for empty categories) and stable in the UI.
  const presentCategories = useMemo(() => {
    if (!data) return [] as string[];
    const seen = new Set<string>();
    for (const n of data.nodes) {
      const cat = (n as { category?: unknown }).category;
      if (typeof cat === 'string' && cat) seen.add(cat);
    }
    // Preserve canonical order from CATEGORY_KEYS, drop unseen.
    return CATEGORY_KEYS.filter((k) => seen.has(k));
  }, [data]);

  const nextThemeLabel = useMemo(() => {
    const idx = GRAPH_THEME_IDS.indexOf(themeId);
    const next = GRAPH_THEME_IDS[(idx + 1) % GRAPH_THEME_IDS.length];
    return t(GRAPH_THEMES[next].labelKey);
  }, [themeId, t]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node as GraphNode);
    searchParams.set('focus', node.id);
    setSearchParams(searchParams);
  }, [searchParams, setSearchParams]);

  const handlePanelNavigate = useCallback((nodeId: string) => {
    const target = graphData.nodes.find((n: any) => n.id === nodeId);
    if (target) {
      setSelectedNode(target as GraphNode);
      searchParams.set('focus', nodeId);
      setSearchParams(searchParams);
    }
  }, [graphData, searchParams, setSearchParams]);

  const showInitialPanel = !data;

  return (
    <div className={`page graph-page ${theme.containerClass}${selectedNode ? ' has-detail' : ''}`}>
      <div className="graph-container" ref={containerRef}>
        {/* Floating focus banner — top-left, only when focused */}
        {focusId && (
          <div className="graph-focus-banner">
            {focusFrom === 'calendar' && (
              <button
                className="graph-focus-back"
                onClick={() =>
                  navigate(focusDate ? `/calendar?date=${encodeURIComponent(focusDate)}` : '/calendar')
                }
                title={t('graph.backToCalendar')}
              >
                {t('graph.backCalendarButton')}
              </button>
            )}
            {focusFrom === 'search' && (
              <button
                className="graph-focus-back"
                onClick={() => window.dispatchEvent(new Event('gemvis:open-spotlight'))}
                title={t('graph.backToSearch')}
              >
                {t('graph.backButton')}
              </button>
            )}
            <span className="graph-focus-banner-text">
              {t('graph.focusLabel')}: <code>{focusId}</code>
            </span>
            <span className="graph-focus-meta">
              {t('graph.highlighting', { count: highlightedNodes.size - 1 })}
            </span>
          </div>
        )}

        {/* Unified graph console — bottom-left.
            Apple-style liquid glass card grouping filter / display / view. */}
        <aside
          ref={filterRef}
          className="graph-console"
          style={{ width: filterWidth }}
          aria-label={t('graph.legendLabel', { defaultValue: 'Graph controls' })}
        >
          <div
            className="graph-console-resizer"
            onMouseDown={startResize(filterRef.current, filterWidth, 'right', FILTER_W_MIN, FILTER_W_MAX, FILTER_W_KEY, setFilterWidth)}
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize filter panel"
            title="Drag to resize"
          />
          <section className="graph-console-section">
            <header className="graph-console-section-head">
              <span>Filter</span>
              {highlightTypes.size > 0 && (
                <button
                  type="button"
                  className="graph-console-clear"
                  onClick={() => {
                    setHighlightTypes(new Set());
                    try { window.localStorage.removeItem(HIGHLIGHT_TYPES_KEY); } catch { /* ignore */ }
                  }}
                  title={t('graph.clearTypeFilter', { defaultValue: 'Clear filter' })}
                  aria-label={t('graph.clearTypeFilter', { defaultValue: 'Clear filter' })}
                >
                  ×
                </button>
              )}
            </header>
            {focusId && (
              <button
                type="button"
                className="graph-console-clear-focus"
                onClick={clearFocus}
                title={t('graph.clearHighlight')}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
                <span>{t('graph.clearHighlight')}</span>
              </button>
            )}
            <div className="graph-console-chips" role="group">
              {legendEntries.map(([type, color]) => {
                const active = highlightTypes.has(type);
                const muted = highlightTypes.size > 0 && !active;
                return (
                  <button
                    key={type}
                    type="button"
                    className={`graph-console-chip${active ? ' active' : ''}${muted ? ' muted' : ''}`}
                    onClick={(e) => toggleType(type, e.shiftKey || e.metaKey || e.ctrlKey)}
                    aria-pressed={active}
                    title={t('graph.legendToggleHint', { type, defaultValue: `Click to highlight ${type} (Shift/⌘ to add)` })}
                  >
                    <span className="graph-console-chip-dot" style={{ background: color }} />
                    <span>{type}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {presentCategories.length > 0 && (
            <section className="graph-console-section">
              <header className="graph-console-section-head">
                <span>{t('graph.fileCategories', { defaultValue: 'File categories' })}</span>
              </header>
              <div className="graph-console-legend" role="list">
                {presentCategories.map((cat) => {
                  const visual = theme.fileCategories[cat];
                  if (!visual) return null;
                  return (
                    <div key={cat} className="graph-console-legend-item" role="listitem">
                      <span
                        className="graph-console-chip-dot"
                        style={{ background: visual.color }}
                        aria-hidden="true"
                      />
                      <span>{t(`graph.category.${cat}`, { defaultValue: cat.replace('_', ' ') })}</span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          <section className="graph-console-section">
            <header className="graph-console-section-head">Display</header>
            <div className="graph-console-slider-row">
              <label htmlFor="graph-density-slider">{t('graph.density', { defaultValue: 'Density' })}</label>
              <input
                id="graph-density-slider"
                type="range"
                min={MIN_LINK_DISTANCE}
                max={MAX_LINK_DISTANCE}
                step={4}
                value={linkDistance}
                onChange={(e) => onLinkDistanceChange(Number(e.target.value))}
              />
            </div>
            <div className="graph-console-slider-row">
              <label htmlFor="graph-degree-slider">{t('graph.degreeWeight', { defaultValue: 'Hub size' })}</label>
              <input
                id="graph-degree-slider"
                type="range"
                min={MIN_DEGREE_WEIGHT}
                max={MAX_DEGREE_WEIGHT}
                step={0.1}
                value={degreeWeight}
                onChange={(e) => onDegreeWeightChange(Number(e.target.value))}
              />
            </div>
            <label className="graph-console-check" htmlFor="graph-hide-unanalyzed" title={t('graph.hideUnanalyzedHint')}>
              <input
                id="graph-hide-unanalyzed"
                type="checkbox"
                checked={hideUnanalyzed}
                onChange={(e) => onHideUnanalyzedChange(e.target.checked)}
              />
              <span>{t('graph.hideUnanalyzed')}</span>
            </label>
          </section>

          <section className="graph-console-section graph-console-actions">
            <button
              type="button"
              className="graph-console-action"
              onClick={cycleTheme}
              disabled={!!focusId}
              title={focusId ? t('graph.disabledWhileFocused') : t('graph.theme.toggleTitle')}
              aria-label={t('graph.theme.toggleAria', { name: nextThemeLabel })}
            >
              <span className="graph-console-action-icon" aria-hidden="true">◐</span>
              <span>{t(theme.labelKey)}</span>
            </button>
            <button
              type="button"
              className="graph-console-action graph-console-action-icon"
              onClick={load}
              disabled={!!focusId}
              title={focusId ? t('graph.disabledWhileFocused') : t('common.refresh')}
              aria-label={t('common.refresh')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 12a9 9 0 1 1-3-6.7" />
                <polyline points="21 4 21 12 13 12" />
              </svg>
            </button>
          </section>
        </aside>
        <div className="graph-activity-panel">
          <ScanMonitor />
        </div>
        {loading && data && (
          <div className="graph-refresh-status" role="status">
            <span className="graph-refresh-dot" aria-hidden="true" />
            <span>{t('graph.refreshing', { defaultValue: '그래프 동기화 중' })}</span>
          </div>
        )}
        {loadError && data && (
          <button type="button" className="graph-load-error" onClick={load}>
            {t('graph.loadFailed', { defaultValue: '그래프를 불러오지 못했습니다' })}
          </button>
        )}
        {showInitialPanel ? (
          <div className="graph-loading-panel" role="status" aria-live="polite">
            <span className="graph-loading-dot" aria-hidden="true" />
            <span className="graph-loading-title">
              {loadError
                ? t('graph.loadFailed', { defaultValue: '그래프를 불러오지 못했습니다' })
                : t('graph.syncing', { defaultValue: '그래프 동기화 중' })}
            </span>
            <span className="graph-loading-subtitle">
              {t('graph.syncingHint', { defaultValue: '현재 저장된 그래프를 준비하고 있습니다.' })}
            </span>
            {loadError && (
              <button type="button" className="graph-loading-action" onClick={load}>
                {t('common.refresh')}
              </button>
            )}
          </div>
        ) : data && data.nodes.length === 0 ? (
          <p className="empty-state">{t('graph.empty')}</p>
        ) : (
          <ForceGraph2D
            ref={fgRef}
            key={hideUnanalyzed ? 'hide-unanalyzed' : 'show-all'}
            graphData={graphData}
            width={dims.w}
            height={dims.h}
            backgroundColor="transparent"
            nodeRelSize={6}
            cooldownTicks={100}
            onEngineStop={() => {
              engineStoppedRef.current = true;
              focusAppliedRef.current = null;
              applyFocus();
            }}
            linkColor={(link: any) => {
              const src = typeof link.source === 'object' ? link.source.id : link.source;
              const tgt = typeof link.target === 'object' ? link.target.id : link.target;
              const srcType = (typeof link.source === 'object' ? link.source.type : undefined) as string | undefined;
              const tgtType = (typeof link.target === 'object' ? link.target.type : undefined) as string | undefined;
              if (highlightedLinks.has(`${src}->${tgt}`)) return theme.link.highlighted;
              if (hoveredNode && (src === hoveredNode || tgt === hoveredNode)) return theme.link.hovered;
              if (highlightTypes.size > 0) {
                const matches = (srcType && highlightTypes.has(srcType)) || (tgtType && highlightTypes.has(tgtType));
                return matches ? theme.link.hovered : theme.link.dimmed;
              }
              if (focusId || hoverSet) return theme.link.dimmed;
              return theme.link.idle;
            }}
            linkWidth={(link: any) => {
              const src = typeof link.source === 'object' ? link.source.id : link.source;
              const tgt = typeof link.target === 'object' ? link.target.id : link.target;
              if (highlightedLinks.has(`${src}->${tgt}`)) return 2;
              if (hoveredNode && (src === hoveredNode || tgt === hoveredNode)) return 1.6;
              return 0.8;
            }}
            linkDirectionalParticles={(link: any) => {
              const src = typeof link.source === 'object' ? link.source.id : link.source;
              const tgt = typeof link.target === 'object' ? link.target.id : link.target;
              return highlightedLinks.has(`${src}->${tgt}`) ? 2 : 0;
            }}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleColor={() => theme.link.highlightedParticle}
            enableNodeDrag
            enableZoomInteraction
            onNodeClick={handleNodeClick}
            onNodeHover={(node: any) => setHoveredNode(node ? node.id : null)}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const visual = pickNodeVisual(node, theme);
              const { color, glow } = visual;

              const isFocused = focusId === node.id;
              const isHighlighted = highlightedNodes.has(node.id);
              const isHovered = hoveredNode === node.id;
              const isNeighbor = hoverSet ? hoverSet.has(node.id) : false;
              const typeFilterActive = highlightTypes.size > 0;
              const matchesTypeFilter = typeFilterActive && highlightTypes.has(node.type as string);

              let emphasis: 'strong' | 'normal' | 'dim' | 'idle';
              if (focusId) {
                emphasis = isFocused ? 'strong' : isHighlighted ? 'normal' : 'dim';
              } else if (hoverSet) {
                emphasis = isHovered ? 'strong' : isNeighbor ? 'normal' : 'dim';
              } else if (typeFilterActive) {
                emphasis = matchesTypeFilter ? 'normal' : 'dim';
              } else {
                emphasis = 'idle';
              }

              const nodeAlpha = emphasis === 'dim' ? 0.18 : 1.0;
              ctx.globalAlpha = nodeAlpha;

              if (isFocused || isHovered) {
                ctx.beginPath();
                ctx.fillStyle = glow;
                const haloR = isFocused ? 13 : 10;
                ctx.arc(node.x, node.y, haloR, 0, Math.PI * 2);
                ctx.fill();
              }

              const baseRadius =
                isFocused ? 6.5 :
                isHovered ? 6 :
                isHighlighted || isNeighbor || matchesTypeFilter ? 5 :
                4.2;
              const r = radiusForDegree(degree.get(node.id) ?? 0, baseRadius);
              ctx.shadowColor = color;
              ctx.shadowBlur = (isFocused || isHovered) ? 14 / globalScale : emphasis === 'dim' ? 0 : 5 / globalScale;

              ctx.beginPath();
              ctx.fillStyle = color;
              ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
              ctx.fill();
              ctx.shadowBlur = 0;
              ctx.shadowColor = 'transparent';

              if (isFocused) {
                ctx.strokeStyle = theme.focusRing === 'accent' && theme.focusRingColor
                  ? theme.focusRingColor
                  : color;
                ctx.lineWidth = 2 / globalScale;
                ctx.beginPath();
                ctx.arc(node.x, node.y, r + 2, 0, Math.PI * 2);
                ctx.stroke();
              }

              const label = String(node.name || '');
              if (!label) {
                ctx.globalAlpha = 1;
                return;
              }

              const ZOOM_MIN_IDLE = 1.2;
              const ZOOM_FULL_IDLE = 2.4;
              const ZOOM_HIDE_DIM = 0.6;

              if (emphasis === 'dim' && globalScale < ZOOM_HIDE_DIM) {
                ctx.globalAlpha = 1;
                return;
              }
              if (emphasis === 'idle' && globalScale < ZOOM_MIN_IDLE * 0.6) {
                ctx.globalAlpha = 1;
                return;
              }

              const basePx = emphasis === 'strong' ? 13 : emphasis === 'normal' ? 11.5 : 10.5;
              const fontSize = Math.max(basePx / globalScale, 2.5);
              const weight = emphasis === 'strong' ? 600 : 500;
              ctx.font = `${weight} ${fontSize}px Inter, -apple-system, sans-serif`;

              let labelAlpha: number;
              if (emphasis === 'strong') {
                labelAlpha = 1;
              } else if (emphasis === 'normal') {
                labelAlpha = 0.85;
              } else if (emphasis === 'dim') {
                labelAlpha = 0.08;
              } else {
                const tNorm = Math.min(
                  1,
                  Math.max(0, (globalScale - ZOOM_MIN_IDLE * 0.6) / (ZOOM_FULL_IDLE - ZOOM_MIN_IDLE * 0.6)),
                );
                labelAlpha = 0.18 + tNorm * 0.42;
              }

              const textY = node.y + r + 2 + fontSize * 0.6;

              if (emphasis === 'strong') {
                const textWidth = ctx.measureText(label).width;
                const padX = fontSize * 0.5;
                const padY = fontSize * 0.3;
                const bgW = textWidth + padX * 2;
                const bgH = fontSize + padY * 2;
                const bgX = node.x - bgW / 2;
                const bgY = textY - bgH / 2;
                const radius = 3 / globalScale;

                ctx.globalAlpha = 0.92;
                ctx.fillStyle = theme.label.bg;
                drawRoundRect(ctx, bgX, bgY, bgW, bgH, radius);
                ctx.fill();

                ctx.globalAlpha = 0.5;
                ctx.strokeStyle = color;
                ctx.lineWidth = 0.8 / globalScale;
                ctx.stroke();

                ctx.globalAlpha = 1;
              }

              ctx.globalAlpha = labelAlpha;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = emphasis === 'strong' ? theme.label.textStrong : theme.label.text;
              ctx.fillText(label, node.x, textY);

              ctx.globalAlpha = 1;
            }}
          />
        )}
      </div>
      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          adjacency={adjacency}
          graphNodes={data?.nodes ?? []}
          onNavigate={handlePanelNavigate}
          onClose={() => { clearFocus(); setSelectedNode(null); }}
          width={detailWidth}
          asideRef={detailRef}
          onResizeStart={startResize(detailRef.current, detailWidth, 'left', DETAIL_W_MIN, DETAIL_W_MAX, DETAIL_W_KEY, setDetailWidth)}
        />
      )}
    </div>
  );
}
