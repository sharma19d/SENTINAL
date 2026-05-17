import React, { useState } from 'react';
import {
  LayoutDashboard,
  Router,
  AlertTriangle,
  Lock,
  CircleDot,
  Settings,
  PlusCircle,
  Terminal,
  ListChecks,
  X,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import sentinelIcon from '../assets/icon.png';
import { Screen } from '../types';
import { cn } from '../lib/utils';
import { deployNode } from '../lib/api';

interface SideNavBarProps {
  activeScreen: Screen;
  setActiveScreen: (screen: Screen) => void;
}

interface DeployForm {
  ip: string;
  label: string;
  mac: string;
}

type DeployState = 'idle' | 'loading' | 'success' | 'error';

export default function SideNavBar({ activeScreen, setActiveScreen }: SideNavBarProps) {
  const [showDeploy, setShowDeploy] = useState(false);
  const [form, setForm] = useState<DeployForm>({ ip: '', label: '', mac: '' });
  const [deployState, setDeployState] = useState<DeployState>('idle');
  const [resultMsg, setResultMsg] = useState('');

  const navItems = [
    { id: Screen.DASHBOARD,   label: 'Dashboard', icon: LayoutDashboard },
    { id: Screen.DEVICES,     label: 'Devices',   icon: Router },
    { id: Screen.THREATS,     label: 'Threats',   icon: AlertTriangle },
    { id: Screen.FIREWALL,    label: 'Firewall',  icon: Lock },
    { id: Screen.HONEYPOTS,   label: 'Honeypots', icon: CircleDot },
    { id: Screen.SETTINGS,    label: 'Settings',  icon: Settings },
  ];

  const diagnosticsActive = activeScreen === Screen.DIAGNOSTICS;
  const logsActive = activeScreen === Screen.LOGS;

  const openDeploy = () => {
    setForm({ ip: '', label: '', mac: '' });
    setDeployState('idle');
    setResultMsg('');
    setShowDeploy(true);
  };

  const closeDeploy = () => {
    if (deployState === 'loading') return;
    setShowDeploy(false);
  };

  const handleDeploy = async () => {
    if (!form.ip.trim() || !form.label.trim()) return;
    setDeployState('loading');
    try {
      const result = await deployNode({
        ip: form.ip.trim(),
        label: form.label.trim(),
        mac: form.mac.trim() || undefined,
      });
      setResultMsg(result.message);
      setDeployState('success');
      setTimeout(() => {
        setShowDeploy(false);
        setDeployState('idle');
      }, 2200);
    } catch (err: any) {
      const text = err?.message || '';
      setResultMsg(
        text.includes('Invalid IP')
          ? 'Invalid IP address format.'
          : text.includes('400')
          ? 'Bad request — check IP and label.'
          : 'Backend unreachable. Is the API running?'
      );
      setDeployState('error');
    }
  };

  const canSubmit = form.ip.trim().length > 0 && form.label.trim().length > 0 && deployState !== 'loading';

  return (
    <>
      <nav className="w-[260px] flex-shrink-0 h-full border-r border-white/10 bg-white/5 backdrop-blur-3xl flex flex-col py-8 z-40">
        <div className="px-6 mb-12">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-full border border-white/20 overflow-hidden glow-white flex-shrink-0">
              <img src={sentinelIcon} alt="SENTINEL" className="w-full h-full object-cover grayscale" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight leading-none neon-text-glow">SENTINEL</h1>
              <p className="text-[10px] font-display font-bold text-outline tracking-widest uppercase mt-1">Vigilance Active</p>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-1 w-full px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeScreen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveScreen(item.id)}
                className={cn(
                  'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 w-full group',
                  isActive
                    ? 'bg-white/5 text-white border-l-2 border-white shadow-[inset_10px_0_20px_-10px_rgba(255,255,255,0.1)]'
                    : 'text-outline hover:text-white hover:bg-white/5 border-l-2 border-transparent'
                )}
              >
                <Icon className={cn('w-5 h-5', isActive ? 'className-fill' : '')} />
                <span className={cn('text-sm font-medium', isActive && 'font-semibold')}>{item.label}</span>
              </button>
            );
          })}
        </div>

        <div className="px-4 mt-auto flex flex-col gap-4">
          <button
            onClick={openDeploy}
            className="w-full bg-white/10 border border-white/20 text-white py-3 rounded text-sm font-bold flex items-center justify-center gap-2 hover:bg-white/20 transition-all uppercase font-display tracking-wider"
          >
            <PlusCircle className="w-4 h-4 fill-white text-black" />
            Deploy Node
          </button>

          <div className="flex flex-col gap-1 pt-4 border-t border-white/10">
            <button
              onClick={() => setActiveScreen(Screen.DIAGNOSTICS)}
              className={cn(
                'flex items-center gap-3 px-2 py-2 transition-colors rounded',
                diagnosticsActive ? 'text-white bg-white/5' : 'text-outline hover:text-white'
              )}
            >
              <Terminal className="w-4 h-4" />
              <span className="text-xs font-mono uppercase tracking-tight">Diagnostics</span>
            </button>
            <button
              onClick={() => setActiveScreen(Screen.LOGS)}
              className={cn(
                'flex items-center gap-3 px-2 py-2 transition-colors rounded',
                logsActive ? 'text-white bg-white/5' : 'text-outline hover:text-white'
              )}
            >
              <ListChecks className="w-4 h-4" />
              <span className="text-xs font-mono uppercase tracking-tight">Logs</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Deploy Node Modal */}
      {showDeploy && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-[440px] bg-black border border-white/20 rounded-2xl shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-white/10">
              <div>
                <h2 className="text-lg font-bold text-white tracking-tight">Deploy Node</h2>
                <p className="text-[11px] font-mono text-outline mt-0.5">Register a new monitored asset into the SENTINEL registry</p>
              </div>
              <button
                onClick={closeDeploy}
                disabled={deployState === 'loading'}
                className="text-outline hover:text-white transition-colors disabled:opacity-40"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Form */}
            <div className="px-6 py-6 flex flex-col gap-5">
              {/* IP Address */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">
                  IP Address <span className="text-white/50">*</span>
                </label>
                <input
                  type="text"
                  placeholder="192.168.0.50"
                  value={form.ip}
                  onChange={e => setForm(f => ({ ...f, ip: e.target.value }))}
                  disabled={deployState === 'loading' || deployState === 'success'}
                  className="bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm font-mono text-white placeholder:text-outline/40 focus:outline-none focus:border-white/30 transition-colors disabled:opacity-50"
                />
              </div>

              {/* Label */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">
                  Node Label <span className="text-white/50">*</span>
                </label>
                <input
                  type="text"
                  placeholder="Raspberry Pi Sensor / IP Camera / etc."
                  value={form.label}
                  onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
                  disabled={deployState === 'loading' || deployState === 'success'}
                  className="bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm font-mono text-white placeholder:text-outline/40 focus:outline-none focus:border-white/30 transition-colors disabled:opacity-50"
                />
              </div>

              {/* MAC (optional) */}
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] font-display font-bold text-outline uppercase tracking-widest">
                  MAC Address <span className="text-outline/40">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="aa:bb:cc:dd:ee:ff — auto-generated if blank"
                  value={form.mac}
                  onChange={e => setForm(f => ({ ...f, mac: e.target.value }))}
                  disabled={deployState === 'loading' || deployState === 'success'}
                  className="bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm font-mono text-white placeholder:text-outline/40 focus:outline-none focus:border-white/30 transition-colors disabled:opacity-50"
                />
              </div>

              {/* Result message */}
              {(deployState === 'success' || deployState === 'error') && (
                <div className={cn(
                  'flex items-start gap-3 rounded-lg p-3 border text-sm',
                  deployState === 'success'
                    ? 'bg-white/5 border-white/20 text-white'
                    : 'bg-white/[0.03] border-white/10 text-outline'
                )}>
                  {deployState === 'success'
                    ? <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-white" />
                    : <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
                  <span className="font-mono text-xs leading-relaxed">{resultMsg}</span>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-white/10 flex justify-end gap-3">
              <button
                onClick={closeDeploy}
                disabled={deployState === 'loading'}
                className="px-5 py-2 text-xs font-display font-bold uppercase tracking-wider text-outline border border-white/10 rounded-lg hover:text-white hover:border-white/30 transition-all disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                onClick={handleDeploy}
                disabled={!canSubmit}
                className={cn(
                  'px-5 py-2 text-xs font-display font-bold uppercase tracking-wider rounded-lg transition-all flex items-center gap-2',
                  canSubmit
                    ? 'bg-white text-black hover:bg-white/90'
                    : 'bg-white/5 text-outline border border-white/10 cursor-not-allowed'
                )}
              >
                {deployState === 'loading' ? (
                  <>
                    <span className="w-3 h-3 border border-black/40 border-t-black rounded-full animate-spin" />
                    Deploying…
                  </>
                ) : deployState === 'success' ? (
                  <>
                    <CheckCircle className="w-3 h-3" />
                    Deployed
                  </>
                ) : (
                  <>
                    <PlusCircle className="w-3 h-3" />
                    Deploy
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
