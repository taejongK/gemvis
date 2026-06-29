import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { api } from './api';
import type { Task } from './types';

interface Props {
  date: string;
  onChanged?: () => void;
}

export default function TaskSection({ date, onChanged }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [tasks, setTasks] = useState<Task[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const flashInfo = (text: string) => {
    setInfo(text);
    window.setTimeout(() => setInfo((cur) => (cur === text ? null : cur)), 3500);
  };

  const today = new Date().toISOString().slice(0, 10);
  const isEditable = date >= today;

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.tasks.list(date);
      setTasks(r.tasks);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'load failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  const addOne = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      await api.tasks.add(text, date);
      setInput('');
      await load();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'add failed');
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (task: Task) => {
    setBusy(true);
    try {
      await api.tasks.update(task.id, { completed: !task.completed });
      await load();
      onChanged?.();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    setBusy(true);
    try {
      await api.tasks.delete(id);
      await load();
      onChanged?.();
    } finally {
      setBusy(false);
    }
  };

  const recheck = async () => {
    setEvaluating(true);
    setError(null);
    try {
      const r = await api.tasks.evaluate(date);
      setTasks(r.tasks);
      onChanged?.();
      // Tell the user what happened — without a toast, recheck silently
      // returning 0 looked like the button did nothing.
      if ((r.file_count ?? 0) === 0) {
        flashInfo(t('calendar.tasks.recheckNoFiles'));
      } else if (r.updated > 0) {
        flashInfo(t('calendar.tasks.recheckUpdated', { count: r.updated }));
      } else {
        flashInfo(t('calendar.tasks.recheckNoChange'));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'evaluate failed');
    } finally {
      setEvaluating(false);
    }
  };

  const showInGraph = (path: string) => {
    const focus = `file:${path}`;
    navigate(
      `/graph?focus=${encodeURIComponent(focus)}&from=calendar&date=${encodeURIComponent(date)}`,
    );
  };

  const openInExplorer = async (path: string) => {
    try {
      await api.openFolder(path);
    } catch (err) {
      console.error('openFolder failed:', err);
    }
  };

  const total = tasks.length;
  const done = tasks.filter((t) => t.completed).length;

  return (
    <section className="task-section">
      <header className="task-section-head">
        <h3>
          {t('calendar.tasks.heading')}
          <span
            className="summary-block-info"
            tabIndex={0}
            role="button"
            aria-label={t('calendar.tasks.headingHint')}
          >
            ⓘ
            <span className="summary-block-info-popup" role="tooltip">
              {t('calendar.tasks.headingHint')}
            </span>
          </span>
        </h3>
        <div className="task-section-meta">
          {total > 0 && (
            <span className="task-progress">
              {t('calendar.tasks.progress', { done, total })}
            </span>
          )}
          {total > 0 && (
            <button
              type="button"
              className="btn btn-ghost"
              disabled={evaluating || busy}
              onClick={recheck}
            >
              {evaluating ? t('calendar.tasks.evaluating') : t('calendar.tasks.recheck')}
            </button>
          )}
        </div>
      </header>

      {isEditable ? (
        <div className="task-input-row">
          <input
            type="text"
            className="task-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') addOne();
            }}
            placeholder={t('calendar.tasks.inputPlaceholder')}
            disabled={busy}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={addOne}
            disabled={busy || !input.trim()}
          >
            {t('calendar.tasks.addButton')}
          </button>
        </div>
      ) : (
        <div className="task-readonly-hint">{t('calendar.tasks.readonlyHint')}</div>
      )}

      {error && <div className="task-error">{error}</div>}
      {info && <div className="task-info">{info}</div>}

      {loading ? (
        <div className="loading">{t('calendar.loadingDay')}</div>
      ) : total === 0 ? (
        <div className="task-empty">{t('calendar.tasks.empty')}</div>
      ) : (
        <ul className="task-list">
          {tasks.map((task) => (
            <TaskItem
              key={task.id}
              task={task}
              busy={busy}
              onToggle={() => toggle(task)}
              onDelete={() => remove(task.id)}
              showInGraph={showInGraph}
              openInExplorer={openInExplorer}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

interface TaskItemProps {
  task: Task;
  busy: boolean;
  onToggle: () => void;
  onDelete: () => void;
  showInGraph: (path: string) => void;
  openInExplorer: (path: string) => Promise<void>;
}

function TaskItem({ task, busy, onToggle, onDelete, showInGraph, openInExplorer }: TaskItemProps) {
  const { t } = useTranslation();
  const hasFiles = task.related_files.length > 0;
  return (
    <li className={`task-item${task.completed ? ' task-completed' : ''}`}>
      <label className="task-row">
        <input
          type="checkbox"
          className="task-check"
          checked={task.completed}
          onChange={onToggle}
          disabled={busy}
        />
        <span className="task-text">{task.text}</span>
        {task.rollover_count > 0 && task.original_date && (() => {
          const [, mm, dd] = task.original_date.split('-');
          const label = `${Number(mm)}/${Number(dd)}`;
          return (
            <span
              className="task-rollover"
              title={t('calendar.tasks.rolloverTitle', {
                count: task.rollover_count,
                date: task.original_date,
              })}
            >
              {t('calendar.tasks.rolloverInline', {
                date: label,
                count: task.rollover_count,
              })}
            </span>
          );
        })()}
        <button
          type="button"
          className="task-delete"
          onClick={onDelete}
          aria-label={t('calendar.tasks.deleteTitle')}
          title={t('calendar.tasks.deleteTitle')}
          disabled={busy}
        >
          ×
        </button>
      </label>
      {task.completed && hasFiles && (
        <details className="task-related summary-block-files">
          <summary>{t('calendar.tasks.relatedFiles', { count: task.related_files.length })}</summary>
          {task.evidence && <div className="task-evidence">{task.evidence}</div>}
          <ul>
            {task.related_files.map((p) => {
              const basename = p.split(/[\\/]/).pop() || p;
              return (
                <li key={p}>
                  <button
                    type="button"
                    className="summary-file-name"
                    onClick={() => showInGraph(p)}
                    title={t('calendar.showInGraphTitle')}
                  >
                    {basename}
                  </button>
                  <button
                    type="button"
                    className="summary-file-open"
                    onClick={() => openInExplorer(p)}
                    title={t('calendar.openFolderTitle')}
                    aria-label={t('calendar.openFolderTitle')}
                  >
                    📂
                  </button>
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </li>
  );
}
