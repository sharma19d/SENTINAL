import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'motion/react';
import { Shield, ShieldAlert, Network, Lock, Gavel, Activity, Cpu, Brain, Zap, Plus, Trash2, RefreshCw } from 'lucide-react';
import { cn } from '../lib/utils';
import {
  fetchFirewallRules, createFirewallRule, toggleFirewallRule, deleteFirewallRule,
  fetchHoneypotStatus, fetchSystemMetrics, fetchSettings, updateSettings,
  ApiFirewallRule, HoneypotStatus, SystemMetrics,
} from '../lib/api';

export default function Firewall() {
  const [rules, setRules] = useState<ApiFirewallRule[]>([]);
  const [honeypots, setHoneypots] = useState<HoneypotStatus | null>(null);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [autoQuarantine, setAutoQuarantine] = useState(true);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState(false);
  const [showNewRule, setShowNewRule] = useState(false);
  const [newRule, setNewRule] = useState({ protocol: 'TCP/22', target: '0.0.0.0/0', action: 'DROP', description: '' });

  const loadAll = useCallback(async () => {
    setRefreshing(true);
    setRefreshError(false);
    try {
      const [r, h, m, s] = await Promise.all([
        fetchFirewallRules(),
        fetchHoneypotStatus(),
        fetchSystemMetrics(),
        fetchSettings(),
      ]);
      setRules(r);
      setHoneypots(h);
      setMetrics(m);
      setAutoQuarantine(s.auto_quarantine);
    } catch {
      setRefreshError(true);
      setTimeout(() => setRefreshError(false), 3000);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleToggle = async (ruleId: string) => {
    await toggleFirewallRule(ruleId);
    setRules(prev => prev.map(r => r.rule_id === ruleId ? { ...r, enabled: !r.enabled } : r));
  };

  const handleDelete = async (ruleId: string) => {
    await deleteFirewallRule(ruleId);
    setRules(prev => prev.filter(r => r.rule_id !== ruleId));
  };

  const handleCreate = async () => {
    const rule = await createFirewallRule(newRule);
    setRules(prev => [...prev, rule]);
    setShowNewRule(false);
    setNewRule({ protocol: 'TCP/22', target: '0.0.0.0/0', action: 'DROP', description: '' });
  };

  const handlePolicyChange = async (val: boolean) => {
    setAutoQuarantine(val);
    await updateSettings({ auto_quarantine: val });
  };

  return (
    <div className="p-4 md:p-10 flex flex-col gap-6 md:gap-10">
      <div className="flex flex-wrap justify-between items-start gap-3">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Security Controls & Firewall</h2>
          <p className="text-xs md:text-sm text-outline mt-1 font-sans">Active defensive posture management and nftables rule configuration.</p>
        </div>
        <div className="flex items-center gap-3">
          <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 2, repeat: Infinity }}
            className="w-2.5 h-2.5 rounded-full bg-white glow-white" />
          <span className="text-[11px] font-mono text-white uppercase tracking-widest font-bold">System Armed</span>
          {refreshError && (
            <span className="text-[10px] font-mono text-white/70 uppercase tracking-wide">Refresh failed</span>
          )}
          <button
            onClick={loadAll}
            disabled={refreshing}
            className="text-outline hover:text-white transition-colors p-2 ml-2 disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-4 md:gap-8 items-stretch">
        {/* Firewall Rules Table */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-8">
          <section className="glass-panel rounded-2xl p-6 flex flex-col">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-white flex items-center gap-3">
                <Shield className="w-5 h-5" />
                Active Firewall Rules
              </h3>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-display font-bold text-outline border border-white/10 px-3 py-1 rounded uppercase tracking-wider">NFTABLES</span>
                <button onClick={() => setShowNewRule(v => !v)}
                  className="flex items-center gap-2 bg-white text-black px-3 py-1.5 rounded text-[10px] font-display font-bold uppercase tracking-wider hover:bg-white/90 transition-all">
                  <Plus className="w-3 h-3" /> New Rule
                </button>
              </div>
            </div>

            {showNewRule && (
              <div className="mb-4 p-4 bg-white/5 border border-white/10 rounded-xl flex flex-wrap gap-3 items-end">
                <div className="flex flex-col gap-1">
                  <label className="text-[9px] font-display font-bold text-outline uppercase tracking-widest">Protocol</label>
                  <input value={newRule.protocol} onChange={e => setNewRule(p => ({ ...p, protocol: e.target.value }))}
                    className="bg-black border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-white/30 w-28" />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[9px] font-display font-bold text-outline uppercase tracking-widest">Target</label>
                  <input value={newRule.target} onChange={e => setNewRule(p => ({ ...p, target: e.target.value }))}
                    className="bg-black border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-white/30 w-36" />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[9px] font-display font-bold text-outline uppercase tracking-widest">Action</label>
                  <select value={newRule.action} onChange={e => setNewRule(p => ({ ...p, action: e.target.value }))}
                    className="bg-black border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-white/30">
                    {['DROP', 'REJECT', 'ACCEPT', 'LOG_ONLY'].map(a => <option key={a}>{a}</option>)}
                  </select>
                </div>
                <button onClick={handleCreate}
                  className="bg-white text-black px-4 py-1.5 rounded text-xs font-bold uppercase tracking-wider hover:bg-white/90 transition-all">
                  Add
                </button>
                <button onClick={() => setShowNewRule(false)} className="text-outline hover:text-white transition-colors text-xs px-2">Cancel</button>
              </div>
            )}

            <div className="void-card rounded-xl overflow-hidden border border-white/5">
              {loading ? (
                <div className="p-8 text-center text-outline font-mono text-sm animate-pulse">Loading rules…</div>
              ) : (
                <table className="w-full text-left border-collapse">
                  <thead className="bg-white/5 border-b border-white/5">
                    <tr>
                      <th className="py-4 px-6 text-[10px] font-display font-bold text-outline uppercase tracking-widest">Rule ID</th>
                      <th className="py-4 px-6 text-[10px] font-display font-bold text-outline uppercase tracking-widest">Protocol</th>
                      <th className="py-4 px-6 text-[10px] font-display font-bold text-outline uppercase tracking-widest">Target</th>
                      <th className="py-4 px-6 text-[10px] font-display font-bold text-outline uppercase tracking-widest">Action</th>
                      <th className="py-4 px-6 text-[10px] font-display font-bold text-outline uppercase tracking-widest text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 font-mono text-xs">
                    {rules.length === 0 ? (
                      <tr><td colSpan={5} className="py-8 text-center text-outline">No rules configured. Add your first rule above.</td></tr>
                    ) : rules.map((rule) => (
                      <tr key={rule.rule_id}
                        className={cn('transition-colors group', rule.enabled ? 'bg-transparent hover:bg-white/[0.03]' : 'bg-black opacity-50')}>
                        <td className="py-5 px-6 font-bold text-white">#{rule.rule_id}</td>
                        <td className="py-5 px-6 text-outline">{rule.protocol}</td>
                        <td className="py-5 px-6 text-outline">{rule.target}</td>
                        <td className="py-5 px-6">
                          <span className={cn('font-bold',
                            rule.action === 'DROP' || rule.action === 'REJECT' ? 'text-on-surface' :
                            rule.action === 'ACCEPT' ? 'text-white' : 'text-outline')}>
                            {rule.action}
                          </span>
                        </td>
                        <td className="py-5 px-6">
                          <div className="flex justify-end items-center gap-3">
                            <button onClick={() => handleToggle(rule.rule_id)}
                              className={cn('w-10 h-5 rounded-full relative transition-all duration-300',
                                rule.enabled ? 'bg-white/20 border border-white' : 'bg-white/5 border border-white/10')}>
                              <div className={cn('absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full transition-all duration-300',
                                rule.enabled ? 'translate-x-5 bg-white glow-white' : 'translate-x-0 bg-outline')} />
                            </button>
                            <button onClick={() => handleDelete(rule.rule_id)}
                              className="text-outline hover:text-white transition-colors opacity-0 group-hover:opacity-100">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>

          {/* System Metrics */}
          <div className="grid grid-cols-3 gap-6">
            <div className="glass-panel rounded-xl p-5 flex items-center justify-between group hover:border-white/20 transition-all border border-white/10">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-surface-container-highest border border-white/10 flex items-center justify-center">
                  <Cpu className="w-5 h-5 text-outline" />
                </div>
                <div>
                  <h4 className="text-[9px] font-display font-bold text-outline uppercase tracking-widest">CPU Usage</h4>
                  <div className="flex items-baseline gap-1 mt-1">
                    <span className="font-mono text-xl text-white font-bold tracking-tight">{metrics?.cpu_percent ?? '—'}</span>
                    <span className="text-[9px] font-mono text-outline uppercase">%</span>
                  </div>
                </div>
              </div>
              {metrics && (
                <div className="w-16 h-1.5 bg-black rounded-full overflow-hidden border border-white/5">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${metrics.cpu_percent}%` }}
                    className="h-full bg-gradient-to-r from-white/40 to-white glow-white rounded-full" />
                </div>
              )}
            </div>

            <div className="glass-panel rounded-xl p-5 flex items-center justify-between group hover:border-white/20 transition-all border border-white/10">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-surface-container-highest border border-white/10 flex items-center justify-center">
                  <Activity className="w-5 h-5 text-outline" />
                </div>
                <div>
                  <h4 className="text-[9px] font-display font-bold text-outline uppercase tracking-widest">RAM Usage</h4>
                  <div className="flex items-baseline gap-1 mt-1">
                    <span className="font-mono text-xl text-white font-bold tracking-tight">{metrics?.memory.used_gb ?? '—'}</span>
                    <span className="text-[9px] font-mono text-outline uppercase">/ {metrics?.memory.total_gb ?? '—'} GB</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="glass-panel rounded-xl p-5 flex items-center justify-between group hover:border-white/20 transition-all border border-white/10">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-surface-container-highest border border-white/10 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-outline" />
                </div>
                <div>
                  <h4 className="text-[9px] font-display font-bold text-outline uppercase tracking-widest">LLM Engine</h4>
                  <div className="flex items-baseline gap-1 mt-1">
                    <span className="font-mono text-xl text-white font-bold tracking-tight">
                      {metrics?.llm_latency_ms ?? '—'}
                    </span>
                    <span className="text-[9px] font-mono text-outline uppercase">ms/req</span>
                  </div>
                </div>
              </div>
              <span className="text-[9px] font-display font-bold text-white bg-white/10 px-2 py-1 rounded border border-white/30 tracking-[0.2em] uppercase ring-1 ring-white/10">Idle</span>
            </div>
          </div>
        </div>

        {/* Side Panel */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-8">
          {/* System Policy */}
          <section className="glass-panel-heavy rounded-2xl p-6 relative group overflow-hidden border border-white/10">
            <div className="absolute inset-0 bg-gradient-to-br from-white/[0.03] to-transparent pointer-events-none" />
            <h3 className="text-xl font-bold text-white flex items-center gap-3 mb-2 relative z-10">
              <Gavel className="w-5 h-5" /> System Policy
            </h3>
            <p className="text-xs text-outline mb-6 relative z-10 leading-relaxed">
              Determines appliance response to detected high-confidence threats.
            </p>
            <div className="void-card rounded-xl p-2 flex flex-col gap-2 relative z-10 border border-white/10">
              <button onClick={() => handlePolicyChange(true)}
                className={cn('w-full flex items-center justify-between p-4 rounded-lg border transition-all duration-300',
                  autoQuarantine ? 'bg-white/10 border-white text-white glow-white' : 'bg-surface-container-high/40 border-white/5 text-outline hover:border-white/20')}>
                <div className="flex items-center gap-3">
                  <div className={cn('w-4 h-4 rounded-full border flex items-center justify-center', autoQuarantine ? 'border-white' : 'border-outline')}>
                    {autoQuarantine && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                  <span className="text-sm font-bold">Auto-Quarantine</span>
                </div>
                <Zap className={cn('w-4 h-4', autoQuarantine ? 'text-white' : 'text-outline/40')} />
              </button>
              <button onClick={() => handlePolicyChange(false)}
                className={cn('w-full flex items-center justify-between p-4 rounded-lg border transition-all duration-300',
                  !autoQuarantine ? 'bg-white/10 border-white text-white glow-white' : 'bg-surface-container-high/20 border-white/5 text-outline hover:border-white/20')}>
                <div className="flex items-center gap-3">
                  <div className={cn('w-4 h-4 rounded-full border flex items-center justify-center', !autoQuarantine ? 'border-white' : 'border-outline')}>
                    {!autoQuarantine && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                  <span className="text-sm font-bold">Manual Approval</span>
                </div>
                <Lock className={cn('w-4 h-4', !autoQuarantine ? 'text-white' : 'text-outline/40')} />
              </button>
            </div>
            <div className="mt-4 flex items-center gap-2 text-white font-display font-bold text-[10px] uppercase tracking-[0.2em] relative z-10" style={{ opacity: autoQuarantine ? 1 : 0.4 }}>
              <ShieldAlert className="w-3.5 h-3.5" /> Auto-Quarantine Active
            </div>
          </section>

          {/* Deception Engine */}
          <section className="glass-panel rounded-2xl p-6 flex flex-col flex-1 border border-white/10">
            <h3 className="text-xl font-bold text-white flex items-center gap-3 mb-6">
              <Network className="w-5 h-5 text-outline" /> Deception Engine
            </h3>
            <div className="space-y-4">
              {honeypots ? (
                <>
                  <div className="void-card p-4 rounded-xl relative overflow-hidden border-l-2 border-l-white/60">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h4 className="text-sm font-bold text-white">{honeypots.cowrie.name}</h4>
                        <p className="text-[10px] font-mono text-outline uppercase mt-1">vIP: {honeypots.cowrie.ip}</p>
                      </div>
                      <span className="text-[9px] font-display font-bold bg-white/10 text-white px-2 py-1 rounded border border-white/20 uppercase">{honeypots.cowrie.status}</span>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="flex flex-col">
                        <span className="text-[9px] font-display font-bold text-outline uppercase tracking-wider mb-1">Sessions</span>
                        <span className="text-xl font-mono font-bold text-white/60">{honeypots.cowrie.total_sessions}</span>
                      </div>
                      <div className="h-8 w-px bg-white/10 self-end mb-1" />
                      <div className="flex flex-col">
                        <span className="text-[9px] font-display font-bold text-outline uppercase tracking-wider mb-1">Creds Logged</span>
                        <span className="text-xl font-mono font-bold text-white">{honeypots.cowrie.successful_logins + honeypots.cowrie.total_sessions}</span>
                      </div>
                    </div>
                  </div>
                  <div className="void-card p-4 rounded-xl relative overflow-hidden border-l-2 border-l-white/20">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h4 className="text-sm font-bold text-white">{honeypots.opencanary.name}</h4>
                        <p className="text-[10px] font-mono text-outline uppercase mt-1">vIP: {honeypots.opencanary.ip}</p>
                      </div>
                      <span className="text-[9px] font-display font-bold bg-white/10 text-white px-2 py-1 rounded border border-white/20 uppercase">{honeypots.opencanary.status}</span>
                    </div>
                    <div>
                      <p className="text-[9px] font-display font-bold text-outline uppercase tracking-wider mb-2">Active Services:</p>
                      <div className="flex gap-2">
                        {honeypots.opencanary.services.map(s => (
                          <span key={s} className="bg-white/10 px-2 py-1 rounded border border-white/10 text-[9px] font-mono text-white/70 uppercase">{s}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-outline font-mono text-xs">Honeypot status unavailable</div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
