import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertCircle, ShieldOff, Search, CheckCircle2, Gavel, ShieldCheck, RefreshCw, Globe, ChevronDown } from 'lucide-react';
import { cn } from '../lib/utils';
import { fetchThreats, fetchIntel, createEventSocket, ApiThreat, IntelData } from '../lib/api';

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toUTCString().split(' ')[4] + ' UTC';
}

// indicators can be plain strings OR objects depending on how the agent stored them
type Indicator = string | { type?: string; value?: string; confidence?: number };

function indicatorValue(i: Indicator): string {
  return typeof i === 'string' ? i : (i.value || '');
}

function indicatorType(i: Indicator): string {
  return typeof i === 'string' ? '' : (i.type || '');
}

function sourceFromIndicators(indicators: Indicator[]): string {
  for (const i of indicators) {
    const v = indicatorValue(i);
    const t = indicatorType(i);
    if (t === 'src_ip' || t === 'ip' || /^\d+\.\d+\.\d+\.\d+/.test(v)) return v;
  }
  return indicators.length > 0 ? indicatorValue(indicators[0]) : '—';
}

function targetFromIndicators(indicators: Indicator[]): string {
  for (const i of indicators) {
    const t = indicatorType(i);
    if (t === 'dst_ip' || t === 'target') return indicatorValue(i);
  }
  return '—';
}

