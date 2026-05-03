'use client';

import { useEffect, useState, useMemo } from 'react';
import { useWebsocket } from '../hooks/useWebsocket';
import RiskGraph from '../components/RiskGraph';
import { 
  Shield, AlertTriangle, Cpu, Activity, Globe, Search, Bell, Settings, 
  ChevronRight, Zap, X, ShieldAlert, Bug, Fingerprint, Lock
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function Dashboard() {
  const [devices, setDevices] = useState<any[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<any>(null);
  const [selectedThreat, setSelectedThreat] = useState<any>(null);
  const [pendingAction, setPendingAction] = useState<any>(null);
  const [ribbonExpanded, setRibbonExpanded] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  
  const { events, isConnected } = useWebsocket('ws://localhost:8000/ws/events');

  // Fetch initial data
  useEffect(() => {
    setIsMounted(true);
    const fetchData = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/devices');
        const data = await res.json();
        setDevices(data);
      } catch (err) {
        console.error('Fetch error:', err);
      }
    };
    fetchData();
  }, []);

  // Update devices/threats from websocket events
  useEffect(() => {
    if (events.length > 0) {
      const lastEvent = events[0];
      
      // Expand ribbon on new threat
      if (lastEvent.channel === 'sentinel:threat' || lastEvent.channel === 'sentinel:anomaly') {
        setRibbonExpanded(true);
      }

      // Handle security gate
      if (lastEvent.channel === 'sentinel:alerts' && lastEvent.data.status === 'pending_confirmation') {
        setPendingAction(lastEvent.data);
      }
    }
  }, [events]);

  const activeThreats = useMemo(() => 
    events.filter(e => e.channel === 'sentinel:threat'), 
  [events]);

  const authorizeQuarantine = async () => {
    if (!pendingAction) return;
    try {
      await fetch(`http://localhost:8000/api/actions/quarantine/${pendingAction.device_id}`, { method: 'POST' });
      setPendingAction(null);
      // Update local state immediately
      setDevices(prev => prev.map(d => d.device_id === pendingAction.device_id ? { ...d, is_quarantined: true } : d));
    } catch (err) {
      console.error('Action failed:', err);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-bg-void overflow-hidden selection:bg-amber-dim selection:text-amber-bright">
      
      {/* ── COMMAND BAR (Fixed Top) ────────────────────────────── */}
      <nav className="h-14 border-b border-border-subtle bg-bg-surface/80 backdrop-blur-xl flex items-center justify-between px-6 z-50 shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex flex-col leading-tight">
            <div className="font-display font-extrabold text-lg tracking-tighter flex items-center gap-2">
              <Shield className="text-amber-primary w-5 h-5" fill="currentColor" fillOpacity={0.1} />
              SENTINEL
            </div>
            <div className="font-mono text-[9px] text-text-muted tracking-widest flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-safe animate-pulse' : 'bg-critical'}`} />
              SYSTEM {isConnected ? 'ACTIVE' : 'OFFLINE'}
            </div>
          </div>
        </div>

        <div className="flex-1 max-w-xl px-12 relative group">
          <Search className="absolute left-16 top-1/2 -translate-y-1/2 text-text-muted w-4 h-4 group-focus-within:text-amber-primary transition-colors" />
          <input 
            type="text" 
            placeholder="Search device, IP, CVE, technique..." 
            className="w-full bg-bg-base border border-border-default rounded-full py-1.5 pl-10 pr-4 text-xs font-body focus:outline-none focus:border-amber-primary/50 focus:ring-4 focus:ring-amber-glow transition-all"
          />
          <div className="absolute right-16 top-1/2 -translate-y-1/2 px-1.5 py-0.5 border border-border-subtle rounded text-[9px] text-text-muted font-mono bg-bg-surface">
            CMD+K
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 bg-bg-base px-4 py-1.5 rounded-full border border-border-subtle">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-safe" />
              <span className="text-[10px] font-mono font-bold text-text-secondary">{devices.length} DEVICES</span>
            </div>
            <div className="w-px h-3 bg-border-subtle" />
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${activeThreats.length > 0 ? 'bg-critical animate-ping' : 'bg-text-muted'}`} />
              <span className="text-[10px] font-mono font-bold text-text-secondary">{activeThreats.length} ALERTS</span>
            </div>
          </div>
          <button className="text-text-secondary hover:text-text-primary transition-colors relative">
            <Bell size={18} />
            {activeThreats.length > 0 && <div className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-critical rounded-full border-2 border-bg-surface" />}
          </button>
          <Settings size={18} className="text-text-secondary hover:text-text-primary cursor-pointer transition-colors" />
        </div>
      </nav>

      {/* ── THREAT RIBBON ─────────────────────────────────────── */}
      <div 
        className={`bg-bg-base border-b border-border-subtle transition-all duration-500 overflow-hidden relative group cursor-pointer ${ribbonExpanded ? 'h-12' : 'h-1'}`}
        onClick={() => setRibbonExpanded(!ribbonExpanded)}
      >
        {!ribbonExpanded && <div className={`absolute inset-0 transition-colors ${activeThreats.length > 0 ? 'bg-amber-primary/50 animate-pulse' : 'bg-safe/20'}`} />}
        
        <div className="h-full flex items-center px-6 gap-8 no-scrollbar overflow-x-auto whitespace-nowrap">
           {activeThreats.length === 0 ? (
             <span className="text-[10px] font-mono text-text-muted tracking-widest uppercase italic">All Systems Clear · Passive Monitoring Active</span>
           ) : (
             activeThreats.map((t, i) => (
               <motion.div 
                 key={i} 
                 initial={{ opacity: 0, x: 20 }}
                 animate={{ opacity: 1, x: 0 }}
                 className="flex items-center gap-3 shrink-0 group/card"
                 onClick={(e) => { e.stopPropagation(); setSelectedThreat(t.data); }}
               >
                 <div className="w-2 h-2 rounded-full bg-critical shadow-[0_0_8px_rgba(244,63,94,0.6)]" />
                 <span className="font-display font-bold text-[10px] uppercase text-critical">CRITICAL</span>
                 <span className="font-mono text-[10px] text-amber-primary">{t.data.technique_id}</span>
                 <span className="font-mono text-[10px] text-text-code">{t.data.indicators?.[0]}</span>
                 <span className="text-[10px] text-text-secondary max-w-[200px] truncate">{t.data.summary}</span>
                 <ChevronRight size={12} className="text-text-muted group-hover/card:translate-x-1 transition-transform" />
               </motion.div>
             ))
           )}
        </div>
      </div>

      {/* ── MAIN CANVAS ────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 relative">
        
        {/* Network Graph (40%) */}
        <section className="flex-[1.2] relative border-r border-border-subtle bg-bg-void/50">
          <div className="absolute top-6 left-6 z-10 space-y-1">
             <h3 className="font-display font-bold text-xs uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
               <Globe size={14} className="text-amber-primary" /> REAL-TIME TOPOLOGY
             </h3>
             <div className="text-[10px] text-text-muted/60 font-mono tracking-wider uppercase">MAPPED VIA nDPI + DISCOVERY AGENT</div>
          </div>
          <RiskGraph devices={devices} onSelectDevice={(d) => { setSelectedDevice(d); setSelectedThreat(null); }} />
        </section>

        {/* Device List (33%) */}
        <section className="flex-1 flex flex-col bg-bg-base/40 border-r border-border-subtle overflow-hidden">
          <div className="p-6 shrink-0 border-b border-border-subtle flex justify-between items-center bg-bg-surface/20">
             <h3 className="font-display font-bold text-xs uppercase tracking-[0.2em] text-text-muted flex items-center gap-2">
               <Cpu size={14} className="text-amber-primary" /> DISCOVERED NODES
             </h3>
             <span className="text-[10px] font-mono text-text-muted">{devices.length} TOTAL</span>
          </div>
          <div className="flex-1 overflow-y-auto no-scrollbar p-4 space-y-2">
            {devices.map(device => (
              <motion.div 
                key={device.device_id}
                whileHover={{ x: 4 }}
                onClick={() => { setSelectedDevice(device); setSelectedThreat(null); }}
                className={`p-4 rounded-xl border transition-all cursor-pointer group ${
                  selectedDevice?.device_id === device.device_id 
                    ? 'bg-bg-overlay border-amber-primary/40 shadow-lg' 
                    : 'bg-bg-surface/40 border-border-subtle hover:bg-bg-elevated hover:border-border-default'
                }`}
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="p-2 bg-bg-void rounded-lg border border-border-subtle group-hover:border-amber-primary/30 transition-colors">
                    <Activity size={16} className={device.risk_score > 7 ? 'text-critical' : device.risk_score > 4 ? 'text-warning' : 'text-safe'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-display font-bold text-sm text-text-primary truncate">{device.vendor || 'Unknown Host'}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="font-mono text-[10px] text-text-code">{device.ip}</span>
                      <div className="w-1 h-1 rounded-full bg-text-muted/30" />
                      <span className="text-[10px] text-text-muted truncate">{device.mac.toUpperCase()}</span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                     <span className={`font-display font-black text-lg leading-none ${
                        device.risk_score > 7 ? 'text-critical' : device.risk_score > 4 ? 'text-warning' : 'text-safe'
                     }`}>{device.risk_score.toFixed(1)}</span>
                     <div className="w-12 h-1 bg-bg-void rounded-full mt-1 overflow-hidden border border-border-subtle">
                        <motion.div 
                          initial={{ width: 0 }}
                          animate={{ width: `${device.risk_score * 10}%` }}
                          className={`h-full ${device.risk_score > 7 ? 'bg-critical' : device.risk_score > 4 ? 'bg-warning' : 'bg-safe'}`}
                        />
                     </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Detail Panel (27%) */}
        <section className="flex-[0.9] bg-bg-surface overflow-y-auto no-scrollbar shadow-2xl relative z-10 border-l border-border-subtle">
           <AnimatePresence mode="wait">
             {selectedThreat ? (
               <motion.div 
                 key="threat-detail"
                 initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}
                 className="p-8 space-y-8"
               >
                 <div className="space-y-4">
                    <div className="flex justify-between items-start">
                      <div className="p-3 bg-critical/10 border border-critical/20 rounded-2xl text-critical">
                        <ShieldAlert size={28} />
                      </div>
                      <button onClick={() => setSelectedThreat(null)} className="text-text-muted hover:text-text-primary transition-colors"><X size={20}/></button>
                    </div>
                    <div>
                      <h2 className="font-display font-extrabold text-2xl tracking-tight text-text-primary leading-tight">{selectedThreat.summary}</h2>
                      <p className="font-mono text-xs text-amber-primary mt-2 tracking-widest uppercase">{selectedThreat.technique_id} · {selectedThreat.tactic}</p>
                    </div>
                    <div className="flex gap-4">
                       <div className="bg-critical px-4 py-1.5 rounded-full text-[10px] font-display font-black tracking-widest text-white shadow-[0_4px_12px_rgba(244,63,94,0.3)] uppercase">
                         Severity {selectedThreat.severity}/10
                       </div>
                       <div className="bg-bg-overlay border border-border-subtle px-4 py-1.5 rounded-full text-[10px] font-mono text-text-secondary uppercase">
                         CONFIDENCE {Math.round(selectedThreat.confidence * 100)}%
                       </div>
                    </div>
                 </div>

                 <div className="space-y-4">
                    <h4 className="text-[10px] font-display font-bold text-text-muted tracking-[0.2em] uppercase">Security Indicators</h4>
                    <div className="space-y-2">
                       {selectedThreat.indicators?.map((ind: string) => (
                         <div key={ind} className="flex items-center gap-3 p-3 bg-bg-base rounded-xl border border-border-subtle group hover:border-amber-primary/30 transition-colors">
                            <Globe size={14} className="text-text-muted group-hover:text-amber-primary transition-colors" />
                            <span className="font-mono text-xs text-text-code flex-1">{ind}</span>
                            {selectedThreat.intel?.abuse_score > 0 && (
                              <span className="text-[10px] font-mono text-critical font-bold uppercase">{selectedThreat.intel.abuse_score}% ABUSE</span>
                            )}
                         </div>
                       ))}
                    </div>
                 </div>

                 <div className="bg-bg-overlay/50 border-l-2 border-info p-6 rounded-r-2xl space-y-3 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
                       <Zap size={64} className="text-info" />
                    </div>
                    <div className="text-[10px] font-display font-bold text-info tracking-widest uppercase flex items-center gap-2">
                       <Activity size={10} /> SENTINEL ANALYSIS
                    </div>
                    <div className="text-sm text-text-secondary leading-relaxed font-body italic">
                      "{selectedThreat.summary}"
                    </div>
                    <div className="pt-2 flex items-center gap-2">
                       <div className="w-4 h-4 rounded bg-white/10 flex items-center justify-center">
                          <Activity size={10} className="text-text-muted" />
                       </div>
                       <span className="text-[9px] font-mono text-text-muted uppercase tracking-tighter">Powered by Gemma 4 E2B</span>
                    </div>
                 </div>

                 <div className="space-y-3 pt-4">
                    <button 
                      onClick={() => setPendingAction({ device_id: selectedThreat.device_id, summary: selectedThreat.summary })}
                      className="w-full py-4 bg-critical hover:bg-critical/90 text-white font-display font-bold text-sm rounded-xl transition-all shadow-xl shadow-critical/20 flex items-center justify-center gap-2 group"
                    >
                      <ShieldAlert size={18} className="group-hover:rotate-12 transition-transform" />
                      QUARANTINE DEVICE
                    </button>
                    <button className="w-full py-4 bg-bg-elevated hover:bg-bg-overlay border border-border-default text-text-primary font-display font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2">
                      <Bug size={18} className="text-amber-primary" />
                      REDIRECT TO HONEYPOT
                    </button>
                 </div>
               </motion.div>
             ) : selectedDevice ? (
               <motion.div 
                key="device-detail"
                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}
                className="p-8 space-y-8"
               >
                 <div className="flex justify-between items-start">
                    <div className="w-16 h-16 bg-bg-void rounded-2xl border border-border-subtle flex items-center justify-center text-text-muted group-hover:border-amber-primary/30 transition-all">
                       <Cpu size={32} />
                    </div>
                    <button onClick={() => setSelectedDevice(null)} className="text-text-muted hover:text-text-primary transition-colors"><X size={20}/></button>
                 </div>

                 <div>
                    <div className="flex items-center gap-3">
                       <h2 className="font-display font-extrabold text-2xl tracking-tight text-text-primary">{selectedDevice.vendor || 'Unknown Node'}</h2>
                       <div className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest ${selectedDevice.is_quarantined ? 'bg-critical/20 text-critical border border-critical/30' : 'bg-safe/10 text-safe border border-safe/20'}`}>
                         {selectedDevice.is_quarantined ? 'QUARANTINED' : 'ONLINE'}
                       </div>
                    </div>
                    <p className="font-mono text-xs text-text-muted mt-1 uppercase tracking-[0.2em]">{selectedDevice.ip} · {selectedDevice.mac}</p>
                 </div>

                 <div className="grid grid-cols-2 gap-4">
                    <div className="bg-bg-base p-4 rounded-2xl border border-border-subtle">
                       <span className={`text-3xl font-display font-black ${selectedDevice.risk_score > 7 ? 'text-critical' : 'text-safe'}`}>
                         {selectedDevice.risk_score.toFixed(1)}
                       </span>
                       <p className="text-[9px] font-display font-bold text-text-muted uppercase tracking-widest mt-1">RISK SCORE</p>
                    </div>
                    <div className="bg-bg-base p-4 rounded-2xl border border-border-subtle">
                       <span className="text-3xl font-display font-black text-text-code">
                         {JSON.parse(selectedDevice.open_ports || '[]').length}
                       </span>
                       <p className="text-[9px] font-display font-bold text-text-muted uppercase tracking-widest mt-1">OPEN PORTS</p>
                    </div>
                 </div>

                 <div className="space-y-4">
                    <h4 className="text-[10px] font-display font-bold text-text-muted tracking-[0.2em] uppercase">Vulnerabilities Detected</h4>
                    <div className="space-y-3">
                       {JSON.parse(selectedDevice.cve_list || '[]').length === 0 ? (
                         <div className="p-4 bg-safe/5 border border-safe/10 rounded-xl text-center">
                            <div className="text-xs text-safe font-medium uppercase tracking-tight">No CVEs found for this vendor.</div>
                         </div>
                       ) : (
                         JSON.parse(selectedDevice.cve_list || '[]').map((cve: any) => (
                           <div key={cve.cve_id} className="p-4 bg-bg-base border border-border-subtle rounded-xl space-y-2 group hover:border-critical/30 transition-colors">
                              <div className="flex justify-between items-center">
                                 <span className="font-mono text-xs text-critical font-bold tracking-tight">{cve.cve_id}</span>
                                 <span className="text-[10px] font-display font-black px-2 py-0.5 bg-critical/10 text-critical rounded uppercase">LVL {cve.cvss_score || cve.score}</span>
                              </div>
                              <div className="text-[11px] text-text-secondary leading-relaxed line-clamp-2 font-body italic">
                                {cve.description || 'Remote code execution or privilege escalation risk.'}
                              </div>
                           </div>
                         ))
                       )}
                    </div>
                 </div>

                 <div className="space-y-4">
                    <h4 className="text-[10px] font-display font-bold text-text-muted tracking-[0.2em] uppercase">Discovery Insight</h4>
                    <div className="flex items-center gap-3 p-4 bg-bg-base rounded-xl border border-border-subtle">
                       <Activity size={14} className="text-text-muted" />
                       <div className="flex-1">
                          <div className="text-[11px] text-text-secondary font-body leading-tight">First identified via passive SSDP sniffing.</div>
                          <div className="text-[10px] text-text-muted font-mono mt-1 uppercase tracking-tighter">
                            Seen {isMounted ? new Date(selectedDevice.last_seen).toLocaleString() : '---'}
                          </div>
                       </div>
                    </div>
                 </div>

                 {!selectedDevice.is_quarantined && (
                   <div className="pt-4">
                      <button 
                        onClick={() => setPendingAction({ device_id: selectedDevice.device_id, summary: `Manual quarantine requested for ${selectedDevice.vendor}` })}
                        className="w-full py-4 bg-bg-overlay hover:bg-critical hover:text-white border border-border-strong text-critical font-display font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2 group uppercase tracking-widest"
                      >
                        <ShieldAlert size={18} className="group-hover:scale-110 transition-transform" />
                        INITIATE QUARANTINE
                      </button>
                   </div>
                 )}
               </motion.div>
             ) : (
               <motion.div 
                key="empty-detail"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="h-full flex flex-col items-center justify-center p-12 text-center space-y-6"
               >
                 <div className="relative">
                   <div className="absolute inset-0 bg-amber-primary/20 blur-3xl rounded-full" />
                   <div className="relative w-24 h-24 bg-bg-base rounded-3xl border border-border-subtle flex items-center justify-center text-text-muted shadow-2xl">
                     <Shield size={40} className="text-text-disabled" />
                   </div>
                 </div>
                 <div className="space-y-2">
                   <h3 className="font-display font-bold text-lg tracking-tight uppercase tracking-widest">Select Node</h3>
                   <p className="text-sm text-text-muted font-body leading-relaxed max-w-[200px]">Click a device on the graph or list to view security intelligence.</p>
                 </div>
                 <div className="pt-4 grid grid-cols-2 gap-3 w-full">
                    <div className="p-3 bg-bg-base rounded-xl border border-border-subtle text-left">
                       <span className="text-[9px] font-display font-black text-text-muted uppercase tracking-widest block">Uptime</span>
                       <span className="font-mono text-xs text-text-secondary uppercase">4d 12h 31m</span>
                    </div>
                    <div className="p-3 bg-bg-base rounded-xl border border-border-subtle text-left">
                       <span className="text-[9px] font-display font-black text-text-muted uppercase tracking-widest block">Throughput</span>
                       <span className="font-mono text-xs text-text-secondary uppercase">842 pps</span>
                    </div>
                 </div>
               </motion.div>
             )}
           </AnimatePresence>
        </section>

      </div>

      {/* ── INTEL STRIP (Bottom) ────────────────────────────────── */}
      <footer className="h-[120px] bg-bg-surface border-t border-border-subtle shrink-0 grid grid-cols-12 z-20">
         
         <div className="col-span-4 border-r border-border-subtle p-6 flex flex-col">
            <h4 className="text-[10px] font-display font-bold text-text-muted tracking-[0.2em] uppercase flex items-center gap-2 mb-3">
              <Bug size={12} className="text-amber-primary" /> HONEYPOT SESSIONS
            </h4>
            <div className="flex-1 overflow-y-auto no-scrollbar font-mono text-[10px] text-text-secondary space-y-1.5">
               <div className="text-text-muted italic opacity-50 flex items-center gap-2">
                 <div className="w-1 h-1 rounded-full bg-border-strong"/> 
                 Honeypots active and listening on virtual IPs...
               </div>
               <div className="flex justify-between border-l border-border-subtle pl-3 py-1 uppercase tracking-tighter">
                  <span>SSH Connection Attempt · cowrie</span>
                  <span className="text-text-muted">4m ago</span>
               </div>
            </div>
         </div>

         <div className="col-span-4 border-r border-border-subtle p-6 flex flex-col">
            <h4 className="text-[10px] font-display font-bold text-text-muted tracking-[0.2em] uppercase flex items-center gap-2 mb-3">
              <Globe size={12} className="text-amber-primary" /> THREAT INTEL BUS
            </h4>
            <div className="flex-1 overflow-y-auto no-scrollbar font-mono text-[10px] text-text-secondary space-y-1.5">
               {activeThreats.slice(0, 3).map((e, i) => (
                 <div key={i} className="flex justify-between border-l border-critical/30 pl-3 py-1 uppercase tracking-tighter">
                    <span className="text-critical font-bold truncate pr-2">MATCH: {e.data.intel?.otx_tags?.[0] || 'MALICIOUS'}</span>
                    <span className="text-text-muted shrink-0">{Math.round(e.data.intel?.abuse_score || 0)}% CONF</span>
                 </div>
               ))}
               {activeThreats.length === 0 && (
                  <div className="text-text-muted italic opacity-50 flex items-center gap-2">
                    <div className="w-1 h-1 rounded-full bg-border-strong"/> 
                    Subscribed to AlienVault OTX & AbuseIPDB...
                  </div>
               )}
            </div>
         </div>

         <div className="col-span-4 p-6 flex flex-col">
            <h4 className="text-[10px] font-display font-bold text-text-muted tracking-[0.2em] uppercase flex items-center gap-2 mb-3">
              <Zap size={12} className="text-amber-primary" /> SENTINEL HEALTH
            </h4>
            <div className="grid grid-cols-3 gap-6 flex-1">
               <div className="space-y-2">
                  <div className="flex justify-between text-[9px] font-mono font-bold uppercase"><span>CPU</span><span className="text-amber-primary">34%</span></div>
                  <div className="h-1.5 bg-bg-base rounded-full border border-border-subtle overflow-hidden">
                    <div className="h-full w-[34%] bg-safe rounded-full" />
                  </div>
               </div>
               <div className="space-y-2">
                  <div className="flex justify-between text-[9px] font-mono font-bold uppercase"><span>RAM</span><span className="text-amber-primary">61%</span></div>
                  <div className="h-1.5 bg-bg-base rounded-full border border-border-subtle overflow-hidden">
                    <div className="h-full w-[61%] bg-warning rounded-full" />
                  </div>
               </div>
               <div className="space-y-2 text-right">
                  <div className="text-[9px] font-mono font-bold uppercase text-text-muted mb-1 tracking-widest">PACKETS/S</div>
                  <div className="text-xl font-display font-black text-text-primary leading-none tabular-nums tracking-tighter animate-pulse">847</div>
               </div>
            </div>
         </div>

      </footer>

      {/* ── SECURITY GATE MODAL ──────────────────────────────────── */}
      <AnimatePresence>
        {pendingAction && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-bg-void/90 backdrop-blur-md z-[100] flex items-center justify-center p-4"
          >
            <motion.div 
              initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }}
              className="bg-bg-surface border-2 border-critical p-10 rounded-[2.5rem] max-w-xl w-full shadow-[0_0_100px_rgba(244,63,94,0.3)] relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
                 <ShieldAlert size={120} className="text-critical" />
              </div>

              <div className="space-y-8 relative z-10">
                <div className="flex items-center gap-4 text-critical">
                  <div className="w-14 h-14 bg-critical/20 rounded-2xl flex items-center justify-center">
                    <ShieldAlert size={32} />
                  </div>
                  <div>
                    <h2 className="text-3xl font-display font-extrabold tracking-tighter uppercase tracking-tighter leading-none">Security Intervention</h2>
                    <p className="text-[10px] font-mono tracking-[0.3em] uppercase opacity-70 mt-2">Layer 5 Response Gate Active</p>
                  </div>
                </div>

                <div className="bg-bg-base/50 p-6 rounded-3xl border border-border-subtle space-y-4">
                  <div className="space-y-1">
                    <span className="text-[9px] font-display font-black text-text-muted tracking-[0.2em] uppercase">Anomaly Source</span>
                    <p className="text-xl font-display font-bold text-text-primary">Suspicious Traffic from {pendingAction.device_id}</p>
                  </div>
                  <div className="text-sm text-text-secondary leading-relaxed font-body italic">
                    "{pendingAction.summary}"
                  </div>
                  <div className="pt-4 border-t border-border-subtle flex flex-col gap-2">
                     <div className="flex items-center gap-2 text-xs text-text-secondary">
                        <Lock size={14} className="text-critical" />
                        <span className="uppercase tracking-tight text-[10px] font-bold">Action will immediately drop all L2/L3 traffic.</span>
                     </div>
                     <div className="flex items-center gap-2 text-xs text-text-secondary">
                        <Fingerprint size={14} className="text-amber-primary" />
                        <span className="uppercase tracking-tight text-[10px] font-bold">Authorized audit log will be generated.</span>
                     </div>
                  </div>
                </div>

                <div className="flex flex-col gap-4">
                  <button 
                    onClick={authorizeQuarantine}
                    className="w-full py-5 bg-critical hover:bg-critical/90 text-white font-display font-black text-lg rounded-2xl transition-all shadow-xl shadow-critical/30 flex items-center justify-center gap-3 active:scale-95 uppercase tracking-widest"
                  >
                    AUTHORIZE QUARANTINE
                  </button>
                  <button 
                    onClick={() => setPendingAction(null)}
                    className="w-full py-4 bg-transparent hover:bg-bg-elevated text-text-muted font-display font-bold text-sm rounded-2xl transition-all uppercase tracking-widest"
                  >
                    DISMISS AND MONITOR
                  </button>
                </div>

                <div className="flex justify-center pt-2">
                   <div className="flex gap-1.5 items-center">
                      {[1,2,3,4,5,6].map(i => <div key={i} className="w-1.5 h-1.5 rounded-full bg-border-strong animate-pulse" style={{ animationDelay: `${i*150}ms` }} />)}
                   </div>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
