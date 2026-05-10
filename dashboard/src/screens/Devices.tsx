import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Monitor, Camera, Laptop, Router, Cpu, Wifi, ShieldAlert, Lock, Unlock, RefreshCw, ChevronDown, ExternalLink } from 'lucide-react';
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

function cvssColor(score: number): string {
  if (score >= 9) return 'text-white';
  if (score >= 7) return 'text-white/80';
  if (score >= 4) return 'text-white/60';
  return 'text-outline';
}

function cvssBg(score: number): string {
  if (score >= 9) return 'bg-white/15 border-white/40';
  if (score >= 7) return 'bg-white/8 border-white/20';
  if (score >= 4) return 'bg-white/5 border-white/10';
  return 'bg-white/[0.02] border-white/5';
}

function cvssLabel(score: number): string {
  if (score >= 9) return 'CRITICAL';
  if (score >= 7) return 'HIGH';
  if (score >= 4) return 'MEDIUM';
  return 'LOW';
}

interface DevicesProps {
  externalFilter?: string;
}

export default function Devices({ externalFilter = '' }: DevicesProps) {
  const [devices, setDevices] = useState<ApiDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (externalFilter.trim()) {
      setFilter(externalFilter);
    }
  }, [externalFilter]);

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

  const handleQuarantine = async (e: React.MouseEvent, deviceId: string) => {
    e.stopPropagation();
    await quarantineDevice(deviceId);
    setDevices(prev => prev.map(d =>
      d.device_id === deviceId ? { ...d, is_quarantined: !d.is_quarantined } : d
    ));
  };

  const toggleExpand = (deviceId: string) => {
    setExpandedId(prev => prev === deviceId ? null : deviceId);
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
          <p className="text-sm text-outline mt-1">Real-time asset discovery and risk analysis · Click a row to expand CVE details</p>
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
        <div className="w-full flex flex-col gap-2">
          <div className="grid grid-cols-[2.5fr_2fr_2fr_1.5fr_1fr_auto] gap-4 px-6 py-3 border-b border-white/5">
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">Asset Identity</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">Network Locator</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest text-center">Risk Vector</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest text-center">Exposure</span>
            <span className="text-[10px] font-display font-bold text-outline uppercase tracking-widest text-right">Action</span>
            <span />
          </div>

          <div className="flex flex-col gap-2">
            {filtered.length === 0 ? (
              <div className="text-center py-16 text-outline font-mono text-sm">
                {devices.length === 0 ? 'No devices discovered yet. Start the capture engine.' : 'No devices match the filter.'}
              </div>
            ) : (
              filtered.map((device, idx) => (
                <DeviceRow
                  key={device.device_id}
                  device={device}
                  index={idx}
                  expanded={expandedId === device.device_id}
                  onToggle={() => toggleExpand(device.device_id)}
                  onQuarantine={handleQuarantine}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const DeviceRow: React.FC<{
  device: ApiDevice;
  index: number;
  expanded: boolean;
  onToggle: () => void;
  onQuarantine: (e: React.MouseEvent, id: string) => void;
}> = ({ device, index, expanded, onToggle, onQuarantine }) => {
  const isHighRisk = device.risk_score >= 7;
  const isMediumRisk = device.risk_score >= 4 && device.risk_score < 7;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className={cn(
        'border rounded-xl overflow-hidden transition-all duration-200',
        expanded ? 'border-white/20' : isHighRisk ? 'border-white/20' : 'border-white/5',
        'bg-white/[0.02] hover:bg-white/[0.04]'
      )}
    >
      {/* Main row — clickable */}
      <div
        className="grid grid-cols-[2.5fr_2fr_2fr_1.5fr_1fr_auto] gap-4 items-center p-3 cursor-pointer relative"
        onClick={onToggle}
      >
        {isHighRisk && <div className="absolute left-0 top-0 bottom-0 w-1 bg-white glow-white rounded-l-xl" />}

        {/* Identity */}
        <div className="flex items-center gap-4 pl-2">
          <div className={cn(
            'w-12 h-12 rounded-lg bg-black border border-white/10 flex items-center justify-center',
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
          <div className={cn(
            'px-2 py-1 rounded flex items-center gap-1.5 min-w-[70px] justify-center border',
            device.cve_list.length > 0 ? 'bg-white/10 border-white/30' : 'bg-black border-white/10'
          )}>
            <ShieldAlert className={cn('w-3 h-3', device.cve_list.length > 0 ? 'text-white' : 'text-outline')} />
            <span className={cn('text-[10px] font-mono', device.cve_list.length > 0 ? 'text-white font-bold' : 'text-white/70')}>
              {device.cve_list.length} CVEs
            </span>
          </div>
        </div>

        {/* Action */}
        <div className="flex justify-end pr-2">
          <button
            onClick={(e) => onQuarantine(e, device.device_id)}
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

        {/* Expand chevron */}
        <div className="flex items-center pr-2">
          <ChevronDown className={cn('w-4 h-4 text-outline transition-transform duration-200', expanded && 'rotate-180')} />
        </div>
      </div>

      {/* Expanded detail panel */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/5 p-6 bg-black/40 flex flex-col gap-6">

              {/* Open Ports */}
              {device.open_ports.length > 0 && (
                <div>
                  <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-3">
                    Open Ports ({device.open_ports.length})
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {device.open_ports.map(port => (
                      <span
                        key={port}
                        className="px-2 py-1 bg-white/5 border border-white/10 rounded font-mono text-xs text-white/80"
                      >
                        {port}
                        <span className="text-outline ml-1">{portLabel(port)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* CVE List */}
              {device.cve_list.length > 0 ? (
                <div>
                  <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-3">
                    Known Vulnerabilities — NVD / NIST ({device.cve_list.length})
                  </p>
                  <div className="flex flex-col gap-2">
                    {device.cve_list.map((cve: any) => {
                      const score = cve.score ?? cve.cvss_score ?? 0;
                      const desc = cve.desc ?? cve.description ?? 'No description available.';
                      return (
                        <div
                          key={cve.cve_id}
                          className={cn('rounded-lg border p-4 flex gap-4 items-start', cvssBg(score))}
                        >
                          {/* CVSS score badge */}
                          <div className="flex flex-col items-center flex-shrink-0 w-16">
                            <span className={cn('text-lg font-mono font-bold leading-none', cvssColor(score))}>
                              {score.toFixed(1)}
                            </span>
                            <span className={cn('text-[9px] font-display font-bold uppercase tracking-widest mt-1', cvssColor(score))}>
                              {cvssLabel(score)}
                            </span>
                          </div>

                          {/* CVE info */}
                          <div className="flex flex-col gap-1 flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-mono font-bold text-white">{cve.cve_id}</span>
                              <a
                                href={`https://nvd.nist.gov/vuln/detail/${cve.cve_id}`}
                                target="_blank"
                                rel="noreferrer"
                                onClick={e => e.stopPropagation()}
                                className="text-outline hover:text-white transition-colors"
                                title="View on NVD"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                              </a>
                            </div>
                            <p className="text-xs text-white/60 leading-relaxed">{desc}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div>
                  <p className="text-[10px] font-display font-bold text-outline uppercase tracking-widest mb-3">Known Vulnerabilities</p>
                  <p className="text-sm text-outline font-mono">No CVEs found for this device. {device.vendor ? `Vendor: ${device.vendor}` : 'Vendor unknown — CVE lookup requires vendor identification.'}</p>
                </div>
              )}

              {/* Last seen */}
              <div className="pt-2 border-t border-white/5 flex justify-between items-center">
                <span className="text-[10px] font-mono text-outline uppercase tracking-wider">
                  Last seen: {device.last_seen ? new Date(device.last_seen).toUTCString() : '—'}
                </span>
                <span className="text-[10px] font-mono text-outline uppercase tracking-wider">
                  Device ID: {device.device_id}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

function portLabel(port: number): string {
  const known: Record<number, string> = {
    21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
    80: 'HTTP', 110: 'POP3', 143: 'IMAP', 443: 'HTTPS', 445: 'SMB',
    554: 'RTSP', 993: 'IMAPS', 995: 'POP3S', 1883: 'MQTT', 3389: 'RDP',
    5900: 'VNC', 8080: 'HTTP-Alt', 8443: 'HTTPS-Alt', 8554: 'RTSP-Alt',
  };
  return known[port] ? `(${known[port]})` : '';
}