export default function Threats() {
  const [threats, setThreats] = useState<ApiThreat[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const loadThreats = useCallback(async () => {
    try {
      const t = await fetchThreats(50);
      setThreats(t);
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadThreats();
    const ws = createEventSocket((channel, data: any) => {
      if (channel === 'sentinel:threat') {
        setThreats(prev => [data as ApiThreat, ...prev].slice(0, 50));
      }
    });
    return () => ws.close();
  }, [loadThreats]);

  const filtered = threats.filter(t =>
    !filter ||
    (t.summary || '').toLowerCase().includes(filter.toLowerCase()) ||
    (t.tactic || '').toLowerCase().includes(filter.toLowerCase()) ||
    (t.technique_id || '').toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="p-10 flex flex-col gap-8 max-w-6xl mx-auto w-full">
      <div className="flex justify-between items-center bg-black/40 backdrop-blur-xl p-6 rounded-2xl border border-white/5 border-t-white/10">
        <div className="flex items-center gap-6">
          <div className="text-[11px] font-display font-bold text-outline tracking-[0.2em] uppercase">Sentinel</div>
          <div className="w-px h-6 bg-white/10" />
          <h2 className="text-3xl font-bold text-white tracking-tight leading-none">Live Threat Feed</h2>
          <span className="text-[10px] font-mono text-outline border border-white/10 px-2 py-1 rounded">
            {threats.length} events
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="bg-white/5 border border-white/10 rounded-full px-4 py-2 flex items-center gap-3 w-64 group focus-within:border-white/30 transition-all">
            <Search className="w-4 h-4 text-outline group-focus-within:text-white" />
            <input
              type="text"
              placeholder="Filter threats..."
              value={filter}
              onChange={e => setFilter(e.target.value)}
              className="bg-transparent border-none text-sm text-white placeholder:text-outline/50 focus:ring-0 p-0 w-full font-mono uppercase tracking-tight"
            />
          </div>
          <button onClick={loadThreats} className="text-outline hover:text-white transition-colors p-2">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-outline font-mono text-sm animate-pulse">
          Loading threat feed…
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 gap-4">
          <CheckCircle2 className="w-10 h-10 text-outline" />
          <p className="text-outline font-mono text-sm">
            {threats.length === 0 ? 'No threats detected. Network is clean.' : 'No threats match the filter.'}
          </p>
        </div>
      ) : (
        <div className="relative mt-4">
          <div className="absolute left-[24px] top-4 bottom-4 w-px bg-gradient-to-b from-white/30 via-white/10 to-transparent" />
          <div className="flex flex-col gap-10">
            {filtered.map((threat, index) => (
              <ThreatCard key={threat.event_id} threat={threat} index={index} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const ThreatCard: React.FC<{ threat: ApiThreat; index: number }> = ({ threat, index }) => {
  const isCritical = (threat.severity || 0) >= 9;
  const src = sourceFromIndicators(threat.indicators);
  const tgt = targetFromIndicators(threat.indicators);
  const code = threat.technique_id
    ? `${threat.technique_id}: ${threat.tactic || 'Unknown'}`
    : threat.tactic || 'Unknown';

  const [showIntel, setShowIntel] = useState(false);
  const [intel, setIntel] = useState<IntelData | null>(null);
  const [intelLoading, setIntelLoading] = useState(false);

  const loadIntel = async () => {
    if (intel) { setShowIntel(v => !v); return; }
    const ip = src !== '—' ? src : null;
    if (!ip || !/^\d+\.\d+\.\d+\.\d+/.test(ip)) { setShowIntel(v => !v); return; }
    setIntelLoading(true);
    setShowIntel(true);
    try {
      const data = await fetchIntel(ip);
      setIntel(data);
    } catch { /* offline */ }
    finally { setIntelLoading(false); }
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.07 }}
      className="relative pl-[60px]"
    >
      <div className={cn(
        'absolute left-[19px] top-[24px] w-[11px] h-[11px] rounded-full z-10 ring-4 ring-black',
        isCritical ? 'bg-white glow-white' : 'bg-outline'
      )} />

      <div className={cn(
        'relative rounded-2xl overflow-hidden transition-all duration-300',
        isCritical
          ? 'bg-black border border-white/30 shadow-[0_0_40px_rgba(255,255,255,0.05)]'
          : 'glass-panel-heavy border-white/10'
      )}>
        {isCritical && (
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/50 to-transparent" />
        )}

        <div className="p-8">
          <div className="flex justify-between items-start mb-6">
            <div className="flex items-center gap-3">
              <span className={cn('text-[11px] font-mono leading-none tracking-tight uppercase', isCritical ? 'text-white' : 'text-outline')}>
                {formatTime(threat.timestamp)}
              </span>
              <div className="w-1 h-1 bg-white/20 rounded-full" />
              <span className={cn('text-[11px] font-mono leading-none tracking-tight uppercase', isCritical ? 'text-white' : 'text-white/60')}>
                {code}
              </span>
            </div>
            <div className={cn(
              'px-3 py-1.5 rounded flex items-center gap-2 border',
              isCritical ? 'bg-white/10 border-white text-white' : 'bg-white/5 border-white/20 text-white/80'
            )}>
              <AlertCircle className="w-3.5 h-3.5" />
              <span className="text-[10px] font-display font-bold uppercase tracking-widest leading-none">
                SEV {String(threat.severity || 0).padStart(2, '0')}
              </span>
            </div>
          </div>

          <div className="mb-8">
            <h3 className={cn('text-xl font-bold mb-2 tracking-tight', isCritical ? 'text-white' : 'text-on-surface')}>
              {threat.summary || 'Unclassified threat event'}
            </h3>
            <p className="text-sm text-on-surface-variant leading-relaxed max-w-2xl">
              Confidence: {threat.confidence != null ? `${(threat.confidence * 100).toFixed(0)}%` : 'N/A'}
              {threat.indicators.length > 0 && ` · ${threat.indicators.length} indicator${threat.indicators.length > 1 ? 's' : ''} detected`}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-6 mb-8 bg-white/[0.03] p-4 rounded-xl border border-white/5">
            <div>
              <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-1.5">Source Vector</p>
              <p className={cn('text-sm font-mono tracking-tight', isCritical ? 'text-white' : 'text-white/80')}>{src}</p>
            </div>
            <div>
              <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-1.5">Target / Device</p>
              <p className={cn('text-sm font-mono tracking-tight', isCritical ? 'text-white' : 'text-white/80')}>
                {tgt !== '—' ? tgt : (threat.device_id || '—')}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-6 border-t border-white/10">
            <div className={cn('flex items-center gap-2', isCritical ? 'text-white' : 'text-outline')}>
              {isCritical ? <ShieldOff className="w-4 h-4" /> : threat.resolved ? <ShieldCheck className="w-4 h-4" /> : <Gavel className="w-4 h-4" />}
              <span className="text-[11px] font-mono uppercase tracking-wider">
                {threat.action_taken || (threat.resolved ? 'Resolved' : 'Pending')}
              </span>
            </div>
            <div className="flex gap-3">
              <button className="px-5 py-2 text-xs font-bold font-display uppercase tracking-wider text-white border border-white/20 rounded-lg hover:bg-white/10 transition-all">
                Acknowledge
              </button>
              <button
                onClick={loadIntel}
                className="flex items-center gap-2 px-5 py-2 text-xs font-bold font-display uppercase tracking-wider text-white border border-white/20 rounded-lg hover:bg-white/10 transition-all"
              >
                <Globe className="w-3.5 h-3.5" />
                IP Intel
                <ChevronDown className={cn('w-3 h-3 transition-transform', showIntel && 'rotate-180')} />
              </button>
              <button className={cn(
                'px-5 py-2 text-xs font-bold font-display uppercase tracking-wider rounded-lg transition-all',
                isCritical
                  ? 'bg-white text-black hover:bg-white/90 shadow-[0_0_15px_rgba(255,255,255,0.2)]'
                  : 'border border-white/20 text-white hover:bg-white/10'
              )}>
                {isCritical ? 'Investigate' : 'View Logs'}
              </button>
            </div>
          </div>
        </div>

        {/* Intel panel */}
        <AnimatePresence>
          {showIntel && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden border-t border-white/10"
            >
              <div className="p-6 bg-black/50">
                <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-4">
                  Threat Intelligence — {src}
                </p>

                {intelLoading ? (
                  <p className="text-sm font-mono text-outline animate-pulse">Querying OTX & AbuseIPDB…</p>
                ) : intel ? (
                  <div className="grid grid-cols-3 gap-4">
                    {/* Malicious flag */}
                    <div className={cn(
                      'rounded-xl p-4 border flex flex-col gap-2',
                      intel.is_malicious ? 'bg-white/10 border-white/30' : 'bg-white/[0.02] border-white/5'
                    )}>
                      <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">Verdict</p>
                      <p className={cn('text-lg font-bold font-mono', intel.is_malicious ? 'text-white' : 'text-outline')}>
                        {intel.is_malicious ? 'MALICIOUS' : 'CLEAN'}
                      </p>
                    </div>

                    {/* OTX */}
                    <div className="rounded-xl p-4 border border-white/5 bg-white/[0.02] flex flex-col gap-2">
                      <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">AlienVault OTX</p>
                      <p className="text-lg font-bold font-mono text-white">{intel.otx_pulse_count} pulses</p>
                      {intel.otx_tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {intel.otx_tags.slice(0, 5).map(tag => (
                            <span key={tag} className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-[10px] font-mono text-white/60">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* AbuseIPDB */}
                    <div className={cn(
                      'rounded-xl p-4 border flex flex-col gap-2',
                      intel.abuse_score > 50 ? 'bg-white/10 border-white/30' : 'bg-white/[0.02] border-white/5'
                    )}>
                      <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">AbuseIPDB Score</p>
                      <p className={cn('text-lg font-bold font-mono', intel.abuse_score > 50 ? 'text-white' : 'text-outline')}>
                        {intel.abuse_score}%
                      </p>
                      <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full transition-all', intel.abuse_score > 50 ? 'bg-white' : 'bg-outline')}
                          style={{ width: `${intel.abuse_score}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm font-mono text-outline">
                    {src === '—' ? 'No source IP available for this threat.' : 'Intel lookup failed — check API keys in .env'}
                  </p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
