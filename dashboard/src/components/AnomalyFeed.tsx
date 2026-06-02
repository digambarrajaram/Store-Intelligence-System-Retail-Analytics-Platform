import React from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { Alert } from '../types/api';
import { useEffect, useRef, useState } from 'react';

interface AlertEvent {
  type: string;
  data: Alert;
}

export const AnomalyFeed = () => {
  const rawWsUrl = import.meta.env.VITE_WS_URL?.trim();
  const wsUrl = rawWsUrl
    ? rawWsUrl.replace(/\/$/, '')
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
  const { data: wsMessage, error, isConnected } = useWebSocket<Alert>(`${wsUrl}/ws/alerts`);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [toastAlert, setToastAlert] = useState<Alert | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!wsMessage) return;

    if (wsMessage.type === 'anomaly' || wsMessage.type === 'catchup') {
      const alert = wsMessage.data;
      setAlerts((prev) => [alert, ...prev].slice(0, 20));

      if (wsMessage.type === 'anomaly') {
        setToastAlert(alert);
      }
    }
  }, [wsMessage]);

  // Scroll to bottom when new alert arrives
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [alerts]);

  useEffect(() => {
    if (!toastAlert) return;
    const timer = window.setTimeout(() => setToastAlert(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toastAlert]);

  if (error) {
    return (
      <div className="h-96 w-full bg-red-500 bg-opacity-20 rounded-lg p-4">
        <div className="h-full flex items-center justify-center text-red-400">
          WebSocket Error: {error}
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="h-96 w-full bg-gray-700 bg-opacity-50 rounded-lg p-4">
        <div className="h-full flex items-center justify-center text-gray-400">
          Connecting to WebSocket...
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-96 w-full bg-gray-800 bg-opacity-50 rounded-lg p-4 overflow-y-auto">
      {toastAlert && (
        <div className="pointer-events-none absolute right-4 top-4 z-20 w-72 rounded-2xl border border-cyan-400/20 bg-slate-950/95 p-4 shadow-2xl shadow-black/30">
          <p className="text-xs uppercase tracking-[0.24em] text-cyan-300">New Alert</p>
          <p className="mt-2 text-sm font-semibold text-white">{toastAlert.type}</p>
          <p className="mt-1 text-sm text-slate-400">{toastAlert.zone}</p>
          <p className="mt-2 text-xs text-slate-500">{new Date(toastAlert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
        </div>
      )}
      <div className="space-y-2">
        {alerts.map((alert) => (
          <div key={alert.id} className="p-3 border-b border-gray-700 last:border-b-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <span
                  className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                    alert.severity === 'critical'
                      ? 'bg-red-500 text-white'
                      : alert.severity === 'warning'
                      ? 'bg-yellow-500 text-black'
                      : 'bg-blue-500 text-white'
                  }`}
                >
                  {alert.severity.toUpperCase()}
                </span>
                <div>
                  <p className="font-medium text-white">{alert.type}</p>
                  <p className="text-sm text-gray-400">{alert.zone}</p>
                </div>
              </div>
              <p className="text-xs text-gray-500">
                {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}
        {alerts.length === 0 && (
          <div className="py-4 text-center text-gray-400">
            No alerts
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};