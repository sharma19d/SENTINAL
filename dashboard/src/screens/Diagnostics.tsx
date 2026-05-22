import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCw, ServerCrash, Stethoscope } from 'lucide-react';
import { cn } from '../lib/utils';
import { ApiDiagnostics, fetchDiagnostics } from '../lib/api';

function statusBadge(status: ApiDiagnostics['overall_status']) {
  if (status === 'healthy') return 'Healthy';
  if (status === 'degraded') return 'Degraded';
  return 'Critical';
}

export default function Diagnostics() {
  const [data, setData] = useState<ApiDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);

  const run = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchDiagnostics());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { run(); }, [run]);

  return (
    <div className="p-4 md:p-10 flex flex-col gap-6 md:gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">Diagnostics</h2>
          <p className="text-sm text-outline mt-1">Live backend and service health checks for SENTINEL.</p>
        </div>
        <button
          onClick={run}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white text-black text-xs font-display font-bold uppercase tracking-wider hover:bg-white/90 transition-all"
        >
          <RefreshCw className="w-4 h-4" />
          Run Diagnostics
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-56 text-outline font-mono text-sm animate-pulse">
          Running diagnostics…
        </div>
      ) : !data ? (
        <div className="glass-panel rounded-xl p-8 flex items-center gap-3 text-outline">
          <ServerCrash className="w-5 h-5" />
          Diagnostics unavailable. Backend might be offline.
        </div>
      ) : (
        <>
          <section className="glass-panel rounded-xl p-6 border border-white/10">
            <div className="flex flex-wrap items-center gap-3">
              <Stethoscope className="w-5 h-5 text-white" />
              <span className="text-sm font-display font-bold uppercase tracking-widest text-outline">Overall Status</span>
              <span
                className={cn(
                  'text-xs font-mono uppercase px-2.5 py-1 rounded border',
                  data.overall_status === 'healthy'
                    ? 'bg-white/10 text-white border-white/40'
                    : data.overall_status === 'degraded'
                    ? 'bg-white/5 text-outline border-white/20'
                    : 'bg-black text-white border-white'
                )}
              >
                {statusBadge(data.overall_status)}
              </span>
              <span className="text-[11px] font-mono text-outline">Last run: {new Date(data.generated_at).toLocaleString()}</span>
            </div>
          </section>

          <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
            {data.checks.map((check) => (
              <div key={check.name} className="void-card rounded-xl p-5 border border-white/10">
                <div className="flex items-center justify-between">
                  <h3 className="text-[11px] font-display font-bold text-outline uppercase tracking-widest">{check.name}</h3>
                  {check.status === 'healthy' ? (
                    <CheckCircle2 className="w-4 h-4 text-white" />
                  ) : check.status === 'degraded' ? (
                    <AlertTriangle className="w-4 h-4 text-outline" />
                  ) : (
                    <ServerCrash className="w-4 h-4 text-white" />
                  )}
                </div>
                <p className="text-sm text-on-surface mt-2 leading-relaxed">{check.detail}</p>
                <p className="text-[10px] font-mono text-outline mt-4">{new Date(check.checked_at).toLocaleTimeString()}</p>
              </div>
            ))}
          </section>

          <section className="glass-panel rounded-xl p-6 border border-white/10">
            <h3 className="text-[11px] font-display font-bold text-outline uppercase tracking-widest mb-4">System Snapshot</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs font-mono">
              <div className="bg-black/50 border border-white/10 rounded p-3">
                <p className="text-outline">CPU</p>
                <p className="text-white mt-1">{data.system_metrics.cpu_percent}%</p>
              </div>
              <div className="bg-black/50 border border-white/10 rounded p-3">
                <p className="text-outline">Memory</p>
                <p className="text-white mt-1">{data.system_metrics.memory.used_gb} / {data.system_metrics.memory.total_gb} GB</p>
              </div>
              <div className="bg-black/50 border border-white/10 rounded p-3">
                <p className="text-outline">Interface</p>
                <p className="text-white mt-1">{data.context.capture_interface}</p>
              </div>
              <div className="bg-black/50 border border-white/10 rounded p-3">
                <p className="text-outline">Subnets</p>
                <p className="text-white mt-1">{data.context.monitored_subnets}</p>
              </div>
              <div className="bg-black/50 border border-white/10 rounded p-3">
                <p className="text-outline">Devices</p>
                <p className="text-white mt-1">{data.context.total_devices}</p>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
