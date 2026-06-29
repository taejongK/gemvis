import { useEffect, useState } from 'react';
import { api } from './api';
import type { GraphStats, WatcherStatus } from './types';

export default function StatusBar() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [watcher, setWatcher] = useState<WatcherStatus | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let active = true;
    const poll = async () => {
      if (!active) return;
      if (document.hidden) {
        timer = setTimeout(poll, 30_000);
        return;
      }
      try {
        const [d, w] = await Promise.all([
          api.files({ limit: 1, include_stats: true }),
          api.watcherStatus(),
        ]);
        if (active) {
          setStats(d.stats);
          setWatcher(w);
        }
      } catch { /* silent */ }
      if (active) timer = setTimeout(poll, 30_000);
    };
    poll();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, []);

  const nodeCount = stats?.total_nodes ?? 0;
  const fileCount = stats?.node_types?.file ?? 0;
  const watching = watcher?.running;

  return (
    <div className="statusbar">
      <div className="statusbar-item">
        <span className="statusbar-dot" />
        <span>gemma-4-E2B-it</span>
      </div>
      <div className="statusbar-item">
        <span>🔒</span>
        <span>100% Local</span>
      </div>
      <div className="statusbar-item muted">
        <code>{fileCount} files</code>
        <span>·</span>
        <code>{nodeCount} nodes</code>
      </div>
      <div className={`statusbar-item${watching ? '' : ' warn'}`}>
        <span className="statusbar-dot" />
        <span>{watching ? 'watching' : 'idle'}</span>
        {watcher?.watch_dirs && watcher.watch_dirs.length > 0 && (
          <code title={watcher.watch_dirs.join('\n')}>
            {watcher.watch_dirs.length === 1
              ? shortPath(watcher.watch_dirs[0])
              : `${shortPath(watcher.watch_dirs[0])} +${watcher.watch_dirs.length - 1}`}
          </code>
        )}
      </div>
    </div>
  );
}

function shortPath(p: string): string {
  const parts = p.split(/[\\/]/).filter(Boolean);
  if (parts.length <= 2) return p;
  return '…/' + parts.slice(-2).join('/');
}
