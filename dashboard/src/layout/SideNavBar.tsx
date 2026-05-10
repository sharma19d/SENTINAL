import React from 'react';
import { 
  Shield, 
  LayoutDashboard, 
  Router, 
  AlertTriangle, 
  Lock, 
  CircleDot, 
  Settings, 
  PlusCircle, 
  Terminal, 
  ListChecks 
} from 'lucide-react';
import { Screen } from '../types';
import { cn } from '../lib/utils';

interface SideNavBarProps {
  activeScreen: Screen;
  setActiveScreen: (screen: Screen) => void;
}

export default function SideNavBar({ activeScreen, setActiveScreen }: SideNavBarProps) {
  const navItems = [
    { id: Screen.DASHBOARD, label: 'Dashboard', icon: LayoutDashboard },
    { id: Screen.DEVICES, label: 'Devices', icon: Router },
    { id: Screen.THREATS, label: 'Threats', icon: AlertTriangle },
    { id: Screen.FIREWALL, label: 'Firewall', icon: Lock },
    { id: Screen.HONEYPOTS, label: 'Honeypots', icon: CircleDot },
    { id: Screen.SETTINGS, label: 'Settings', icon: Settings },
  ];

  const diagnosticsActive = activeScreen === Screen.DIAGNOSTICS;
  const logsActive = activeScreen === Screen.LOGS;

  return (
    <nav className="w-[260px] flex-shrink-0 h-full border-r border-white/10 bg-white/5 backdrop-blur-3xl flex flex-col py-8 z-40">
      <div className="px-6 mb-12">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-full bg-white/10 border border-white/20 flex items-center justify-center glow-white">
            <Shield className="w-6 h-6 text-white fill-current" />
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
                "flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 w-full group",
                isActive 
                  ? "bg-white/5 text-white border-l-2 border-white shadow-[inset_10px_0_20px_-10px_rgba(255,255,255,0.1)]" 
                  : "text-outline hover:text-white hover:bg-white/5 border-l-2 border-transparent"
              )}
            >
              <Icon className={cn("w-5 h-5", isActive ? "className-fill" : "")} />
              <span className={cn("text-sm font-medium", isActive && "font-semibold")}>{item.label}</span>
            </button>
          );
        })}
      </div>

      <div className="px-4 mt-auto flex flex-col gap-4">
        <button className="w-full bg-white/10 border border-white/20 text-white py-3 rounded text-sm font-bold flex items-center justify-center gap-2 hover:bg-white/20 transition-all uppercase font-display tracking-wider">
          <PlusCircle className="w-4 h-4 fill-white text-black" />
          Deploy Node
        </button>
        
        <div className="flex flex-col gap-1 pt-4 border-t border-white/10">
          <button
            onClick={() => setActiveScreen(Screen.DIAGNOSTICS)}
            className={cn(
              "flex items-center gap-3 px-2 py-2 transition-colors rounded",
              diagnosticsActive ? "text-white bg-white/5" : "text-outline hover:text-white"
            )}
          >
            <Terminal className="w-4 h-4" />
            <span className="text-xs font-mono uppercase tracking-tight">Diagnostics</span>
          </button>
          <button
            onClick={() => setActiveScreen(Screen.LOGS)}
            className={cn(
              "flex items-center gap-3 px-2 py-2 transition-colors rounded",
              logsActive ? "text-white bg-white/5" : "text-outline hover:text-white"
            )}
          >
            <ListChecks className="w-4 h-4" />
            <span className="text-xs font-mono uppercase tracking-tight">Logs</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
