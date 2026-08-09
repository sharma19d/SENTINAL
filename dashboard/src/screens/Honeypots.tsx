import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Shield, Terminal, Key, Clock, RefreshCw, Wifi,
  ChevronDown, ChevronUp, Globe, Ban, CheckCircle,
  AlertCircle, Search, Filter, Activity,
} from 'lucide-react';
import { cn } from '../lib/utils';
import {
  fetchHoneypotSessions, fetchHoneypotStatus, fetchIntel, createFirewallRule,
  HoneypotSession, HoneypotStatus, IntelData,
} from '../lib/api';

function formatDuration(secs: number | null): string {
  if (secs === null) return '—';
  if (secs < 60) return `${Math.floor(secs)}s`;
  return `${Math.floor(secs / 60)}m ${Math.floor(secs % 60)}s`;
}

function formatTime(iso: string): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleTimeString('en-US', { hour12: false }); }
  catch { return iso; }
}

function formatDate(iso: string): string {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
  catch { return iso; }
}

type ServiceFilter = 'all' | 'ssh' | 'telnet' | 'http' | 'ftp';

export default function Honeypots() {
  const [sessions, setSessions] = useState<HoneypotSession[]>([]);
  const [status, setStatus] = useState<HoneypotStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [searchIp, setSearchIp] = useState('');
  const [serviceFilter, setServiceFilter] = useState<ServiceFilter>('all');
  const [successOnly, setSuccessOnly] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadData = useCallback(async () => {
    setRefreshing(true);
    setRefreshError(false);
    try {
      const [s, st] = await Promise.all([fetchHoneypotSessions(), fetchHoneypotStatus()]);
      setSessions(s);
      setStatus(st);
      setLastUpdated(new Date());
    } catch {
      setRefreshError(true);
      setTimeout(() => setRefreshError(false), 3000);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  const filtered = useMemo(() => {
    return sessions.filter(s => {
      if (searchIp && !s.src_ip.includes(searchIp)) return false;
      if (successOnly && !s.success) return false;
      if (serviceFilter !== 'all' && s.service.toLowerCase() !== serviceFilter) return false;
      return true;
    });
  }, [sessions, searchIp, successOnly, serviceFilter]);

  // Top credentials from all sessions
  const topCredentials = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of sessions) {
      for (const a of s.login_attempts) {
        const key = `${a.username} / ${a.password}`;
        counts[key] = (counts[key] || 0) + 1;
      }
    }
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8)
      .map(([cred, count]) => {
        const [username, password] = cred.split(' / ');
        return { username, password, count };
      });
  }, [sessions]);

  // Top attacker IPs
  const topAttackers = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of sessions) counts[s.src_ip] = (counts[s.src_ip] || 0) + 1;
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([ip, count]) => ({ ip, count, success: sessions.some(s => s.src_ip === ip && s.success) }));
  }, [sessions]);

  const successful = sessions.filter(s => s.success);
  const uniqueIps = new Set(sessions.map(s => s.src_ip)).size;
  const totalCreds = sessions.reduce((acc, s) => acc + s.login_attempts.length, 0);

  return (
    <div className="p-4 md:p-10 flex flex-col gap-6 md:gap-8">

      {/* Header */}
      <div className="flex flex-wrap justify-between items-start gap-3">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Honeypot Intelligence</h2>
          <p className="text-xs md:text-sm text-outline mt-1">Attacker sessions captured by Cowrie (SSH/Telnet) & OpenCanary</p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-[10px] font-mono text-outline hidden sm:block">
              Updated {formatTime(lastUpdated.toISOString())}
            </span>
          )}
          <motion.div
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-2 h-2 rounded-full bg-white"
          />
          {refreshError && (
            <span className="text-[10px] font-mono text-white/70 uppercase tracking-wide">Refresh failed</span>
          )}
          <button
            onClick={loadData}
            disabled={refreshing}
            className="text-outline hover:text-white transition-colors p-2 disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        {[
          { label: 'Total Sessions', value: sessions.length, icon: Activity },
          { label: 'Unique Attackers', value: uniqueIps, icon: Wifi },
          { label: 'Successful Logins', value: successful.length, highlight: successful.length > 0, icon: AlertCircle },
          { label: 'Credentials Captured', value: totalCreds, icon: Key },
        ].map(({ label, value, highlight, icon: Icon }) => (
          <div key={label} className={cn(
            'void-card rounded-xl p-4 md:p-5 flex flex-col gap-2',
            highlight && 'border-white/30 glow-white'
          )}>
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">{label}</p>
              <Icon className={cn('w-4 h-4', highlight ? 'text-white' : 'text-outline/50')} />
            </div>
            <p className={cn('text-2xl md:text-3xl font-mono font-bold', highlight ? 'text-white' : 'text-white')}>{value}</p>
          </div>
        ))}
      </div>

      {/* Honeypot Status cards */}
      {status && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4">
          {/* Cowrie */}
          <div className="glass-panel rounded-xl p-4 md:p-5 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-white/10 border border-white/20 flex items-center justify-center flex-shrink-0">
                <Terminal className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-white">{status.cowrie.name}</p>
                <p className="text-[10px] font-mono text-outline mt-0.5">{status.cowrie.ip}</p>
              </div>
              <span className={cn(
                'text-[9px] font-display font-bold px-2 py-1 rounded border uppercase tracking-wider flex-shrink-0',
                status.cowrie.status === 'ONLINE' ? 'bg-white/10 text-white border-white/30' : 'text-outline border-white/10'
              )}>{status.cowrie.status}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 border-t border-white/5 pt-3">
              <div>
                <p className="text-[10px] font-mono text-outline">Sessions</p>
                <p className="text-sm font-mono font-bold text-white">{status.cowrie.total_sessions}</p>
              </div>
              <div>
                <p className="text-[10px] font-mono text-outline">Logins</p>
                <p className="text-sm font-mono font-bold text-white">{status.cowrie.successful_logins}</p>
              </div>
              <div>
                <p className="text-[10px] font-mono text-outline">Attackers</p>
                <p className="text-sm font-mono font-bold text-white">{status.cowrie.unique_attackers}</p>
              </div>
            </div>
          </div>

          {/* OpenCanary */}
          <div className="glass-panel rounded-xl p-4 md:p-5 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                <Shield className="w-5 h-5 text-outline" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-white">{status.opencanary.name}</p>
                <p className="text-[10px] font-mono text-outline mt-0.5">{status.opencanary.ip}</p>
              </div>
              <span className={cn(
                'text-[9px] font-display font-bold px-2 py-1 rounded border uppercase tracking-wider flex-shrink-0',
                status.opencanary.status === 'ONLINE' ? 'bg-white/10 text-white border-white/30' : 'text-outline border-white/10'
              )}>{status.opencanary.status}</span>
            </div>
            <div className="border-t border-white/5 pt-3">
              <p className="text-[10px] font-mono text-outline mb-2">Listening Services</p>
              <div className="flex flex-wrap gap-1.5">
                {status.opencanary.services.map(svc => (
                  <span key={svc} className="px-2 py-1 bg-white/5 border border-white/10 rounded text-[10px] font-mono text-white uppercase tracking-wider">
                    {svc}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Intelligence panels: Top attackers + Top credentials */}
      {sessions.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Top Attacker IPs */}
          <div className="glass-panel rounded-xl p-4 md:p-5">
            <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-3">Top Attacker IPs</p>
            <div className="flex flex-col gap-2">
              {topAttackers.map(({ ip, count, success }) => (
                <div key={ip} className="flex items-center gap-3">
                  <div className={cn(
                    'w-1.5 h-1.5 rounded-full flex-shrink-0',
                    success ? 'bg-white glow-white' : 'bg-outline'
                  )} />
                  <span className="font-mono text-xs text-white flex-1">{ip}</span>
                  {success && (
                    <span className="text-[9px] font-display font-bold text-white bg-white/10 px-1.5 py-0.5 rounded border border-white/20 uppercase">
                      Breached
                    </span>
                  )}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <div className="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-white/40 rounded-full"
                        style={{ width: `${(count / (topAttackers[0]?.count || 1)) * 100}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-outline w-6 text-right">{count}</span>
                  </div>
                </div>
              ))}
              {topAttackers.length === 0 && (
                <p className="text-outline font-mono text-xs">No sessions yet.</p>
              )}
            </div>
          </div>

          {/* Top Credentials */}
          <div className="glass-panel rounded-xl p-4 md:p-5">
            <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-3">Most Attempted Credentials</p>
            <div className="flex flex-col gap-2 max-h-40 overflow-y-auto custom-scrollbar">
              {topCredentials.map(({ username, password, count }) => (
                <div key={`${username}/${password}`} className="flex items-center gap-3 py-1">
                  <Key className="w-3 h-3 text-outline flex-shrink-0" />
                  <span className="font-mono text-xs text-white truncate max-w-[80px]">{username}</span>
                  <span className="text-outline text-xs">/</span>
                  <span className="font-mono text-xs text-white/70 truncate flex-1">{password}</span>
                  <span className="text-[10px] font-mono text-outline flex-shrink-0">×{count}</span>
                </div>
              ))}
              {topCredentials.length === 0 && (
                <p className="text-outline font-mono text-xs">No login attempts recorded.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="glass-panel rounded-xl p-3 md:p-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 bg-black/30 border border-white/10 rounded-lg px-3 py-2 flex-1 min-w-[160px] max-w-xs">
          <Search className="w-4 h-4 text-outline flex-shrink-0" />
          <input
            type="text"
            placeholder="Filter by IP..."
            value={searchIp}
            onChange={e => setSearchIp(e.target.value)}
            className="bg-transparent text-sm font-mono text-white placeholder:text-outline/50 focus:outline-none w-full"
          />
        </div>

        <div className="flex items-center gap-1">
          <Filter className="w-3.5 h-3.5 text-outline" />
          {(['all', 'ssh', 'telnet', 'http', 'ftp'] as ServiceFilter[]).map(f => (
            <button
              key={f}
              onClick={() => setServiceFilter(f)}
              className={cn(
                'px-3 py-1.5 rounded text-[10px] font-display font-bold uppercase tracking-wider transition-all',
                serviceFilter === f
                  ? 'bg-white text-black'
                  : 'text-outline hover:text-white border border-white/10 hover:border-white/30'
              )}
            >
              {f}
            </button>
          ))}
        </div>

        <button
          onClick={() => setSuccessOnly(v => !v)}
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded text-[10px] font-display font-bold uppercase tracking-wider transition-all border',
            successOnly
              ? 'bg-white/10 text-white border-white/30'
              : 'text-outline border-white/10 hover:border-white/30 hover:text-white'
          )}
        >
          <AlertCircle className="w-3.5 h-3.5" />
          Breached Only
        </button>

        <span className="ml-auto text-[10px] font-mono text-outline">
          {filtered.length} / {sessions.length} sessions
        </span>
      </div>

      {/* Sessions list */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-outline font-mono text-sm animate-pulse">
          Loading sessions…
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 gap-4">
          <Shield className="w-10 h-10 text-outline" />
          <p className="text-outline font-mono text-sm">
            {sessions.length === 0
              ? 'No honeypot sessions recorded yet.'
              : 'No sessions match the current filters.'}
          </p>
          {sessions.length === 0 && (
            <p className="text-outline/60 font-mono text-xs">Cowrie will log sessions when attackers connect.</p>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Desktop header */}
          <div className="hidden md:grid grid-cols-[2fr_2fr_1fr_1fr_1fr_1fr_auto] gap-4 px-5 py-3 border-b border-white/5">
            {['Attacker IP', 'Session ID', 'Service', 'Date / Time', 'Duration', 'Attempts', ''].map(h => (
              <span key={h} className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">{h}</span>
            ))}
          </div>

          {filtered.map((session, i) => (
            <SessionRow
              key={session.session_id}
              session={session}
              index={i}
              expanded={expanded === session.session_id}
              onToggle={() => setExpanded(expanded === session.session_id ? null : session.session_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Session Row ──────────────────────────────────────────────────────

type BlockState = 'idle' | 'loading' | 'done' | 'error';

const SessionRow: React.FC<{
  session: HoneypotSession;
  index: number;
  expanded: boolean;
  onToggle: () => void;
}> = ({ session, index, expanded, onToggle }) => {
  const [showIntel, setShowIntel] = useState(false);
  const [intel, setIntel] = useState<IntelData | null>(null);
  const [intelLoading, setIntelLoading] = useState(false);
  const [blockState, setBlockState] = useState<BlockState>('idle');
  const [blockMsg, setBlockMsg] = useState('');

  const loadIntel = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (intel) { setShowIntel(v => !v); return; }
    setIntelLoading(true);
    setShowIntel(true);
    try {
      const data = await fetchIntel(session.src_ip);
      setIntel(data);
    } catch { /* offline */ }
    finally { setIntelLoading(false); }
  };

  const blockIp = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (blockState === 'done') return;
    setBlockState('loading');
    try {
      await createFirewallRule({
        protocol: 'ANY',
        target: session.src_ip,
        action: 'DROP',
        description: `Honeypot attacker — blocked from session ${session.session_id.slice(0, 8)}`,
      });
      setBlockState('done');
      setBlockMsg(`${session.src_ip} blocked`);
    } catch {
      setBlockState('error');
      setBlockMsg('Block failed');
      setTimeout(() => setBlockState('idle'), 3000);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className={cn(
        'border rounded-xl overflow-hidden transition-all',
        session.success ? 'border-white/20 bg-white/[0.04]' : 'border-white/5 bg-white/[0.02]',
        expanded && 'border-white/20'
      )}
    >
      {/* Mobile layout */}
      <div
        className="md:hidden flex items-start gap-3 p-3 cursor-pointer relative"
        onClick={onToggle}
      >
        {session.success && <div className="absolute left-0 top-0 bottom-0 w-1 bg-white glow-white rounded-l-xl" />}
        <div className="w-9 h-9 rounded-lg bg-black border border-white/10 flex items-center justify-center flex-shrink-0">
          <Wifi className="w-4 h-4 text-outline" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm text-white font-bold">{session.src_ip}</span>
            <div className="flex items-center gap-2 flex-shrink-0">
              {session.success && (
                <span className="text-[9px] font-display font-bold text-white bg-white/10 px-1.5 py-0.5 rounded border border-white/20 uppercase">
                  Breached
                </span>
              )}
              {expanded ? <ChevronUp className="w-4 h-4 text-outline" /> : <ChevronDown className="w-4 h-4 text-outline" />}
            </div>
          </div>
          <p className="text-[10px] font-mono text-outline mt-0.5">
            {session.service.toUpperCase()} · {formatDate(session.start_time)} {formatTime(session.start_time)} · {session.login_attempts.length} attempts
          </p>
        </div>
      </div>

      {/* Desktop layout */}
      <div
        className="hidden md:grid grid-cols-[2fr_2fr_1fr_1fr_1fr_1fr_auto] gap-4 items-center px-5 py-4 cursor-pointer relative"
        onClick={onToggle}
      >
        {session.success && <div className="absolute left-0 top-0 bottom-0 w-1 bg-white glow-white rounded-l-xl" />}
        <div className="flex items-center gap-2">
          <Wifi className="w-4 h-4 text-outline flex-shrink-0" />
          <span className="font-mono text-sm text-white">{session.src_ip}</span>
        </div>
        <span className="font-mono text-xs text-outline truncate">{session.session_id}</span>
        <span className="font-mono text-xs text-outline uppercase">{session.service}</span>
        <span className="font-mono text-xs text-outline">{formatDate(session.start_time)} {formatTime(session.start_time)}</span>
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
          {expanded ? <ChevronUp className="w-4 h-4 text-outline" /> : <ChevronDown className="w-4 h-4 text-outline" />}
        </div>
      </div>

      {/* Expanded panel */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/10 p-4 md:p-5 bg-black/40 flex flex-col gap-4">

              {/* Action buttons */}
              <div className="flex flex-wrap gap-2">
                {/* Block IP */}
                <button
                  onClick={blockIp}
                  disabled={blockState === 'loading' || blockState === 'done'}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-display font-bold uppercase tracking-wider transition-all border',
                    blockState === 'done'
                      ? 'bg-white/10 text-white border-white/30 cursor-default'
                      : blockState === 'error'
                      ? 'border-white/20 text-outline'
                      : 'bg-white text-black hover:bg-white/90 border-white'
                  )}
                >
                  {blockState === 'loading' ? (
                    <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
                  ) : blockState === 'done' ? (
                    <CheckCircle className="w-3.5 h-3.5" />
                  ) : (
                    <Ban className="w-3.5 h-3.5" />
                  )}
                  {blockState === 'done' ? blockMsg : blockState === 'error' ? blockMsg : 'Block IP (Add Firewall Rule)'}
                </button>

                {/* IP Intel */}
                <button
                  onClick={loadIntel}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-display font-bold uppercase tracking-wider text-white border border-white/20 hover:bg-white/10 transition-all"
                >
                  <Globe className="w-3.5 h-3.5" />
                  IP Intel
                  <ChevronDown className={cn('w-3 h-3 transition-transform', showIntel && 'rotate-180')} />
                </button>
              </div>

              {/* IP Intel panel */}
              <AnimatePresence>
                {showIntel && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    className="overflow-hidden"
                  >
                    <div className="bg-black/50 rounded-xl p-4 border border-white/10">
                      <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-3">
                        Threat Intelligence — {session.src_ip}
                      </p>
                      {intelLoading ? (
                        <p className="text-xs font-mono text-outline animate-pulse">Querying OTX & AbuseIPDB…</p>
                      ) : intel ? (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <div className={cn(
                            'rounded-lg p-3 border flex flex-col gap-1',
                            intel.is_malicious ? 'bg-white/10 border-white/30' : 'bg-white/[0.02] border-white/5'
                          )}>
                            <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">Verdict</p>
                            <p className={cn('text-base font-bold font-mono', intel.is_malicious ? 'text-white' : 'text-outline')}>
                              {intel.is_malicious ? 'MALICIOUS' : 'CLEAN'}
                            </p>
                          </div>
                          <div className="rounded-lg p-3 border border-white/5 bg-white/[0.02] flex flex-col gap-1">
                            <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">AlienVault OTX</p>
                            <p className="text-base font-bold font-mono text-white">{intel.otx_pulse_count} pulses</p>
                            {intel.otx_tags.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {intel.otx_tags.slice(0, 4).map(tag => (
                                  <span key={tag} className="px-1.5 py-0.5 bg-white/5 border border-white/10 rounded text-[10px] font-mono text-white/60">
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          <div className={cn(
                            'rounded-lg p-3 border flex flex-col gap-1',
                            intel.abuse_score > 50 ? 'bg-white/10 border-white/30' : 'bg-white/[0.02] border-white/5'
                          )}>
                            <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">AbuseIPDB</p>
                            <p className={cn('text-base font-bold font-mono', intel.abuse_score > 50 ? 'text-white' : 'text-outline')}>
                              {intel.abuse_score}%
                            </p>
                            <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                              <div
                                className={cn('h-full rounded-full', intel.abuse_score > 50 ? 'bg-white' : 'bg-outline')}
                                style={{ width: `${intel.abuse_score}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      ) : (
                        <p className="text-xs font-mono text-outline">Intel lookup failed — check API keys in .env</p>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Login attempts */}
              {session.login_attempts.length > 0 && (
                <div>
                  <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-2">
                    Login Attempts ({session.login_attempts.length})
                  </p>
                  <div className="flex flex-col gap-1 max-h-40 overflow-y-auto custom-scrollbar">
                    {session.login_attempts.map((a, idx) => (
                      <div key={idx} className={cn(
                        'flex items-center gap-3 py-1.5 px-3 rounded font-mono text-xs',
                        a.success ? 'bg-white/10 text-white' : 'text-outline'
                      )}>
                        <span className="w-24 truncate">{a.username}</span>
                        <span className="text-white/30">/</span>
                        <span className="flex-1 truncate">{a.password}</span>
                        {a.success && (
                          <span className="text-[9px] text-white font-bold uppercase bg-white/10 px-1.5 py-0.5 rounded flex-shrink-0">
                            Success
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Commands */}
              {session.commands.length > 0 && (
                <div>
                  <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-2">
                    Commands Executed ({session.commands.length})
                  </p>
                  <div className="flex flex-col gap-1 max-h-40 overflow-y-auto custom-scrollbar bg-black/50 rounded-xl p-3">
                    {session.commands.map((cmd, idx) => (
                      <div key={idx} className="flex items-center gap-2 py-0.5 font-mono text-xs text-white/70">
                        <span className="text-outline select-none">$</span>
                        <span className="break-all">{cmd}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {session.login_attempts.length === 0 && session.commands.length === 0 && (
                <p className="text-outline font-mono text-xs">No activity recorded for this session.</p>
              )}

              {/* Session metadata */}
              <div className="pt-2 border-t border-white/5 flex flex-col sm:flex-row sm:justify-between gap-1">
                <span className="text-[10px] font-mono text-outline">
                  Start: {session.start_time ? new Date(session.start_time).toUTCString() : '—'}
                </span>
                <span className="text-[10px] font-mono text-outline truncate">
                  ID: {session.session_id}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
