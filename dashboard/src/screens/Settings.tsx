import React, { useEffect, useState, useCallback } from 'react';
import { Brain, Bell, Wifi, Info, Save, RefreshCw, CheckCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { fetchSettings, updateSettings, SentinelSettings } from '../lib/api';

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="glass-panel rounded-2xl p-6 flex flex-col gap-5 border border-white/10">
      <h3 className="text-lg font-bold text-white flex items-center gap-3">
        {icon}{title}
      </h3>
      {children}
    </section>
  );
}

function FieldRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-8 py-3 border-b border-white/5 last:border-0">
      <div className="flex-1">
        <p className="text-sm font-medium text-on-surface">{label}</p>
        {description && <p className="text-[11px] text-outline mt-0.5 leading-relaxed">{description}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!value)}
      className={cn('w-10 h-5 rounded-full relative transition-all duration-300',
        value ? 'bg-white/20 border border-white' : 'bg-white/5 border border-white/10')}>
      <div className={cn('absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full transition-all duration-300',
        value ? 'translate-x-5 bg-white glow-white' : 'translate-x-0 bg-outline')} />
    </button>
  );
}

function Slider({ value, min, max, step = 0.01, onChange, display }: {
  value: number; min: number; max: number; step?: number; onChange: (v: number) => void; display?: (v: number) => string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-sm text-white w-12 text-right">{display ? display(value) : value}</span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-32 accent-white" />
    </div>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState<SentinelSettings | null>(null);
  const [draft, setDraft] = useState<Partial<SentinelSettings>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState(false);
  const [saved, setSaved] = useState(false);

  const loadSettings = useCallback(async () => {
    setRefreshing(true);
    setRefreshError(false);
    try {
      const s = await fetchSettings();
      setSettings(s);
      setDraft({});
    } catch {
      setRefreshError(true);
      setTimeout(() => setRefreshError(false), 3000);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  const set = (key: keyof SentinelSettings, value: any) => {
    setDraft(prev => ({ ...prev, [key]: value }));
    setSettings(prev => prev ? { ...prev, [key]: value } : prev);
  };

  const handleSave = async () => {
    if (!Object.keys(draft).length) return;
    await updateSettings(draft);
    setSaved(true);
    setDraft({});
    setTimeout(() => setSaved(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-outline font-mono text-sm animate-pulse">
        Loading settings…
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex items-center justify-center h-64 text-outline font-mono text-sm">
        Backend offline. Settings unavailable.
      </div>
    );
  }

  const hasDraft = Object.keys(draft).length > 0;

  return (
    <div className="p-4 md:p-10 flex flex-col gap-6 md:gap-8 max-w-4xl mx-auto w-full">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">Settings</h2>
          <p className="text-sm text-outline mt-1">Configure SENTINEL AI thresholds, alerts, and network parameters</p>
        </div>
        <div className="flex items-center gap-3">
          {refreshError && (
            <span className="text-[10px] font-mono text-white/70 uppercase tracking-wide">Refresh failed</span>
          )}
          <button
            onClick={loadSettings}
            disabled={refreshing}
            className="text-outline hover:text-white transition-colors p-2 disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
          </button>
          <button
            onClick={handleSave}
            disabled={!hasDraft}
            className={cn(
              'flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-display font-bold uppercase tracking-wider transition-all',
              hasDraft
                ? 'bg-white text-black hover:bg-white/90'
                : saved
                ? 'bg-white/10 text-white border border-white/20'
                : 'bg-white/5 text-outline border border-white/10 cursor-not-allowed'
            )}
          >
            {saved ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {saved ? 'Saved' : 'Save Changes'}
          </button>
        </div>
      </div>

      {/* AI Model Thresholds */}
      <Section title="AI Model Thresholds" icon={<Brain className="w-5 h-5 text-outline" />}>
        <FieldRow
          label="Anomaly Detection Threshold"
          description="LSTM anomaly score above this value triggers an alert. Higher = fewer false positives."
        >
          <Slider value={settings.anomaly_threshold} min={0.5} max={0.99} step={0.01}
            onChange={v => set('anomaly_threshold', v)}
            display={v => `${(v * 100).toFixed(0)}%`} />
        </FieldRow>
        <FieldRow
          label="Threat Confidence Cutoff"
          description="Minimum confidence for the LLM to classify an event as a threat."
        >
          <Slider value={settings.threat_confidence_cutoff} min={0.5} max={0.99} step={0.01}
            onChange={v => set('threat_confidence_cutoff', v)}
            display={v => `${(v * 100).toFixed(0)}%`} />
        </FieldRow>
        <FieldRow
          label="Auto-Quarantine"
          description="Automatically isolate devices when a critical threat is detected (severity ≥ 9)."
        >
          <Toggle value={settings.auto_quarantine} onChange={v => set('auto_quarantine', v)} />
        </FieldRow>
        <FieldRow
          label="Auto-Honeypot Redirect"
          description="Redirect suspicious devices to the honeypot network automatically."
        >
          <Toggle value={settings.auto_honeypot} onChange={v => set('auto_honeypot', v)} />
        </FieldRow>
      </Section>

      {/* Alert Configuration */}
      <Section title="Alert Configuration" icon={<Bell className="w-5 h-5 text-outline" />}>
        <FieldRow
          label="Alerts Enabled"
          description="Enable or disable the alerting subsystem entirely."
        >
          <Toggle value={settings.alert_enabled} onChange={v => set('alert_enabled', v)} />
        </FieldRow>
        <FieldRow
          label="Minimum Severity to Alert"
          description={`Only threats with severity ≥ ${settings.min_severity_alert} will trigger notifications.`}
        >
          <Slider value={settings.min_severity_alert} min={1} max={10} step={1}
            onChange={v => set('min_severity_alert', v)}
            display={v => `${v}/10`} />
        </FieldRow>
      </Section>

      {/* Network Configuration */}
      <Section title="Network Configuration" icon={<Wifi className="w-5 h-5 text-outline" />}>
        <FieldRow
          label="Capture Interface"
          description="Network interface used for packet capture."
        >
          <input value={settings.capture_interface}
            onChange={e => set('capture_interface', e.target.value)}
            className="bg-black border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-white/30 w-32" />
        </FieldRow>
        <FieldRow
          label="Monitored Subnets"
          description="Comma-separated CIDR ranges to monitor."
        >
          <input value={settings.monitored_subnets}
            onChange={e => set('monitored_subnets', e.target.value)}
            className="bg-black border border-white/10 rounded px-3 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-white/30 w-48" />
        </FieldRow>
        <FieldRow
          label="Scan Interval (minutes)"
          description="How often the active scanner runs."
        >
          <Slider value={settings.scan_interval_minutes} min={1} max={60} step={1}
            onChange={v => set('scan_interval_minutes', v)}
            display={v => `${v}m`} />
        </FieldRow>
      </Section>

      {/* System Info */}
      <Section title="System Information" icon={<Info className="w-5 h-5 text-outline" />}>
        {[
          { label: 'Version', value: settings.system.version },
          { label: 'Database', value: settings.system.db_url },
          { label: 'Redis', value: `${settings.system.redis_host}:${settings.system.redis_port}` },
          { label: 'Ollama URL', value: settings.system.ollama_base_url },
          { label: 'LLM Model', value: settings.system.llm_model },
        ].map(({ label, value }) => (
          <React.Fragment key={label}>
            <FieldRow label={label}>
              <span className="font-mono text-xs text-outline">{value}</span>
            </FieldRow>
          </React.Fragment>
        ))}
      </Section>
    </div>
  );
}
