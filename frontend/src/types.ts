export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  node_types: Record<string, number>;
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  sort_by: string;
  order: string;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  [key: string]: unknown;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface WatcherStatus {
  running: boolean;
  watch_dirs: string[];
  default_dirs: string[];
  processed_count: number;
  watched_files_total?: number;
}

export interface ApiMessage {
  status: string;
  message: string;
  message_key?: string;
  message_params?: Record<string, string | number>;
}

export interface ScanProgress {
  status: 'idle' | 'scanning' | 'paused' | 'done' | 'error';
  total: number;
  processed: number;
  current_file: string;
  error: string;
  elapsed_sec: number;
  avg_sec_per_file: number;
  eta_sec: number;
  /** Scan mode of the most recent run: 'all' | 'documents' | 'images' | 'skeleton' | '' */
  mode?: string;
  /** ISO datetime string when the most recent scan started; "" if never */
  started_at?: string;
  /** Set when the latest scan request had no work to do; cleared by ack endpoint. */
  last_no_op_mode?: string;
}

export interface SearchIntent {
  search_terms: string[];
  node_types: string[];
  intent: string;
}

export interface SearchResponse {
  answer: string;
  intent: SearchIntent | null;
  graph_results: Record<string, unknown>[];
  context?: Record<string, unknown>;
}

export type DayHours = { start: string; end: string } | null;

export interface WorkScheduleMap {
  monday: DayHours;
  tuesday: DayHours;
  wednesday: DayHours;
  thursday: DayHours;
  friday: DayHours;
  saturday: DayHours;
  sunday: DayHours;
}

export interface ScheduleResponse {
  schedule: WorkScheduleMap;
}

export type SummaryPeriod = 'work' | 'personal' | 'daily';

export interface DailySummary {
  date: string;            // YYYY-MM-DD
  period: SummaryPeriod;
  summary: string;
  work_hours: string;
  file_count: number;
  created_count: number;
  modified_count: number;
  deleted_count: number;
  generated_at: string;
  files?: { id: string; name: string }[];
}

export interface SummaryListResponse {
  summaries: DailySummary[];
}

export interface DaySummaryResponse {
  date: string;
  work: DailySummary | null;
  personal: DailySummary | null;
  daily: DailySummary | null;
}

// ── v2 Unified FileRecord (geminsight-develop) ───────────────────
//
// Mirror of gemvis/api.py::FileRecord Pydantic model. Every file in
// Gemvis has exactly one FileRecord, and every UI feature should read
// this shape via /api/files — never assemble from multiple endpoints.

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface FileRecord {
  // Identity
  file_id: string;        // absolute path (primary key)
  file_name: string;
  extension: string;

  // Physical
  size_bytes: number | null;
  file_mtime: string;     // ISO datetime
  file_ctime: string;     // ISO datetime
  added_at: string;       // ISO datetime

  // Analytical (null when analysis_status !== 'completed')
  category: string | null;
  summary: string | null;
  tags: string[];
  risk_level: string | null;
  entities: {
    people?: string[];
    places?: string[];
    projects?: string[];
    dates?: string[];
    events?: string[];
  };
  relations: Array<{
    source: string;
    source_type: string;
    target: string;
    target_type: string;
    relation: string;
  }>;

  // State machine
  analysis_status: AnalysisStatus;
  last_analyzed_at: string | null;
  error: string | null;
}

// ── Chat (general conversation + file search routing) ────────────

export interface ChatFile {
  file_id: string;
  file_name: string;
  category: string | null;
  summary: string | null;
}

export interface SearchFileContext {
  query: string;
  files: ChatFile[];
}

export interface ChatResponse {
  answer: string;
  files: ChatFile[];
  intent_type: 'general' | 'file_search';
}

export interface WebResult {
  title: string;
  snippet: string;
  url: string;
}

export type SSEEvent =
  | { type: 'meta'; intent_type: 'general' | 'file_search'; files: ChatFile[]; web?: WebResult[] }
  | { type: 'chunk'; text: string }
  | { type: 'error'; text: string }
  | { type: 'done' };

// ── Graph Insights (computed from graph topology) ───────────────
export interface CoOccurrence {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  shared_count: number;
}

export interface RelatedFile {
  file_id: string;
  file_name: string;
  shared_entities: string[];
  score: number;
}

export interface TimelineEntry {
  date: string;
  file_id: string;
  file_name: string;
  summary: string;
}

export interface NodeInsights {
  node_id: string;
  node_type: string;
  bridge_score?: number;
  co_occurrences?: CoOccurrence[];
  related_files?: RelatedFile[];
  timeline?: TimelineEntry[];
}

export interface FileListResponse {
  files: FileRecord[];
  pagination: Pagination;
  stats: GraphStats | null;
  // Whole-dataset status distribution — counts reflect `pagination.total`,
  // not the current page, so filter buttons/totals stay correct across pages.
  status_counts: Record<AnalysisStatus, number>;
}

// ── Tasks (calendar to-do) ───────────────────────────────────────
//
// Mirror of gemvis/api.py::TaskOut. User-defined to-do items pinned to a
// date. LLM auto-checks them against the day's file activity; manual user
// toggles lock the task from further auto-evaluation.

export interface Task {
  id: string;
  text: string;
  date: string;            // YYYY-MM-DD (current assignment, may have rolled over)
  original_date: string;   // YYYY-MM-DD (where it was first created)
  created_at: string;      // ISO datetime
  completed: boolean;
  completed_at: string | null;
  related_files: string[]; // absolute paths chosen by the LLM
  evidence: string | null;
  rollover_count: number;
  locked_by_user: boolean;
}

export interface TaskListResponse {
  date: string;
  tasks: Task[];
}

export interface TaskEvaluateResponse {
  date: string;
  updated: number;
  tasks: Task[];
  checked_count?: number;
  file_count?: number;
}

export interface TaskProgress {
  date: string;
  total: number;
  done: number;
}

export interface TaskProgressResponse {
  progress: TaskProgress[];
}

export interface BrowseDirsResponse {
  current: string;
  parent: string | null;
  dirs: string[];
  error: string | null;
}
