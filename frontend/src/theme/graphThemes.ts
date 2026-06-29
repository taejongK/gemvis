export type GraphThemeId = 'obsidian' | 'accent';

export interface GraphNodeVisual {
  color: string;
  glow: string;
}

export interface GraphTheme {
  id: GraphThemeId;
  labelKey: string;
  containerClass: string;
  nodeTypes: Record<string, GraphNodeVisual>;
  /**
   * File-node sub-palette keyed by GemInsight `category`. Falls back to
   * `nodeTypes.file` when a file has no category yet (e.g. pending).
   */
  fileCategories: Record<string, GraphNodeVisual>;
  link: {
    idle: string;
    dimmed: string;
    hovered: string;
    highlighted: string;
    highlightedParticle: string;
  };
  label: {
    bg: string;
    text: string;
    textStrong: string;
  };
  focusRing: 'type' | 'accent';
  focusRingColor?: string;
}

const withAlpha = (hex: string, alpha: number): string => {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const buildNodeTypes = (palette: Record<string, string>): Record<string, GraphNodeVisual> => {
  const out: Record<string, GraphNodeVisual> = {};
  for (const [k, v] of Object.entries(palette)) {
    out[k] = { color: v, glow: withAlpha(v, 0.45) };
  }
  return out;
};

const OBSIDIAN_PALETTE: Record<string, string> = {
  file: '#A78BFA',
  person: '#60A5FA',
  place: '#FBBF24',
  project: '#F472B6',
  event: '#34D399',
  date: '#818CF8',
  tag: '#2DD4BF',
};

const ACCENT_PALETTE: Record<string, string> = {
  file: '#79C99A',
  person: '#89A7FF',
  place: '#F0A369',
  project: '#C98AFF',
  event: '#F0798C',
  date: '#9AA6B0',
  tag: '#6FC8D3',
};

/**
 * Category sub-palettes for file nodes. Hues are inspired by Tableau 10
 * (d3-scale-chromatic `schemeTableau10`) so they stay perceptually distinct
 * without adding a runtime dependency.
 */
export const CATEGORY_KEYS = [
  'memo',
  'photo',
  'screenshot',
  'document',
  'voice_memo',
  'code',
  'data',
  'other',
] as const;
export type FileCategory = typeof CATEGORY_KEYS[number];

const OBSIDIAN_CATEGORIES: Record<FileCategory, string> = {
  memo:        '#FCD34D', // amber-300
  photo:       '#F472B6', // pink-400
  screenshot:  '#FB923C', // orange-400
  document:    '#A78BFA', // violet-400 (matches base file color)
  voice_memo:  '#22D3EE', // cyan-400
  code:        '#34D399', // emerald-400
  data:        '#60A5FA', // blue-400
  other:       '#94A3B8', // slate-400
};

const ACCENT_CATEGORIES: Record<FileCategory, string> = {
  memo:        '#F4C95D',
  photo:       '#F08AC0',
  screenshot:  '#F0A369',
  document:    '#79C99A',
  voice_memo:  '#6FC8D3',
  code:        '#89D4A7',
  data:        '#89A7FF',
  other:       '#9AA6B0',
};

export const GRAPH_THEMES: Record<GraphThemeId, GraphTheme> = {
  obsidian: {
    id: 'obsidian',
    labelKey: 'graph.theme.obsidian',
    containerClass: 'graph-theme-obsidian',
    nodeTypes: buildNodeTypes(OBSIDIAN_PALETTE),
    fileCategories: buildNodeTypes(OBSIDIAN_CATEGORIES),
    link: {
      idle: 'rgba(203, 213, 225, 0.18)',
      dimmed: 'rgba(148, 163, 184, 0.08)',
      hovered: 'rgba(226, 232, 240, 0.55)',
      highlighted: 'rgba(167, 139, 250, 0.85)',
      highlightedParticle: '#C4B5FD',
    },
    label: {
      bg: 'rgba(10, 14, 22, 0.88)',
      text: 'rgba(226, 232, 240, 0.92)',
      textStrong: '#FFFFFF',
    },
    focusRing: 'type',
  },
  accent: {
    id: 'accent',
    labelKey: 'graph.theme.accent',
    containerClass: 'graph-theme-accent',
    nodeTypes: buildNodeTypes(ACCENT_PALETTE),
    fileCategories: buildNodeTypes(ACCENT_CATEGORIES),
    link: {
      idle: 'rgba(156, 171, 255, 0.22)',
      dimmed: 'rgba(200, 203, 210, 0.08)',
      hovered: 'rgba(192, 152, 255, 0.5)',
      highlighted: 'rgba(192, 152, 255, 0.9)',
      highlightedParticle: '#C098FF',
    },
    label: {
      bg: 'rgba(22, 24, 29, 0.88)',
      text: 'rgba(245, 246, 248, 0.92)',
      textStrong: '#FFFFFF',
    },
    focusRing: 'accent',
    focusRingColor: '#C098FF',
  },
};

export const DEFAULT_GRAPH_THEME: GraphThemeId = 'obsidian';
export const GRAPH_THEME_IDS: GraphThemeId[] = ['obsidian', 'accent'];
