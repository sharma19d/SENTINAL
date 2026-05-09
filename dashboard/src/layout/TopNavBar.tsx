import React from 'react';
import { Search, Bell, Activity, User } from 'lucide-react';

export default function TopNavBar() {
  return (
    <header className="h-[72px] w-full sticky top-0 z-50 bg-black/40 backdrop-blur-3xl border-b border-white/10 flex items-center justify-between px-10">
      <div className="flex-1 max-w-md">
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-outline group-focus-within:text-white transition-colors" />
          <input 
            type="text" 
            placeholder="Search MAC, IP, or Vector..." 
            className="w-full bg-black/20 border border-white/10 text-white rounded-md py-2 pl-10 pr-4 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/20 transition-all placeholder:text-outline/40 font-mono text-sm uppercase tracking-tight"
          />
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex gap-4">
          <button className="relative text-outline hover:text-white transition-colors">
            <Bell className="w-5 h-5" />
            <span className="absolute top-0 right-0 w-2 h-2 bg-white rounded-full ring-2 ring-black" />
          </button>
          <button className="text-outline hover:text-white transition-colors">
            <Activity className="w-5 h-5" />
          </button>
        </div>
        
        <div className="h-6 w-px bg-white/10" />
        
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-display font-bold text-outline border border-white/10 rounded px-1.5 py-0.5 uppercase">SA</span>
          <div className="w-8 h-8 rounded-full border border-white/20 bg-white/5 flex items-center justify-center p-1 grayscale group hover:grayscale-0 transition-all cursor-pointer">
            <div className="w-full h-full rounded-full bg-white/10 flex items-center justify-center">
              <User className="w-4 h-4 text-white/40" />
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
