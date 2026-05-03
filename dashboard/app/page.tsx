'use client';

import { useEffect, useState } from 'react';
import { useWebsocket } from '../hooks/useWebsocket';
import RiskGraph from '../components/RiskGraph';
import { Shield, AlertTriangle, Cpu, Activity, Globe } from 'lucide-react';

export default function Dashboard() {
  const [devices, setDevices] = useState<any[]>([]);
  const [pendingAction, setPendingAction] = useState<any>(null);
  const { events, isConnected } = useWebsocket('ws://localhost:8000/ws/events');

  useEffect(() => {
    fetch('http://localhost:8000/api/devices')
      .then(res => res.json())
      .then(data => setDevices(data))
      .catch(err => console.error('Fetch error:', err));
  }, []);

  // Watch for pending actions
  useEffect(() => {
    const latestAlert = events.find(e => e.channel === 'sentinel:alerts' && e.data.status === 'pending_confirmation');
    if (latestAlert) {
      setPendingAction(latestAlert.data);
    }
  }, [events]);

  const authorizeQuarantine = async () => {
    if (!pendingAction) return;
    try {
      await fetch(`http://localhost:8000/api/actions/quarantine/${pendingAction.device_id}`, { method: 'POST' });
      setPendingAction(null);
    } catch (err) {
      console.error('Action failed:', err);
    }
  };

  return (
    <main className="flex min-h-screen flex-col bg-slate-950 text-slate-100 p-8">
      {/* Security Gate Modal */}
      {pendingAction && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border-2 border-red-500 p-8 rounded-2xl max-w-lg w-full shadow-2xl animate-in zoom-in duration-300">
            <h2 className="text-2xl font-bold text-red-500 mb-4 flex items-center gap-2">
              <Shield className="w-8 h-8" /> ACTION REQUIRED
            </h2>
            <p className="text-slate-300 mb-6 font-medium">
              {pendingAction.summary}
            </p>
            <div className="flex gap-4">
              <button 
                onClick={authorizeQuarantine}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 rounded-xl transition-all"
              >
                AUTHORIZE QUARANTINE
              </button>
              <button 
                onClick={() => setPendingAction(null)}
                className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold py-3 rounded-xl transition-all"
              >
                DISMISS
              </button>
            </div>
          </div>
        </div>
      )}
      <header className="flex justify-between items-center mb-8 border-b border-slate-800 pb-6">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Shield className="text-blue-500 w-8 h-8" />
            SENTINEL <span className="text-slate-500 font-light">| IoT Security</span>
          </h1>
          <p className="text-slate-400">Agentic AI Network Monitoring</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-slate-900 px-4 py-2 rounded-full border border-slate-800">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-sm font-medium">{isConnected ? 'System Online' : 'System Offline'}</span>
          </div>
        </div>
      </header>

      {/* Grid Layout */}
      <div className="grid grid-cols-12 gap-8 flex-1">
        
        {/* Left Column: Stats & Device List */}
        <div className="col-span-3 space-y-6">
          <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 shadow-xl">
            <h3 className="text-slate-400 uppercase text-xs font-bold tracking-widest mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4" /> System Health
            </h3>
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <span className="text-2xl font-bold">{devices.length}</span>
                <p className="text-[10px] text-slate-500">DEVICES</p>
              </div>
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <span className="text-2xl font-bold text-red-500">{events.filter(e => e.channel === 'sentinel:threat').length}</span>
                <p className="text-[10px] text-slate-500">ACTIVE THREATS</p>
              </div>
            </div>
          </div>

          <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800 shadow-xl flex-1 overflow-auto max-h-[600px]">
            <h3 className="text-slate-400 uppercase text-xs font-bold tracking-widest mb-4 flex items-center gap-2">
              <Cpu className="w-4 h-4" /> Active Devices
            </h3>
            <div className="space-y-3">
              {devices.map(device => (
                <div key={device.device_id} className="p-3 bg-slate-950 rounded-lg border border-slate-800 hover:border-blue-500 transition-colors cursor-pointer group">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-bold text-sm">{device.vendor || 'Unknown Device'}</p>
                      <p className="text-[10px] text-slate-500 font-mono">{device.ip}</p>
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                      device.risk_score > 7 ? 'bg-red-900 text-red-200' : 
                      device.risk_score > 4 ? 'bg-orange-900 text-orange-200' : 'bg-green-900 text-green-200'
                    }`}>
                      {device.risk_score} Risk
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center Column: Risk Map */}
        <div className="col-span-6 flex flex-col gap-6">
          <div className="flex-1 bg-slate-900 rounded-2xl border border-slate-800 shadow-2xl relative overflow-hidden">
            <div className="absolute top-6 left-6 z-10">
              <h3 className="text-slate-400 uppercase text-xs font-bold tracking-widest flex items-center gap-2">
                <Globe className="w-4 h-4" /> Real-time Risk Topology
              </h3>
            </div>
            <RiskGraph devices={devices} />
          </div>
        </div>

        {/* Right Column: Threat Feed */}
        <div className="col-span-3 bg-slate-900 p-6 rounded-2xl border border-slate-800 shadow-xl overflow-hidden flex flex-col">
          <h3 className="text-slate-400 uppercase text-xs font-bold tracking-widest mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Security Intelligence Feed
          </h3>
          <div className="flex-1 overflow-auto space-y-4 pr-2">
            {events.length === 0 && (
              <div className="h-full flex items-center justify-center text-slate-600 italic text-sm">
                Waiting for network events...
              </div>
            )}
            {events.map((event, i) => (
              <div key={i} className={`p-4 rounded-xl border animate-in fade-in slide-in-from-right duration-500 ${
                event.channel === 'sentinel:threat' ? 'bg-red-950/30 border-red-900' : 
                event.channel === 'sentinel:anomaly' ? 'bg-orange-950/30 border-orange-900' : 'bg-blue-950/30 border-blue-900'
              }`}>
                <div className="flex justify-between items-center mb-1">
                   <span className="text-[10px] font-bold uppercase tracking-wider">
                     {event.channel.split(':')[1]}
                   </span>
                   <span className="text-[10px] text-slate-500">Just now</span>
                </div>
                <p className="text-xs font-medium text-slate-200 leading-relaxed">
                  {event.data.summary || event.data.anomaly_score || 'Network activity detected'}
                </p>
                {event.data.tactic && (
                  <div className="mt-2 text-[10px] bg-red-900/50 text-red-200 inline-block px-2 py-0.5 rounded">
                    {event.data.tactic}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

      </div>
    </main>
  );
}
