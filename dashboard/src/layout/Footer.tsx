import React from 'react';

export default function Footer() {
  return (
    <footer className="fixed bottom-0 left-[260px] right-0 h-[40px] bg-black/80 backdrop-blur-md border-t border-white/10 flex justify-between items-center px-10 z-50">
      <span className="text-[10px] font-display font-bold text-outline tracking-widest uppercase">
        SENTINEL v2.4.0-STABLE
      </span>
      <div className="flex gap-6">
        <span className="text-[11px] font-mono text-white glow-sm cursor-default">LSTM: ACTIVE</span>
        <span className="text-[11px] font-mono text-outline hover:text-white cursor-default transition-colors">LLM: RUNNING</span>
        <span className="text-[11px] font-mono text-outline hover:text-white cursor-default transition-colors">eBPF: MONITORING</span>
      </div>
    </footer>
  );
}
