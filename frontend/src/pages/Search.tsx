import { useRef, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Markdown from 'react-markdown';
import { useSearch } from '../SearchContext';

const SUGGESTION_KEYS = ['chat.suggestion1', 'chat.suggestion2', 'chat.suggestion3'];

const SESSIONS_OPEN_KEY = 'gemvis.chat.sessionsOpen';
const readSessionsOpen = (): boolean => {
  try {
    const v = window.localStorage.getItem(SESSIONS_OPEN_KEY);
    if (v === '0') return false;
    if (v === '1') return true;
  } catch { /* ignore */ }
  return true; // default open on first visit
};

function formatTimestamp(ts: number): string {
  const now = Date.now();
  const diff = now - ts;
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export default function Search() {
  const { t } = useTranslation();
  const {
    messages, debugLog, input, setInput, loading, send, reset,
    sessions, activeSessionId, newSession, selectSession, deleteSession, renameSession,
  } = useSearch();
  const [debugOpen, setDebugOpen] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState<boolean>(readSessionsOpen);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SESSIONS_OPEN_KEY, sessionsOpen ? '1' : '0');
    } catch { /* ignore */ }
  }, [sessionsOpen]);

  const latestDebug = debugLog[debugLog.length - 1] ?? null;

  // Sort sessions by recency (descending updatedAt). Empty new chats stay at top.
  const orderedSessions = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);

  const startRename = (id: string, currentTitle: string) => {
    setEditingId(id);
    setEditingTitle(currentTitle);
  };
  const commitRename = () => {
    if (editingId) renameSession(editingId, editingTitle);
    setEditingId(null);
    setEditingTitle('');
  };

  return (
    <div className={`search-layout${debugOpen ? ' debug-open' : ''}${sessionsOpen ? ' sessions-open' : ''}`}>
      {/* Sessions drawer — left side */}
      <aside className="chat-sessions" aria-label={t('chat.sessions.label', { defaultValue: 'Conversations' })}>
        <div className="chat-sessions-head">
          <button
            className="btn chat-sessions-new"
            onClick={newSession}
            title={t('chat.sessions.new', { defaultValue: 'New chat' })}
            aria-label={t('chat.sessions.new', { defaultValue: 'New chat' })}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 5v14" />
              <path d="M5 12h14" />
            </svg>
            <span className="chat-sessions-new-label">{t('chat.sessions.new', { defaultValue: 'New chat' })}</span>
          </button>
          <button
            type="button"
            className="btn chat-sessions-toggle"
            onClick={() => setSessionsOpen((v) => !v)}
            aria-pressed={sessionsOpen}
            aria-label={t(sessionsOpen ? 'chat.sessions.hide' : 'chat.sessions.show', {
              defaultValue: sessionsOpen ? 'Hide conversations' : 'Show conversations',
            })}
            title={t(sessionsOpen ? 'chat.sessions.hide' : 'chat.sessions.show', {
              defaultValue: sessionsOpen ? 'Hide conversations' : 'Show conversations',
            })}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path d="M9 3v18" />
              {sessionsOpen ? (
                <path d="m16 15-3-3 3-3" />
              ) : (
                <path d="m14 9 3 3-3 3" />
              )}
            </svg>
          </button>
        </div>

        <div className="chat-sessions-list">
          {orderedSessions.map((s) => {
            const isActive = s.id === activeSessionId;
            const isEditing = editingId === s.id;
            const preview = s.messages.length > 0
              ? `${s.messages.length} ${t('chat.sessions.messages', { defaultValue: 'messages' })}`
              : t('chat.sessions.empty', { defaultValue: 'Empty' });
            return (
              <div
                key={s.id}
                className={`chat-session-item${isActive ? ' active' : ''}`}
                onClick={() => !isEditing && selectSession(s.id)}
                role="button"
                tabIndex={0}
              >
                <div className="chat-session-main">
                  {isEditing ? (
                    <input
                      autoFocus
                      className="chat-session-rename-input"
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
                        if (e.key === 'Escape') { setEditingId(null); setEditingTitle(''); }
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <div
                      className="chat-session-title"
                      onDoubleClick={(e) => { e.stopPropagation(); startRename(s.id, s.title); }}
                      title={s.title}
                    >
                      {s.title}
                    </div>
                  )}
                  <div className="chat-session-meta">
                    <span className="chat-session-preview">{preview}</span>
                    <span className="chat-session-time">{formatTimestamp(s.updatedAt)}</span>
                  </div>
                </div>
                <div className="chat-session-actions">
                  <button
                    type="button"
                    className="chat-session-action"
                    onClick={(e) => { e.stopPropagation(); startRename(s.id, s.title); }}
                    title={t('chat.sessions.rename', { defaultValue: 'Rename' })}
                    aria-label={t('chat.sessions.rename', { defaultValue: 'Rename' })}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M12 20h9" />
                      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    className="chat-session-action chat-session-action-danger"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(t('chat.sessions.deleteConfirm', { defaultValue: 'Delete this conversation?' }))) {
                        deleteSession(s.id);
                      }
                    }}
                    title={t('chat.sessions.delete', { defaultValue: 'Delete' })}
                    aria-label={t('chat.sessions.delete', { defaultValue: 'Delete' })}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6 18 20a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                      <path d="M10 11v6" />
                      <path d="M14 11v6" />
                    </svg>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </aside>

      <div className="chat-page">
        {/* Floating action group — inside chat-page so it shrinks/shifts with
            the content area when the L/R drawers open. */}
        <div className="chat-floating-actions">
          {messages.length > 0 && (
            <button
              className="btn btn-ghost"
              onClick={reset}
              title={t('chat.resetTitle')}
            >
              {t('chat.reset')}
            </button>
          )}
        </div>
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-glow" aria-hidden="true">✦</div>
              <h2 className="chat-empty-title">{t('chat.title')}</h2>
              <p className="chat-empty-hint">{t('chat.emptyHint')}</p>
              <div className="suggestions">
                {SUGGESTION_KEYS.map((key) => {
                  const text = t(key);
                  return (
                    <button key={key} className="suggestion-chip" onClick={() => send(text)}>
                      {text}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {messages.map((m, i) => {
            const isStreamingPlaceholder = m.role === 'assistant' && !m.content && loading && i === messages.length - 1;
            return (
              <div key={i} className={`chat-bubble ${m.role}`}>
                <div className={`chat-content${isStreamingPlaceholder ? ' typing' : ''}`}>
                  {isStreamingPlaceholder
                    ? t('chat.generating')
                    : m.role === 'assistant'
                    ? <Markdown>{m.content}</Markdown>
                    : m.content}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>

        <form
          className="chat-input"
          onSubmit={(e) => { e.preventDefault(); send(input); }}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('chat.inputPlaceholder')}
            disabled={loading}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !input.trim()}
            aria-label={t('chat.send')}
            title={t('chat.send')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="m5 12 7-7 7 7" />
              <path d="M12 19V5" />
            </svg>
          </button>
        </form>
      </div>

      <aside className="debug-panel">
        <button
          className={`debug-tab-toggle${debugOpen ? ' active' : ''}`}
          onClick={() => setDebugOpen((v) => !v)}
          aria-expanded={debugOpen}
          title={debugOpen ? t('chat.hideDebug') : t('chat.showDebug')}
          aria-label={debugOpen ? t('chat.hideDebug') : t('chat.showDebug')}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M15 3v18" />
          </svg>
        </button>
        <h3>{t('chat.debugTitle')}</h3>
        {!latestDebug ? (
          <p className="debug-empty">{t('chat.debugEmpty')}</p>
        ) : (
          <>
            <div className="debug-section">
              <h4>{t('chat.intentAnalysis')}</h4>
              <div className="debug-content">
                <div className="debug-row">
                  <span className="debug-label">mode</span>
                  <code>{latestDebug.intent_type}</code>
                </div>
              </div>
            </div>

            {latestDebug.intent_type === 'file_search' && (
              <div className="debug-section">
                <h4>{t('chat.graphResults', { count: latestDebug.files.length })}</h4>
                <div className="debug-results">
                  {latestDebug.files.length === 0 ? (
                    <p className="debug-muted">{t('chat.noResults')}</p>
                  ) : latestDebug.files.map((f, i) => (
                    <div key={i} className="debug-result-item">
                      {f.category && <span className="debug-type">{f.category}</span>}
                      <span className="debug-name">{f.file_name}</span>
                      {f.summary && <span className="debug-muted" style={{ fontSize: '0.75em', display: 'block', marginTop: '2px' }}>{f.summary}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {latestDebug.web && latestDebug.web.length > 0 && (
              <div className="debug-section">
                <h4>{t('chat.webResults', { count: latestDebug.web.length })}</h4>
                <div className="debug-results">
                  {latestDebug.web.map((w, i) => (
                    <a
                      key={i}
                      href={w.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="debug-result-item debug-web-item"
                      title={w.url}
                    >
                      <span className="debug-type">🌐</span>
                      <span className="debug-name">{w.title}</span>
                      {w.snippet && (
                        <span className="debug-muted" style={{ fontSize: '0.75em', display: 'block', marginTop: '2px' }}>
                          {w.snippet}
                        </span>
                      )}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
