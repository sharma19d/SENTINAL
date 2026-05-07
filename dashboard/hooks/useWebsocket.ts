import { useEffect, useState, useRef, useCallback } from 'react';

export function useWebsocket(url: string) {
  const [events, setEvents] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef(1000);
  const unmounted = useRef(false);

  const connect = useCallback(() => {
    if (unmounted.current) return;
    if (ws.current?.readyState === WebSocket.OPEN) return;

    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      setIsConnected(true);
      reconnectDelay.current = 1000;
    };

    ws.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setEvents((prev) => [message, ...prev].slice(0, 100));
      } catch {
        // ignore malformed frames
      }
    };

    ws.current.onclose = () => {
      setIsConnected(false);
      if (!unmounted.current) {
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30_000);
          connect();
        }, reconnectDelay.current);
      }
    };

    ws.current.onerror = () => {
      ws.current?.close();
    };
  }, [url]);

  useEffect(() => {
    unmounted.current = false;
    connect();
    return () => {
      unmounted.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [connect]);

  return { events, isConnected };
}
