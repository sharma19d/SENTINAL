import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Search, Bell, Activity, User, Menu, Wifi, WifiOff } from 'lucide-react';
import { Screen } from '../types';
import {
  ApiActivityPulse,
  ApiNetworkResponse,
  ApiNotificationsResponse,
  ApiSearchResponse,
  fetchActivityPulse,
  fetchCurrentNetwork,
  fetchGlobalSearch,
  fetchNotifications,
} from '../lib/api';

interface TopNavBarProps {
  onNavigateToResult: (screen: Screen, query: string) => void;
  onMenuToggle?: () => void;
}

export default function TopNavBar({ onNavigateToResult, onMenuToggle }: TopNavBarProps) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<ApiSearchResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [notifOpen, setNotifOpen] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  const [network, setNetwork] = useState<ApiNetworkResponse | null>(null);
  const [notifications, setNotifications] = useState<ApiNotificationsResponse | null>(null);
  const [activityPulse, setActivityPulse] = useState<ApiActivityPulse | null>(null);
  const [notifLoading, setNotifLoading] = useState(false);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityRefreshing, setActivityRefreshing] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const notifRef = useRef<HTMLDivElement>(null);
  const activityRef = useRef<HTMLDivElement>(null);

  const items = useMemo(() => {
    const devices = (results?.devices || []).map((d) => ({
      key: `device-${d.device_id}`,
      title: d.ip || d.mac || d.device_id,
      subtitle: `${d.vendor || 'Unknown vendor'} · ${d.mac}`,
      screen: Screen.DEVICES,
    }));

    const threats = (results?.threats || []).map((t) => ({
      key: `threat-${t.event_id}`,
      title: t.summary || t.technique_id || t.event_id,
      subtitle: `${t.tactic || 'Unknown tactic'} · SEV ${t.severity}`,
      screen: Screen.THREATS,
    }));

    return [...devices, ...threats];
  }, [results]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!searchRef.current?.contains(target)) {
        setOpen(false);
      }
      if (!notifRef.current?.contains(target)) {
        setNotifOpen(false);
      }
      if (!activityRef.current?.contains(target)) {
        setActivityOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults(null);
      setOpen(false);
      setSelectedIndex(-1);
      return;
    }

    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetchGlobalSearch(trimmed, 6);
        setResults(res);
        setOpen(true);
      } catch {
        setResults({ query: trimmed, total: 0, devices: [], threats: [] });
        setOpen(true);
      } finally {
        setLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(timer);
  }, [query]);

  const handleSelect = (index: number) => {
    const item = items[index];
    if (!item) return;
    onNavigateToResult(item.screen, query.trim());
    setOpen(false);
  };

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || items.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % items.length);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev <= 0 ? items.length - 1 : prev - 1));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSelect(selectedIndex >= 0 ? selectedIndex : 0);
      return;
    }
    if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const loadNotifications = async () => {
    setNotifLoading(true);
    try {
      setNotifications(await fetchNotifications(8));
    } catch {
      setNotifications({ total: 0, unread: 0, items: [] });
    } finally {
      setNotifLoading(false);
    }
  };

  const loadActivityPulse = async (silent = false) => {
    if (silent) {
      setActivityRefreshing(true);
    } else {
      setActivityLoading(true);
    }
    try {
      setActivityPulse(await fetchActivityPulse());
    } catch {
      if (!silent) {
        setActivityPulse(null);
      }
    } finally {
      if (silent) {
        setActivityRefreshing(false);
      } else {
        setActivityLoading(false);
      }
    }
  };

  useEffect(() => {
    loadNotifications();
  }, []);

  // The appliance can be moved to a different network while the dashboard
  // is open, so this is polled rather than read once at mount.
  useEffect(() => {
    const load = async () => {
      try {
        setNetwork(await fetchCurrentNetwork());
      } catch {
        setNetwork(null);
      }
    };
    load();
    const interval = window.setInterval(load, 15000);
    return () => window.clearInterval(interval);
  }, []);

  const toggleNotifications = () => {
    const next = !notifOpen;
    setNotifOpen(next);
    setActivityOpen(false);
    if (next) {
      loadNotifications();
    }
  };

  const toggleActivity = () => {
    const next = !activityOpen;
    setActivityOpen(next);
    setNotifOpen(false);
    if (next) {
      loadActivityPulse(false);
    }
  };

  useEffect(() => {
    if (!activityOpen) return;
    const interval = window.setInterval(() => {
      loadActivityPulse(true);
    }, 15000);
    return () => window.clearInterval(interval);
  }, [activityOpen]);

  const unreadCount = notifications?.unread || 0;

  return (
    <header className="h-[56px] md:h-[72px] w-full sticky top-0 z-50 bg-black/40 backdrop-blur-3xl border-b border-white/10 flex items-center justify-between px-4 md:px-10 gap-3">
      {/* Hamburger — mobile only */}
      <button
        onClick={onMenuToggle}
        className="md:hidden text-outline hover:text-white transition-colors flex-shrink-0 p-1"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      <div className="flex-1 max-w-xs sm:max-w-md">
        <div className="relative group" ref={searchRef}>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-outline group-focus-within:text-white transition-colors" />
          <input 
            type="text" 
            placeholder="Search MAC, IP, or Vector..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setOpen((results?.total || 0) > 0)}
            onKeyDown={onInputKeyDown}
            className="w-full bg-black/20 border border-white/10 text-white rounded-md py-2 pl-10 pr-4 focus:outline-none focus:border-white/30 focus:ring-1 focus:ring-white/20 transition-all placeholder:text-outline/40 font-mono text-sm uppercase tracking-tight"
          />

          {open && (
            <div className="absolute top-[calc(100%+8px)] left-0 right-0 rounded-lg border border-white/10 bg-black/95 backdrop-blur-xl overflow-hidden shadow-xl">
              {loading ? (
                <div className="px-4 py-3 text-xs font-mono text-outline">Searching…</div>
              ) : items.length === 0 ? (
                <div className="px-4 py-3 text-xs font-mono text-outline">No matches found.</div>
              ) : (
                <div className="max-h-80 overflow-y-auto">
                  {items.map((item, index) => (
                    <button
                      key={item.key}
                      onClick={() => handleSelect(index)}
                      className={`w-full text-left px-4 py-3 border-b border-white/5 last:border-b-0 transition-colors ${
                        selectedIndex === index ? 'bg-white/10' : 'hover:bg-white/5'
                      }`}
                    >
                      <p className="text-sm text-white truncate">{item.title}</p>
                      <p className="text-[10px] font-mono text-outline truncate uppercase tracking-tight">{item.subtitle}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 md:gap-6">
        {/* Which network the dashboard is currently reporting on */}
        <div
          className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-md border border-white/10 bg-white/[0.03]"
          title={
            network?.current
              ? `Gateway ${network.current.gateway_ip} (${network.current.gateway_mac}) on ${network.current.interface}`
              : 'No network detected'
          }
        >
          {network?.current ? (
            <Wifi className="w-3.5 h-3.5 text-white/70" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-outline" />
          )}
          <span className="text-[10px] font-mono uppercase tracking-tight text-white/70">
            {network?.current ? network.current.subnet : 'No network'}
          </span>
        </div>

        <div className="flex gap-3 md:gap-4">
          <div className="relative" ref={notifRef}>
            <button onClick={toggleNotifications} className="relative text-outline hover:text-white transition-colors">
              <Bell className="w-5 h-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 bg-white text-black rounded-full text-[9px] font-bold flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>
            {notifOpen && (
              <div className="absolute top-[calc(100%+10px)] right-0 w-[calc(100vw-2rem)] max-w-[360px] rounded-lg border border-white/10 bg-black/95 backdrop-blur-xl overflow-hidden shadow-xl z-50">
                <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                  <span className="text-xs font-display font-bold text-white uppercase tracking-wider">Notifications</span>
                  <span className="text-[10px] font-mono text-outline">{notifications?.total || 0} events</span>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifLoading ? (
                    <div className="px-4 py-4 text-xs font-mono text-outline">Loading…</div>
                  ) : (notifications?.items.length || 0) === 0 ? (
                    <div className="px-4 py-4 text-xs font-mono text-outline">No notifications yet.</div>
                  ) : (
                    notifications!.items.map((n) => (
                      <div key={n.id} className="px-4 py-3 border-b border-white/5 last:border-b-0">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm text-white leading-tight">{n.title}</p>
                          {n.unread && <span className="w-1.5 h-1.5 rounded-full bg-white mt-1 shrink-0" />}
                        </div>
                        <p className="text-[10px] font-mono text-outline uppercase tracking-tight mt-1">
                          {n.detail} · SEV {n.severity}
                        </p>
                        <p className="text-[10px] font-mono text-outline/70 mt-1">
                          {n.timestamp ? new Date(n.timestamp).toLocaleString() : '—'}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="relative" ref={activityRef}>
            <button onClick={toggleActivity} className="text-outline hover:text-white transition-colors">
              <Activity className="w-5 h-5" />
            </button>
            {activityOpen && (
              <div className="absolute top-[calc(100%+10px)] right-0 w-[calc(100vw-2rem)] max-w-[360px] rounded-lg border border-white/10 bg-black/95 backdrop-blur-xl overflow-hidden shadow-xl z-50">
                <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                  <span className="text-xs font-display font-bold text-white uppercase tracking-wider">Activity Pulse</span>
                  <span className="text-[10px] font-mono text-outline uppercase">
                    {activityRefreshing ? 'updating' : (activityPulse?.overall_status || 'offline')}
                  </span>
                </div>
                {activityLoading || !activityPulse ? (
                  <div className="px-4 py-4 text-xs font-mono text-outline">{activityLoading ? 'Loading…' : 'No activity data.'}</div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-2 p-4 border-b border-white/10">
                      <div className="bg-white/[0.03] border border-white/10 rounded p-2">
                        <p className="text-[10px] font-mono text-outline">CPU</p>
                        <p className="text-sm text-white">{activityPulse.metrics.cpu_percent}%</p>
                      </div>
                      <div className="bg-white/[0.03] border border-white/10 rounded p-2">
                        <p className="text-[10px] font-mono text-outline">MEM</p>
                        <p className="text-sm text-white">{activityPulse.metrics.memory_percent.toFixed(2)}%</p>
                      </div>
                      <div className="bg-white/[0.03] border border-white/10 rounded p-2">
                        <p className="text-[10px] font-mono text-outline">Devices</p>
                        <p className="text-sm text-white">{activityPulse.metrics.total_devices}</p>
                      </div>
                      <div className="bg-white/[0.03] border border-white/10 rounded p-2">
                        <p className="text-[10px] font-mono text-outline">Threats</p>
                        <p className="text-sm text-white">{activityPulse.metrics.active_threats}</p>
                      </div>
                    </div>
                    <div className="px-4 py-3 border-b border-white/10">
                      <p className="text-[10px] font-display font-bold text-outline uppercase tracking-wider mb-2">Services</p>
                      <div className="flex gap-2 flex-wrap">
                        {activityPulse.services.map((service) => (
                          <span key={service.name} className="px-2 py-1 text-[10px] font-mono uppercase rounded border border-white/10 text-outline">
                            {service.name}: {service.status}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="max-h-44 overflow-y-auto">
                      {activityPulse.recent_events.length === 0 ? (
                        <div className="px-4 py-3 text-xs font-mono text-outline">No recent events.</div>
                      ) : (
                        activityPulse.recent_events.map((event) => (
                          <div key={event.id} className="px-4 py-3 border-b border-white/5 last:border-b-0">
                            <p className="text-sm text-white leading-tight">{event.message}</p>
                            <p className="text-[10px] font-mono text-outline mt-1">
                              SEV {event.severity} · {event.timestamp ? new Date(event.timestamp).toLocaleString() : '—'}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
        
        <div className="hidden sm:block h-6 w-px bg-white/10" />

        <div className="hidden sm:flex items-center gap-3">
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
