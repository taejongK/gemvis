import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from './api';

interface FolderPickerProps {
  open: boolean;
  onSelect: (path: string) => void;
  onCancel: () => void;
}

export default function FolderPicker({ open, onSelect, onCancel }: FolderPickerProps) {
  const { t } = useTranslation();
  const [currentPath, setCurrentPath] = useState('');
  const [pathInput, setPathInput] = useState('');
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [dirs, setDirs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const browse = useCallback((path?: string) => {
    setLoading(true);
    setError('');
    api.browseDirs(path).then((res) => {
      setCurrentPath(res.current);
      setPathInput(res.current);
      setParentPath(res.parent);
      setDirs(res.dirs);
      if (res.error === 'not_found') setError(t('folderPicker.error'));
    }).catch(() => {
      setError(t('folderPicker.error'));
    }).finally(() => {
      setLoading(false);
    });
  }, [t]);

  useEffect(() => {
    if (open) browse();
  }, [open, browse]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const dirName = (fullPath: string) => {
    const parts = fullPath.replace(/\/+$/, '').split('/');
    return parts[parts.length - 1] || fullPath;
  };

  const goToInput = () => {
    const p = pathInput.trim();
    if (p) browse(p);
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal folder-picker-modal" onClick={(e) => e.stopPropagation()}>
        <h3>{t('folderPicker.title')}</h3>

        <div className="folder-picker-path-row">
          <input
            type="text"
            className="folder-picker-path-input"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); goToInput(); }
            }}
          />
          <button className="btn btn-ghost" disabled={loading} onClick={goToInput}>
            &crarr;
          </button>
        </div>

        <div className="folder-picker-nav">
          <button
            className="btn btn-ghost"
            disabled={!parentPath || loading}
            onClick={() => parentPath && browse(parentPath)}
          >
            {t('folderPicker.parent')}
          </button>
          <button
            className="btn btn-ghost"
            disabled={loading}
            onClick={() => browse()}
          >
            {t('folderPicker.home')}
          </button>
        </div>

        <div className="folder-picker-list">
          {loading && <div className="folder-picker-empty">{t('folderPicker.loading')}</div>}
          {error && <div className="folder-picker-empty">{error}</div>}
          {!loading && !error && dirs.length === 0 && (
            <div className="folder-picker-empty">{t('folderPicker.empty')}</div>
          )}
          {!loading && !error && dirs.map((d) => (
            <button
              key={d}
              type="button"
              className="folder-picker-item"
              onClick={() => browse(d)}
            >
              <span className="folder-picker-item-name">{dirName(d)}</span>
              <span className="folder-picker-item-chevron" aria-hidden="true">&rsaquo;</span>
            </button>
          ))}
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onCancel}>{t('common.cancel')}</button>
          <button
            className="btn btn-primary"
            disabled={!currentPath}
            onClick={() => onSelect(currentPath)}
          >
            {t('folderPicker.select')}
          </button>
        </div>
      </div>
    </div>
  );
}
