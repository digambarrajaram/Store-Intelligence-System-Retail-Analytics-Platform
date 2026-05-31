import { useEffect, useRef, useState } from 'react';

export interface WebSocketMessage<T> {
  data: T;
}

export const useWebSocket = <T>(url: string) => {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);

  useEffect(() => {
    const connect = () => {
      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          setError(null);
          retryCountRef.current = 0;
        };

        ws.onmessage = (event) => {
          try {
            const parsedData = JSON.parse(event.data) as T;
            setData(parsedData);
          } catch (e) {
            setError('Failed to parse WebSocket message');
          }
        };

        ws.onerror = (e) => {
          setError('WebSocket error');
          console.error('WebSocket error:', e);
        };

        ws.onclose = () => {
          setIsConnected(false);
          // Attempt to reconnect with exponential backoff
          const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000);
          retryCountRef.current++;
          setTimeout(connect, delay);
        };
      } catch (e) {
        setError('Failed to create WebSocket');
        console.error('Failed to create WebSocket:', e);
      }
    };

    connect();

    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [url]);

  return { data, error, isConnected };
};