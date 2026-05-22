import React, { useCallback, useEffect, useState } from 'react';
import { FileText, RefreshCw } from 'lucide-react';
import { fetchLogs, ApiLogsResponse } from '../lib/api';

const LEVELS = ['all', 'info', 'warning', 'error'];

export default function Logs() {
  const [data, setData] = useState<ApiLogsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState<string | undefined>(undefined);
  const [query, setQuery] = useState('');
  const [level, setLevel] = useState('all');

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetchLogs({
        file,
        lines: 300,
        query: query.trim() || undefined,
        level: level === 'all' ? undefined : level,
      });
      setData(response);
      if (!file && response.active_file) {
        setFile(response.active_file);
      }
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [file, query, level]);

  useEffect(() => {
    const timer = window.setTimeout(() => { loadLogs(); }, 200);
    return () => window.clearTimeout(timer);
  }, [loadLogs]);

  return (
    <div className="p-4 md:p-10 flex flex-col gap-4 md:gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Service Logs</h2>
          <p className="text-sm text-outline mt-1">Live operational logs from SENTINEL services.</p>
        </div>
        <button
          onClick={loadLogs}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white text-black text-xs font-display font-bold uppercase tracking-wider hover:bg-white/90 transition-all flex-shrink-0"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="glass-panel rounded-xl border border-white/10 p-4 flex flex-wrap items-center gap-3">
        <select
          value={file || ''}
          onChange={(e) => setFile(e.target.value || undefined)}
          className="bg-black/50 border border-white/10 rounded px-3 py-2 text-xs font-mono text-white"
        >
          {(data?.files || []).map((f) => (
            <option key={f.name} value={f.name}>{f.name}</option>
          ))}
        </select>

        <select
          value={level}
          onChange={(e) => setLevel(e.target.value)}
          className="bg-black/50 border border-white/10 rounded px-3 py-2 text-xs font-mono text-white uppercase"
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>

        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search logs..."
          className="flex-1 min-w-[220px] bg-black/50 border border-white/10 rounded px-3 py-2 text-xs font-mono text-white placeholder:text-outline"
        />
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center text-outline font-mono text-sm animate-pulse">Loading logs…</div>
      ) : !data ? (
        <div className="glass-panel rounded-xl p-8 border border-white/10 text-outline">Logs unavailable. Backend might be offline.</div>
      ) : data.files.length === 0 ? (
        <div className="glass-panel rounded-xl p-8 border border-white/10 text-outline">No log files found in /logs.</div>
      ) : (
        <div className="glass-panel rounded-xl border border-white/10 overflow-hidden">
          <div className="px-5 py-3 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2 text-outline">
              <FileText className="w-4 h-4" />
              <span className="text-xs font-mono uppercase tracking-wide">{data.active_file}</span>
            </div>
            <span className="text-[11px] font-mono text-outline">{data.entries.length} lines</span>
          </div>

          <div className="max-h-[560px] overflow-y-auto custom-scrollbar">
            {data.entries.length === 0 ? (
              <div className="px-5 py-8 text-outline font-mono text-sm">No log entries match your filters.</div>
            ) : (
              data.entries.map((entry) => (
                <div key={`${entry.line_no}-${entry.raw}`} className="px-5 py-2 border-b border-white/5 hover:bg-white/[0.02]">
                  <div className="flex items-start gap-2 md:gap-3 text-xs font-mono">
                    <span className="hidden sm:block text-outline w-16 text-right shrink-0">{entry.line_no}</span>
                    <span className="hidden sm:block text-outline shrink-0">{entry.timestamp || '—'}</span>
                    <span
                      className={`shrink-0 uppercase ${
                        entry.level === 'error' ? 'text-white' : entry.level === 'warning' ? 'text-white/80' : 'text-outline'
                      }`}
                    >
                      [{entry.level}]
                    </span>
                    <span className="text-on-surface break-all">{entry.message || entry.raw}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
