import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'motion/react';
import { Monitor, Camera, Laptop, Router, Cpu, Wifi, ShieldAlert, Lock, Unlock, RefreshCw } from 'lucide-react';
import { cn } from '../lib/utils';
import { fetchDevices, quarantineDevice, createEventSocket, ApiDevice } from '../lib/api';

function getDeviceIcon(device: ApiDevice) {
  const v = (device.vendor || '').toLowerCase();
  const os = (device.os_guess || '').toLowerCase();
  if (v.includes('hikvision') || v.includes('camera')) return <Camera className="w-5 h-5" />;
  if (v.includes('apple') || os.includes('macos')) return <Laptop className="w-5 h-5" />;
  if (v.includes('cisco') || v.includes('tp-link') || v.includes('netgear')) return <Router className="w-5 h-5" />;
  if (v.includes('raspberry') || v.includes('arduino')) return <Cpu className="w-5 h-5" />;
  if (v.includes('samsung') || os.includes('rtos')) return <Monitor className="w-5 h-5" />;
  return <Wifi className="w-5 h-5" />;
}

function deviceLabel(device: ApiDevice): string {
  if (device.vendor) return device.vendor.split(' ')[0];
  if (device.os_guess) return device.os_guess;
  return device.mac.slice(0, 8);
}

