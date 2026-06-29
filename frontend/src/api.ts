import i18n from './i18n';
import type {
  GraphData, WatcherStatus, ApiMessage, SearchResponse,
  ScheduleResponse, WorkScheduleMap,
  SummaryListResponse, DaySummaryResponse, DailySummary, SummaryPeriod,
  ScanProgress,
  FileListResponse, FileRecord, AnalysisStatus,
  ChatResponse, SSEEvent, SearchFileContext,
  Task, TaskListResponse, TaskEvaluateResponse, TaskProgressResponse,
  NodeInsights, BrowseDirsResponse,
} from './types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const lang = i18n.resolvedLanguage || i18n.language || 'ko';
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Accept-Language': lang,
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  graphData: () => request<GraphData>('/graph/data'),
  nodeInsights: (nodeId: string) =>
    request<NodeInsights>(`/graph/insights/${encodeURIComponent(nodeId)}`),
  search: (question: string, prevContext?: Record<string, unknown>) => request<SearchResponse>('/search', {
    method: 'POST',
    body: JSON.stringify({ question, prev_context: prevContext ?? null }),
  }),
  chat: (messages: Array<{ role: string; content: string }>) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ messages }),
    }),
  async *chatStream(
    messages: Array<{ role: string; content: string }>,
    searchContext?: SearchFileContext | null,
  ): AsyncGenerator<SSEEvent> {
    const lang = i18n.resolvedLanguage || i18n.language || 'ko';
    const res = await fetch(`${BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept-Language': lang },
      body: JSON.stringify({ messages, search_context: searchContext ?? null }),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    if (!res.body) throw new Error('No response body');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') return;
          try { yield JSON.parse(data) as SSEEvent; } catch { /* skip malformed */ }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
  watcherStart: () => request<ApiMessage>('/watcher/start', { method: 'POST' }),
  watcherStop: () => request<ApiMessage>('/watcher/stop', { method: 'POST' }),
  watcherStatus: () => request<WatcherStatus>('/watcher/status'),
  watcherScan: (mode: 'all' | 'documents' | 'images' | 'skeleton' = 'all') =>
    request<ApiMessage>(`/watcher/scan?mode=${mode}`, { method: 'POST' }),
  /** @deprecated Use watcherScan('images'). Kept so older code still compiles. */
  watcherScanImages: () => request<ApiMessage>('/watcher/scan?mode=images', { method: 'POST' }),
  scanProgress: () => request<ScanProgress>('/watcher/progress'),
  scanPause: () => request<ApiMessage>('/watcher/scan/pause', { method: 'POST' }),
  scanResume: () => request<ApiMessage>('/watcher/scan/resume', { method: 'POST' }),
  scanAckNoop: () => request<ApiMessage>('/watcher/scan/ack-noop', { method: 'POST' }),
  saveConfig: (api_key?: string, watch_dirs?: string[]) =>
    request<ApiMessage>('/config', {
      method: 'POST',
      body: JSON.stringify({ api_key, watch_dirs }),
    }),
  getPreferences: () =>
    request<{
      analyze_lang: string;
      analyze_images: boolean;
      web_search_enabled: boolean;
      llm_temperature: number;
      llm_max_tokens: number;
      llm_top_p: number;
      llm_top_k: number;
    }>('/preferences'),
  updatePreferences: (prefs: {
    analyze_lang?: string;
    analyze_images?: boolean;
    web_search_enabled?: boolean;
    llm_temperature?: number;
    llm_max_tokens?: number;
    llm_top_p?: number;
    llm_top_k?: number;
  }) =>
    request<{
      analyze_lang: string;
      analyze_images: boolean;
      web_search_enabled: boolean;
      llm_temperature: number;
      llm_max_tokens: number;
      llm_top_p: number;
      llm_top_k: number;
    }>('/preferences', {
      method: 'POST',
      body: JSON.stringify(prefs),
    }),
  browseDirs: (path?: string) => {
    const qs = new URLSearchParams();
    if (path) qs.set('path', path);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<BrowseDirsResponse>(`/dirs/browse${suffix}`);
  },
  clearGraph: () => request<ApiMessage>('/graph', { method: 'DELETE' }),
  openFolder: (path: string) => request<{ status: string; opened: string }>('/file/open-folder', {
    method: 'POST',
    body: JSON.stringify({ path }),
  }),
  getSchedule: () => request<ScheduleResponse>('/schedule'),
  saveSchedule: (schedule: WorkScheduleMap) =>
    request<ScheduleResponse & { status: string }>('/schedule', {
      method: 'POST',
      body: JSON.stringify({ schedule }),
    }),
  listSummaries: (from?: string, to?: string) => {
    const qs = new URLSearchParams();
    if (from) qs.set('date_from', from);
    if (to) qs.set('date_to', to);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<SummaryListResponse>(`/summary${suffix}`);
  },
  getDaySummary: (date: string) =>
    request<DaySummaryResponse>(`/summary/${date}`),
  generateSummary: (date: string, period: SummaryPeriod) =>
    request<DailySummary>(`/summary/${date}/${period}`, { method: 'POST' }),
  deleteSummary: (date: string, period: SummaryPeriod) =>
    request<{ status: string }>(`/summary/${date}/${period}`, { method: 'DELETE' }),

  // ── v2 Unified file endpoints (geminsight-develop) ─────────────
  files: (params?: {
    page?: number;
    limit?: number;
    sort_by?: string;
    order?: string;
    status?: AnalysisStatus;
    category?: string;
    include_stats?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', params.page.toString());
    if (params?.limit) qs.set('limit', params.limit.toString());
    if (params?.sort_by) qs.set('sort_by', params.sort_by);
    if (params?.order) qs.set('order', params.order);
    if (params?.status) qs.set('status', params.status);
    if (params?.category) qs.set('category', params.category);
    if (params?.include_stats) qs.set('include_stats', 'true');
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<FileListResponse>(`/files${suffix}`);
  },
  file: (fileId: string) =>
    request<FileRecord>(`/file/${encodeURIComponent(fileId)}`),
  regenerateFile: (fileId: string) =>
    request<FileRecord>(`/file/${encodeURIComponent(fileId)}/regenerate`, { method: 'POST' }),
  retryFailedFiles: () =>
    request<{ status: string; count: number }>('/files/retry-failed', { method: 'POST' }),

  // ── Tasks (calendar to-do) ────────────────────────────────────
  tasks: {
    list: (date: string) =>
      request<TaskListResponse>(`/tasks?date=${encodeURIComponent(date)}`),
    add: (text: string, date: string) =>
      request<Task>('/tasks', {
        method: 'POST',
        body: JSON.stringify({ text, date }),
      }),
    update: (id: string, body: { completed?: boolean; text?: string }) =>
      request<Task>(`/tasks/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    delete: (id: string) =>
      request<{ status: string }>(`/tasks/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      }),
    evaluate: (date: string) =>
      request<TaskEvaluateResponse>(
        `/tasks/evaluate?date=${encodeURIComponent(date)}`,
        { method: 'POST' },
      ),
    progress: (from?: string, to?: string) => {
      const qs = new URLSearchParams();
      if (from) qs.set('date_from', from);
      if (to) qs.set('date_to', to);
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      return request<TaskProgressResponse>(`/tasks/progress${suffix}`);
    },
  },
};
