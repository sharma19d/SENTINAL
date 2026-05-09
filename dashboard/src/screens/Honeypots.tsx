import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'motion/react';
import { Shield, Terminal, Key, Clock, RefreshCw, Wifi, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../lib/utils';
import { fetchHoneypotSessions, fetchHoneypotStatus, HoneypotSession, HoneypotStatus } from '../lib/api';

function formatDuration(secs: number | null): string {
  if (secs === null) return '—';
  if (secs < 60) return `${Math.floor(secs)}s`;
  return `${Math.floor(secs / 60)}m ${Math.floor(secs % 60)}s`;
}

function formatTime(iso: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString('en-US', { hour12: false });
  } catch { return iso; }
}

export default function Honeypots() {
  const [sessions, setSessions] = useState<HoneypotSession[]>([]);
  const [status, setStatus] = useState<HoneypotStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([fetchHoneypotSessions(), fetchHoneypotStatus()]);
      setSessions(s);
      setStatus(st);
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  const successful = sessions.filter(s => s.success);
  const uniqueIps = new Set(sessions.map(s => s.src_ip)).size;
  const totalCreds = sessions.reduce((acc, s) => acc + s.login_attempts.length, 0);

  return (
    <div className="p-10 flex flex-col gap-8">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">Honeypot Sessions</h2>
          <p className="text-sm text-outline mt-1">Live attacker sessions captured by Cowrie & OpenCanary</p>
        </div>
        <button onClick={loadData} className="text-outline hover:text-white transition-colors p-2">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total Sessions', value: sessions.length },
          { label: 'Unique Attackers', value: uniqueIps },
          { label: 'Successful Logins', value: successful.length },
          { label: 'Credentials Captured', value: totalCreds },
        ].map(({ label, value }) => (
          <div key={label} className="void-card rounded-xl p-5">
            <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-2">{label}</p>
            <p className="text-3xl font-mono font-bold text-white">{value}</p>
          </div>
        ))}
      </div>

      {/* Honeypot status */}
      {status && (
        <div className="grid grid-cols-2 gap-4">
          <div className="glass-panel rounded-xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-white/10 border border-white/20 flex items-center justify-center">
              <Terminal className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white">{status.cowrie.name}</p>
              <p className="text-[10px] font-mono text-outline mt-0.5">
                {status.cowrie.ip} · {status.cowrie.unique_attackers} unique attackers
              </p>
            </div>
            <span className={cn(
              'ml-auto text-[9px] font-display font-bold px-2 py-1 rounded border uppercase tracking-wider',
              status.cowrie.status === 'ONLINE' ? 'bg-white/10 text-white border-white/30' : 'text-outline border-white/10'
            )}>{status.cowrie.status}</span>
          </div>
          <div className="glass-panel rounded-xl p-5 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-outline" />
            </div>
            <div>
              <p className="text-sm font-bold text-white">{status.opencanary.name}</p>
              <p className="text-[10px] font-mono text-outline mt-0.5">
                {status.opencanary.ip} · {status.opencanary.services.join(', ')}
              </p>
            </div>
            <span className={cn(
              'ml-auto text-[9px] font-display font-bold px-2 py-1 rounded border uppercase tracking-wider',
              status.opencanary.status === 'ONLINE' ? 'bg-white/10 text-white border-white/30' : 'text-outline border-white/10'
            )}>{status.opencanary.status}</span>
          </div>
        </div>
      )}

      {/* Sessions list */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-outline font-mono text-sm animate-pulse">
          Loading sessions…
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 gap-4">
          <Shield className="w-10 h-10 text-outline" />
          <p className="text-outline font-mono text-sm">No honeypot sessions recorded yet.</p>
          <p className="text-outline/60 font-mono text-xs">Cowrie will log sessions when attackers connect.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-[2fr_2fr_1fr_1fr_1fr_1fr_auto] gap-4 px-5 py-3 border-b border-white/5">
            {['Attacker IP', 'Session ID', 'Service', 'Start Time', 'Duration', 'Attempts', ''].map(h => (
              <span key={h} className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">{h}</span>
            ))}
          </div>
          {sessions.map((session, i) => (
            <motion.div key={session.session_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
              <div
                className={cn(
                  'grid grid-cols-[2fr_2fr_1fr_1fr_1fr_1fr_auto] gap-4 items-center px-5 py-4 rounded-xl border transition-all cursor-pointer',
                  session.success ? 'bg-white/[0.05] border-white/20' : 'bg-white/[0.02] border-white/5 hover:border-white/10',
                  expanded === session.session_id && 'rounded-b-none border-b-0'
                )}
                onClick={() => setExpanded(expanded === session.session_id ? null : session.session_id)}
              >
                {session.success && <div className="absolute left-0 top-0 bottom-0 w-1 bg-white glow-white rounded-l-xl" />}
                <div className="flex items-center gap-2">
                  <Wifi className="w-4 h-4 text-outline flex-shrink-0" />
                  <span className="font-mono text-sm text-white">{session.src_ip}</span>
                </div>
                <span className="font-mono text-xs text-outline truncate">{session.session_id}</span>
                <span className="font-mono text-xs text-outline uppercase">{session.service}</span>
                <span className="font-mono text-xs text-outline">{formatTime(session.start_time)}</span>
                <div className="flex items-center gap-1 text-outline">
                  <Clock className="w-3 h-3" />
                  <span className="font-mono text-xs">{formatDuration(session.duration)}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Key className="w-3 h-3 text-outline" />
                  <span className={cn('font-mono text-xs', session.success ? 'text-white font-bold' : 'text-outline')}>
                    {session.login_attempts.length}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {session.success && (
                    <span className="text-[9px] font-display font-bold text-white bg-white/10 px-2 py-0.5 rounded border border-white/30 uppercase">
                      Breached
                    </span>
                  )}
                  {expanded === session.session_id ? <ChevronUp className="w-4 h-4 text-outline" /> : <ChevronDown className="w-4 h-4 text-outline" />}
                </div>
              </div>

              {expanded === session.session_id && (
                <div className="bg-white/[0.02] border border-t-0 border-white/10 rounded-b-xl p-5 flex flex-col gap-4">
                  {session.login_attempts.length > 0 && (
                    <div>
                      <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-2">Login Attempts</p>
                      <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
                        {session.login_attempts.map((a, idx) => (
                          <div key={idx} className={cn(
                            'flex items-center gap-4 py-1.5 px-3 rounded font-mono text-xs',
                            a.success ? 'bg-white/10 text-white' : 'text-outline'
                          )}>
                            <span className="w-20 truncate">{a.username}</span>
                            <span className="text-white/40">/</span>
                            <span className="flex-1 truncate">{a.password}</span>
                            {a.success && <span className="text-[9px] text-white font-bold uppercase">Success</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {session.commands.length > 0 && (
                    <div>
                      <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-2">Commands Executed</p>
                      <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
                        {session.commands.map((cmd, idx) => (
                          <div key={idx} className="flex items-center gap-2 py-1 px-3 bg-black/50 rounded font-mono text-xs text-white/70">
                            <span className="text-outline">$</span>
                            <span>{cmd}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {session.login_attempts.length === 0 && session.commands.length === 0 && (
                    <p className="text-outline font-mono text-xs">No activity recorded for this session.</p>
                  )}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
