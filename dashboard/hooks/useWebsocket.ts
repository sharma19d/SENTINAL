import { useEffect, useState, useRef } from 'react';

export function useWebsocket(url: string) {
  const [events, setEvents] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      setIsConnected(true);
      console.log('Connected to SENTINEL Event Stream');
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setEvents((prev) => [message, ...prev].slice(0, 100));
    };

    ws.current.onclose = () => {
      setIsConnected(false);
      console.log('Disconnected from SENTINEL Event Stream');
    };

    return () => {
      ws.current?.close();
    };
  }, [url]);

  return { events, isConnected };
}
