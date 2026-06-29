import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import { api } from './api';
import type { SearchResponse, ChatFile } from './types';
import { useSearch } from './SearchContext';

const TYPE_ICONS: Record<string, string> = {
  file: '📄',
  person: '👤',
  place: '📍',
  project: '🗂️',
  event: '📅',
  date: '🕐',
  tag: '🏷️',
};

interface SpotlightProps {
  open: boolean;
  onClose: () => void;
}

export default function Spotlight({ open, onClose }: SpotlightProps) {
  const { t } = useTranslation();
  const { sendFromSpotlight } = useSearch();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [searchedQuery, setSearchedQuery] = useState('');  // query that produced current response
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const itemRefs = useRef<(HTMLDivElement | null)[]>([]);
  const requestIdRef = useRef(0);
  const navigate = useNavigate();

  // When opened, focus input and select text so user can keep or replace
  useEffect(() => {
    if (open) {
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 50);
    }
  }, [open]);

  // Explicit search (triggered on Enter, not on every keystroke)
  const runSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;

    const currentRequest = ++requestIdRef.current;
    setLoading(true);
    setError(null);

    try {
      const result = await api.search(q);
      if (currentRequest === requestIdRef.current) {
        setResponse(result);
        setSearchedQuery(q);
        setSelectedIndex(0);
      }
    } catch (err) {
      if (currentRequest === requestIdRef.current) {
        setError(err instanceof Error ? err.message : t('spotlight.searchFailed'));
      }
    } finally {
      if (currentRequest === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [query]);

  // Filter to only file-type results
  const fileResults = (response?.graph_results || []).filter((item) => {
    const r = item as Record<string, unknown>;
    return r.type === 'file';
  });

  // Open containing folder via backend
  const openFolderFor = useCallback(async (item: Record<string, unknown>) => {
    const path = (item.name as string) || (item.id as string);
    if (!path) return;
    try {
      await api.openFolder(path);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('spotlight.openFolderFailed'));
    }
  }, [t]);

  // Navigate to graph view with this node focused
  const showInGraph = useCallback((item: Record<string, unknown>) => {
    const id = item.id as string;
    if (!id) return;
    navigate(`/graph?focus=${encodeURIComponent(id)}`);
    onClose();
  }, [navigate, onClose]);

  // Send current search result to Search tab and navigate there
  const sendToChat = useCallback(() => {
    if (!response || !searchedQuery) return;

    const fileResults = (response.graph_results || []).filter((item) => {
      const r = item as Record<string, unknown>;
      return r.type === 'file';
    });

    const chatFiles: ChatFile[] = fileResults.map((f) => {
      const r = f as Record<string, unknown>;
      const rawName = (r.name as string) || (r.id as string) || '';
      const fileName = rawName.split('/').pop()?.split('\\').pop() || rawName;
      return {
        file_id: r.id as string,
        file_name: fileName,
        category: (r.category as string) || '',
        summary: (r.summary as string) || '',
      };
    });

    sendFromSpotlight(searchedQuery, response.answer || '', chatFiles);
    navigate('/search');
    onClose();
  }, [response, searchedQuery, sendFromSpotlight, navigate, onClose]);

  // Global keyboard handler (works even if input loses focus e.g. after explorer.exe steals it)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, fileResults.length - 1));
        inputRef.current?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
        inputRef.current?.focus();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const q = query.trim();
        // If query was changed since last search (or no search yet), run search.
        // Otherwise, open the selected file's folder.
        if (q && q !== searchedQuery) {
          void runSearch();
        } else if (fileResults[selectedIndex]) {
          void openFolderFor(fileResults[selectedIndex] as Record<string, unknown>);
        }
      } else if ((e.key === 'v' || e.key === 'V') && e.ctrlKey && e.altKey && fileResults[selectedIndex]) {
        e.preventDefault();
        showInGraph(fileResults[selectedIndex] as Record<string, unknown>);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, fileResults, selectedIndex, onClose, openFolderFor, showInGraph, query, searchedQuery, runSearch]);

  // When window regains focus (e.g. after closing explorer.exe), restore input focus
  useEffect(() => {
    if (!open) return;
    const onFocus = () => inputRef.current?.focus();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [open]);

  // Auto-scroll to selected item
  useEffect(() => {
    const el = itemRefs.current[selectedIndex];
    if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedIndex]);

  if (!open) return null;

  return (
    <div className="spotlight-overlay" onClick={onClose}>
      <div className="spotlight" onClick={(e) => e.stopPropagation()}>
        <div className="spotlight-header">
          <span className="spotlight-icon">🔍</span>
          <input
            ref={inputRef}
            type="text"
            placeholder={t('spotlight.placeholder')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="spotlight-input"
          />
          <span className="spotlight-badge">{t('spotlight.badgeLocal')}</span>
        </div>

        <div className="spotlight-body">
          {!query && !response && (
            <div className="spotlight-hint">
              <div className="spotlight-hint-title">{t('spotlight.hintTitle')}</div>
              <div className="spotlight-examples">
                <div>{t('spotlight.example1')}</div>
                <div>{t('spotlight.example2')}</div>
                <div>{t('spotlight.example3')}</div>
              </div>
            </div>
          )}

          {loading && (
            <div className="spotlight-loading">
              <span className="spotlight-spinner"></span>
              <span>{t('spotlight.loading')}</span>
            </div>
          )}

          {error && (
            <div className="spotlight-error">
              ⚠️ {error}
            </div>
          )}

          {response && !loading && (
            <>
              {response.answer && (
                <div className="spotlight-answer">
                  <div className="spotlight-answer-label">{t('spotlight.answerLabel')}</div>
                  <ReactMarkdown>{response.answer}</ReactMarkdown>
                </div>
              )}

              {fileResults.length > 0 && (
                <div className="spotlight-results">
                  <div className="spotlight-results-label">
                    {t('spotlight.relatedFiles', { count: fileResults.length })}
                  </div>
                  {fileResults.map((item, idx) => {
                    const r = item as Record<string, unknown>;
                    const rawName = (r.name as string) || (r.id as string) || '?';
                    // File name: show only basename (no full path)
                    const displayName = rawName.split('/').pop()?.split('\\').pop() || rawName;
                    const summary = r.summary as string | undefined;
                    const category = r.category as string | undefined;
                    return (
                      <div
                        key={(r.id as string) || idx}
                        ref={(el) => { itemRefs.current[idx] = el; }}
                        className={`spotlight-item ${idx === selectedIndex ? 'selected' : ''}`}
                        onMouseEnter={() => setSelectedIndex(idx)}
                      >
                        <span className="spotlight-item-icon">
                          {TYPE_ICONS.file}
                        </span>
                        <div className="spotlight-item-content">
                          <div className="spotlight-item-name">{displayName}</div>
                          {(summary || category) && (
                            <div className="spotlight-item-meta">
                              {category && <span className="spotlight-item-badge">{category}</span>}
                              {summary && <span className="spotlight-item-summary">{summary}</span>}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {fileResults.length === 0 && !response.answer && (
                <div className="spotlight-empty">{t('spotlight.empty')}</div>
              )}
            </>
          )}
        </div>

        <div className="spotlight-footer">
          {response && searchedQuery ? (
            <>
              <button
                type="button"
                className="spotlight-footer-btn"
                onClick={sendToChat}
                title={t('spotlight.continueInChat', { defaultValue: '대화로 계속하기' })}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                {t('spotlight.continueInChat', { defaultValue: '대화로 계속하기' })}
              </button>
              <div className="spotlight-footer-spacer" />
            </>
          ) : null}
          <span><kbd>↑</kbd><kbd>↓</kbd> {t('spotlight.footerNavigate')}</span>
          <span><kbd>Enter</kbd> {query.trim() && query.trim() !== searchedQuery ? t('spotlight.footerSearch') : t('spotlight.footerOpenFolder')}</span>
          <span><kbd>Ctrl+Alt+V</kbd> {t('spotlight.footerShowGraph')}</span>
          <span><kbd>Esc</kbd> {t('spotlight.footerClose')}</span>
        </div>
      </div>
    </div>
  );
}
