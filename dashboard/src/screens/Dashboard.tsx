import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'motion/react';
import { AlertCircle, CheckCircle, ShieldAlert, RefreshCw, Wifi, Shield, Router } from 'lucide-react';
import { cn } from '../lib/utils';
import {
  fetchDashboardStats, fetchDevices, createEventSocket,
  DashboardStats, ApiDevice, ActivityItem,
} from '../lib/api';

function timeAgo(iso: string): string {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function networkHealth(stats: DashboardStats | null, devices: ApiDevice[]): number {
  if (!stats || devices.length === 0) return 100;
  const criticalRatio = stats.critical_devices / Math.max(stats.total_devices, 1);
  const threatRatio = Math.min(stats.active_threats / 10, 1);
  return Math.max(0, Math.round(100 - criticalRatio * 40 - threatRatio * 30));
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [devices, setDevices] = useState<ApiDevice[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([fetchDashboardStats(), fetchDevices()]);
      setStats(s);
      setDevices(d);
      setActivity(s.recent_activity);
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadData();
    const ws = createEventSocket((channel, data: any) => {
      if (channel === 'sentinel:threat') {
        setActivity(prev => [{
          id: data.event_id || String(Date.now()),
          type: 'threat',
          message: data.summary || 'Threat detected',
          detail: data.tactic || '',
          severity: data.severity || 0,
          timestamp: data.timestamp || new Date().toISOString(),
        }, ...prev].slice(0, 10));
        setStats(prev => prev ? { ...prev, active_threats: prev.active_threats + 1 } : prev);
      }
    });
    return () => ws.close();
  }, [loadData]);

  const health = networkHealth(stats, devices);
  const circumference = 283;
  const dashOffset = circumference * (1 - health / 100);

  return (
    <div className="p-10 flex flex-col gap-8">
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-3 px-4 py-2 bg-white/5 rounded border border-white/20 glow-white">
          <motion.div
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="w-2 h-2 rounded-full bg-white"
          />
          <span className="text-[11px] font-mono text-white uppercase tracking-widest">System Protected</span>
        </div>
        <button onClick={loadData} className="text-outline hover:text-white transition-colors p-2">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-outline font-mono text-sm animate-pulse">
          Connecting to backend…
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column */}
          <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
            {/* Network Health Gauge */}
            <div className="void-card rounded-xl p-8 flex flex-col items-center justify-center relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent opacity-0 group-hover:opacity-10 transition-opacity" />
              <h2 className="text-[11px] font-display font-bold text-outline uppercase tracking-widest absolute top-6 left-6">Network Health</h2>
              <div className="w-40 h-40 mt-8 relative flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="45" fill="none" stroke="#222" strokeWidth="6" />
                  <motion.circle
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: dashOffset }}
                    transition={{ duration: 2, ease: 'easeOut' }}
                    cx="50" cy="50" r="45" fill="none" stroke="white" strokeWidth="6"
                    strokeDasharray={circumference}
                    className="drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]"
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-3xl font-mono text-white font-bold drop-shadow-[0_0_5px_rgba(255,255,255,0.5)] tracking-tighter">{health}%</span>
                  <span className="text-[10px] font-display font-bold text-outline uppercase tracking-tighter mt-1">
                    {health >= 80 ? 'Optimal' : health >= 60 ? 'Degraded' : 'Critical'}
                  </span>
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-6">
              <div className="glass-panel-heavy rounded-xl p-6 relative overflow-hidden border-2 border-white/40 ring-1 ring-white/10 glow-white">
                <div className="absolute -right-4 -top-4 w-16 h-16 bg-white/20 rounded-full blur-xl" />
                <h2 className="text-[10px] font-display font-bold text-white uppercase tracking-widest mb-2">Active Threats</h2>
                <div className="flex items-end gap-2">
                  <span className="text-4xl font-sans font-extrabold text-white leading-none">
                    {String(stats?.active_threats ?? 0).padStart(2, '0')}
                  </span>
                  <AlertCircle className="w-5 h-5 text-white mb-1" />
                </div>
                <div className="mt-3 flex items-center gap-1 text-white font-mono text-[10px]">
                  <ShieldAlert className="w-3 h-3" />
                  <span>{stats?.critical_devices ?? 0} critical devices</span>
                </div>
              </div>

              <div className="glass-panel rounded-xl p-6 border border-white/10 ring-1 ring-white/5">
                <h2 className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-2">Protected Nodes</h2>
                <div className="flex items-end gap-2">
                  <span className="text-4xl font-sans font-extrabold text-white leading-none tracking-tight">
                    {stats?.total_devices ?? 0}
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-1 text-outline font-mono text-[10px]">
                  <CheckCircle className="w-3 h-3" />
                  <span>{stats?.quarantined ?? 0} quarantined</span>
                </div>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="flex-1 glass-panel rounded-xl flex flex-col overflow-hidden min-h-[300px]">
              <div className="px-5 py-4 border-b border-white/5">
                <h2 className="text-[11px] font-display font-bold text-outline uppercase tracking-widest">Recent Activity</h2>
              </div>
              <div className="flex-1 overflow-y-auto">
                {activity.length === 0 ? (
                  <div className="p-5 text-outline font-mono text-xs">No recent activity</div>
                ) : (
                  activity.map((item) => (
                    <div key={item.id} className="px-5 py-3.5 border-b border-white/5 flex items-start gap-3 hover:bg-white/[0.02] transition-colors">
                      <div className={cn(
                        'w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0',
                        item.severity >= 8 ? 'bg-white glow-white' : item.severity >= 5 ? 'bg-white/60' : 'bg-outline'
                      )} />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-on-surface leading-snug truncate">{item.message}</p>
                        {item.detail && <p className="text-[10px] font-mono text-outline mt-0.5 truncate">{item.detail}</p>}
                      </div>
                      <span className="text-[10px] font-mono text-outline/60 ml-auto flex-shrink-0 mt-0.5">
                        {timeAgo(item.timestamp)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right Column — Network Topology */}
          <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
            <div className="void-card rounded-xl flex flex-col min-h-[500px] p-6 overflow-hidden relative">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-[11px] font-display font-bold text-outline uppercase tracking-widest">Network Topology</h2>
                  <p className="text-[10px] font-mono text-outline/60 mt-1">{devices.length} nodes discovered</p>
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono text-outline">
                  <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-white glow-white" /> Critical</div>
                  <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-white/50" /> High</div>
                  <div className="flex items-center gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-outline" /> Safe</div>
                </div>
              </div>

              <div className="flex-1 relative min-h-[400px]">
                {/* Grid background */}
                <div className="absolute inset-0 pointer-events-none opacity-10"
                  style={{
                    backgroundImage: 'linear-gradient(rgba(255,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.15) 1px, transparent 1px)',
                    backgroundSize: '40px 40px'
                  }}
                />

                {/* SVG connection lines */}
                <svg className="absolute inset-0 w-full h-full z-0">
                  {devices.slice(0, 12).map((_, i) => {
                    const total = Math.min(devices.length, 12);
                    const angle = (i / total) * 2 * Math.PI - Math.PI / 2;
                    const radius = 38;
                    const cx = 50 + radius * Math.cos(angle);
                    const cy = 50 + radius * Math.sin(angle);
                    return (
                      <line key={i}
                        x1="50%" y1="50%"
                        x2={`${cx}%`} y2={`${cy}%`}
                        stroke="white" strokeWidth="1" strokeOpacity="0.1" strokeDasharray="4 4"
                      />
                    );
                  })}
                </svg>

                {/* Central SENTINEL node */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20">
                  <div className="w-16 h-16 rounded-full bg-white/10 border-2 border-white glow-white flex items-center justify-center">
                    <Shield className="w-7 h-7 text-white" />
                  </div>
                  <p className="text-[9px] font-mono text-white text-center mt-1 uppercase tracking-wider">SENTINEL</p>
                </div>

                {/* Device nodes */}
                {devices.slice(0, 12).map((d, i) => {
                  const total = Math.min(devices.length, 12);
                  const angle = (i / total) * 2 * Math.PI - Math.PI / 2;
                  const radius = 38;
                  const cx = 50 + radius * Math.cos(angle);
                  const cy = 50 + radius * Math.sin(angle);
                  const isHigh = d.risk_score >= 7;
                  const isMed = d.risk_score >= 4 && d.risk_score < 7;

                  return (
                    <motion.div
                      key={d.device_id}
                      className="absolute -translate-x-1/2 -translate-y-1/2 z-10 group"
                      style={{ left: `${cx}%`, top: `${cy}%` }}
                      initial={{ opacity: 0, scale: 0 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: i * 0.06 }}
                    >
                      <div
                        className={cn(
                          'w-10 h-10 rounded-lg border flex items-center justify-center',
                          isHigh ? 'bg-white/10 border-white glow-white' : isMed ? 'bg-white/5 border-white/40' : 'bg-black border-white/10'
                        )}
                        title={`${d.ip} — Risk ${d.risk_score.toFixed(1)}`}
                      >
                        <Wifi className={cn('w-4 h-4', isHigh ? 'text-white' : isMed ? 'text-white/60' : 'text-outline')} />
                      </div>
                      <p className="text-[8px] font-mono text-outline text-center mt-1 leading-tight max-w-[60px] truncate">{d.ip}</p>
                    </motion.div>
                  );
                })}

                {devices.length === 0 && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <p className="text-outline font-mono text-xs">No devices discovered yet</p>
                  </div>
                )}
              </div>
            </div>

            {/* High risk device list */}
            <div className="glass-panel rounded-xl p-5">
              <h2 className="text-[11px] font-display font-bold text-outline uppercase tracking-widest mb-3">High Risk Devices</h2>
              {devices.filter(d => d.risk_score >= 7).length === 0 ? (
                <p className="text-outline font-mono text-xs">No high-risk devices</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {devices.filter(d => d.risk_score >= 7).slice(0, 4).map(d => (
                    <div key={d.device_id} className="flex items-center gap-4 py-2 border-b border-white/5 last:border-0">
                      <div className="w-6 h-6 rounded bg-white/10 border border-white/20 flex items-center justify-center flex-shrink-0">
                        <Router className="w-3 h-3 text-white" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-mono text-white truncate">{d.ip}</p>
                        <p className="text-[10px] text-outline truncate">{d.vendor || 'Unknown vendor'} · {d.cve_list.length} CVEs</p>
                      </div>
                      <div className="text-xs font-mono font-bold text-white">{d.risk_score.toFixed(1)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
