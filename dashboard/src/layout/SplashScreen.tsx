import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { Shield } from 'lucide-react';
import sentinelIcon from '../assets/icon.png';

const BOOT_MESSAGES = [
  'Initializing packet capture engine…',
  'Loading device registry…',
  'Starting anomaly detection agent…',
  'Warming up threat classifier…',
  'Arming deception layer…',
  'Syncing firewall rules…',
  'Connecting threat intelligence bus…',
  'Vigilance active.',
];

const MIN_DURATION_MS = 1800;

interface SplashScreenProps {
  onDone: () => void;
}

export default function SplashScreen({ onDone }: SplashScreenProps) {
  const [progress, setProgress] = useState(0);
  const startRef = useRef<number>(performance.now());

  useEffect(() => {
    let frame: number;
    const tick = () => {
      const elapsed = performance.now() - startRef.current;
      const pct = Math.min(100, (elapsed / MIN_DURATION_MS) * 100);
      setProgress(pct);
      if (pct < 100) {
        frame = requestAnimationFrame(tick);
      } else {
        onDone();
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [onDone]);

  const messageIndex = Math.min(
    BOOT_MESSAGES.length - 1,
    Math.floor((progress / 100) * BOOT_MESSAGES.length)
  );

  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5, ease: 'easeInOut' }}
      className="fixed inset-0 z-[200] bg-black flex flex-col items-center justify-center overflow-hidden"
    >
      {/* Grid background — matches Dashboard topology panel */}
      <div
        className="absolute inset-0 pointer-events-none opacity-10"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.15) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Radial glow behind logo */}
      <div className="absolute w-[420px] h-[420px] rounded-full bg-white/5 blur-3xl pointer-events-none" />

      {/* Logo */}
      <motion.div
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="relative z-10 flex flex-col items-center gap-6"
      >
        <motion.div
          animate={{ boxShadow: ['0 0 20px rgba(255,255,255,0.15)', '0 0 40px rgba(255,255,255,0.35)', '0 0 20px rgba(255,255,255,0.15)'] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
          className="w-20 h-20 rounded-full border border-white/20 overflow-hidden flex items-center justify-center bg-white/5"
        >
          <img src={sentinelIcon} alt="SENTINEL" className="w-full h-full object-cover grayscale" />
        </motion.div>

        <div className="flex flex-col items-center gap-2">
          <h1 className="text-3xl md:text-4xl font-bold text-white tracking-tight neon-text-glow">
            SENTINEL
          </h1>
          <div className="flex items-center gap-2">
            <Shield className="w-3 h-3 text-outline" />
            <p className="text-[10px] font-display font-bold text-outline tracking-[0.3em] uppercase">
              Agentic AI IoT Security
            </p>
          </div>
        </div>
      </motion.div>

      {/* Boot sequence */}
      <div className="relative z-10 mt-14 flex flex-col items-center gap-4 w-[280px]">
        <div className="w-full h-[3px] bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-white glow-white rounded-full"
            style={{ width: `${progress}%` }}
          />
        </div>

        <p className="text-[11px] font-mono text-outline uppercase tracking-wider text-center min-h-[16px]">
          {BOOT_MESSAGES[messageIndex]}
        </p>
      </div>

      {/* Pulse dot bottom corner, matches Dashboard "System Protected" indicator */}
      <div className="absolute bottom-8 flex items-center gap-2">
        <motion.div
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.6, repeat: Infinity }}
          className="w-1.5 h-1.5 rounded-full bg-white"
        />
        <span className="text-[9px] font-mono text-outline/60 uppercase tracking-widest">
          {Math.round(progress)}%
        </span>
      </div>
    </motion.div>
  );
}