export default function Devices() {
  const [devices, setDevices] = useState<ApiDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const loadDevices = useCallback(async () => {
    try {
      const d = await fetchDevices();
      setDevices(d);
    } catch { /* backend offline */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadDevices();
    const ws = createEventSocket((channel, data: any) => {
      if (channel === 'sentinel:anomaly' || channel === 'sentinel:actions') {
        loadDevices();
      }
    });
    return () => ws.close();
  }, [loadDevices]);

  const handleQuarantine = async (deviceId: string) => {
    await quarantineDevice(deviceId);
    setDevices(prev => prev.map(d =>
      d.device_id === deviceId ? { ...d, is_quarantined: !d.is_quarantined } : d
    ));
  };

  const filtered = devices.filter(d =>
    !filter || (d.ip || '').includes(filter) || (d.vendor || '').toLowerCase().includes(filter.toLowerCase()) || (d.mac || '').includes(filter)
  );

  const critical = devices.filter(d => d.risk_score >= 7).length;

  return (
    <div className="p-10 flex flex-col gap-8">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">Device Registry</h2>
          <p className="text-sm text-outline mt-1">Real-time asset discovery and risk analysis</p>
        </div>
        <div className="flex gap-4 items-center">
          <input
            type="text"
            placeholder="Filter by IP, vendor, MAC…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-sm font-mono text-white placeholder:text-outline focus:outline-none focus:border-white/30 w-56"
          />
          <div className="void-card rounded-lg px-6 py-4 flex flex-col">
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-1">Total Devices</span>
            <span className="text-2xl font-mono text-white font-bold leading-none">{devices.length}</span>
          </div>
          <div className="void-card rounded-lg px-6 py-4 flex flex-col border-white/30 glow-white">
            <span className="text-[10px] font-display font-bold text-white uppercase tracking-widest mb-1">Critical Risk</span>
            <span className="text-2xl font-mono text-white font-bold leading-none">{critical}</span>
          </div>
          <button onClick={loadDevices} className="text-outline hover:text-white transition-colors p-2">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-outline font-mono text-sm animate-pulse">
          Loading devices…
        </div>
      ) : (
        <div className="w-full flex flex-col">
          <div className="grid grid-cols-[2.5fr_2fr_2fr_1.5fr_1fr] gap-4 px-6 py-3 border-b border-white/5 mb-3">
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">Asset Identity</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">Network Locator</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest text-center">Risk Vector</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest text-center">Exposure</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest text-right">Action</span>
          </div>

          <div className="flex flex-col gap-3">
            {filtered.length === 0 ? (
              <div className="text-center py-16 text-outline font-mono text-sm">
                {devices.length === 0 ? 'No devices discovered yet. Start the capture engine.' : 'No devices match the filter.'}
              </div>
            ) : (
              filtered.map((device, idx) => (
                <DeviceRow key={device.device_id} device={device} index={idx} onQuarantine={handleQuarantine} />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const DeviceRow: React.FC<{ device: ApiDevice; index: number; onQuarantine: (id: string) => void }> = ({ device, index, onQuarantine }) => {
  const isHighRisk = device.risk_score >= 7;
  const isMediumRisk = device.risk_score >= 4 && device.risk_score < 7;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className={cn(
        'grid grid-cols-[2.5fr_2fr_2fr_1.5fr_1fr] gap-4 items-center bg-white/[0.02] border border-white/5 rounded-xl p-3 hover:bg-white/[0.05] transition-all relative overflow-hidden group',
        isHighRisk && 'border-white/20'
      )}
    >
      {isHighRisk && <div className="absolute left-0 top-0 bottom-0 w-1 bg-white glow-white" />}

      {/* Identity */}
      <div className="flex items-center gap-4 pl-2">
        <div className={cn(
          'w-12 h-12 rounded-lg bg-black border border-white/10 flex items-center justify-center transition-all group-hover:border-white/30',
          isHighRisk ? 'text-white' : 'text-outline'
        )}>
          {getDeviceIcon(device)}
        </div>
        <div className="flex flex-col min-w-0">
          <span className={cn('text-sm font-bold truncate', isHighRisk ? 'text-white' : 'text-on-surface')}>
            {deviceLabel(device)}
          </span>
          <span className="text-[10px] font-mono text-outline uppercase truncate tracking-tight">
            {device.os_guess || 'Unknown OS'}
          </span>
        </div>
      </div>

      {/* Network */}
      <div className="flex flex-col">
        <span className="text-sm font-mono text-on-surface leading-tight">{device.ip || '—'}</span>
        <span className="text-[10px] font-mono text-outline uppercase tracking-tighter">{device.mac}</span>
      </div>

      {/* Risk Vector */}
      <div className="flex items-center gap-4 px-4">
        <div className={cn(
          'bg-black border border-white/10 w-10 h-10 flex flex-shrink-0 items-center justify-center rounded font-mono font-bold text-sm',
          isHighRisk && 'text-white',
          isMediumRisk && 'text-white/70',
          !isHighRisk && !isMediumRisk && 'text-outline'
        )}>
          {device.risk_score.toFixed(1)}
        </div>
        <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${device.risk_score * 10}%` }}
            transition={{ duration: 1, ease: 'easeOut' }}
            className={cn('h-full rounded-full', isHighRisk ? 'bg-white glow-white' : 'bg-outline')}
          />
        </div>
      </div>

      {/* Exposure */}
      <div className="flex justify-center gap-2">
        <div className="px-2 py-1 bg-black border border-white/10 rounded flex items-center gap-1.5 min-w-[70px] justify-center">
          <Lock className="w-3 h-3 text-outline" />
          <span className="text-[10px] font-mono text-white/70">{device.open_ports.length} Ports</span>
        </div>
        <div className="px-2 py-1 bg-black border border-white/10 rounded flex items-center gap-1.5 min-w-[70px] justify-center">
          <ShieldAlert className="w-3 h-3 text-outline" />
          <span className="text-[10px] font-mono text-white/70">{device.cve_list.length} CVEs</span>
        </div>
      </div>

      {/* Action */}
      <div className="flex justify-end pr-2">
        <button
          onClick={() => onQuarantine(device.device_id)}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded text-[10px] font-display font-bold uppercase tracking-wider transition-all',
            device.is_quarantined
              ? 'bg-white text-black border border-white'
              : 'bg-transparent border border-white/20 text-outline hover:text-white hover:border-white'
          )}
        >
          {device.is_quarantined ? <Lock className="w-4 h-4 fill-current" /> : <Unlock className="w-4 h-4" />}
          {device.is_quarantined ? 'Quarantined' : 'Quarantine'}
        </button>
      </div>
    </motion.div>
  );
};
