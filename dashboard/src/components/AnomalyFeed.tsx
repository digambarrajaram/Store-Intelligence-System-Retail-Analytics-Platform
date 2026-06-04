import React from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { Alert } from '../types/api';
import { useEffect, useRef, useState } from 'react';

export const AnomalyFeed = () => {
  const rawWsUrl = import.meta.env.VITE_WS_URL?.trim();
  // If VITE_WS_URL already contains /ws/alerts, use it directly.
  // Otherwise, append /ws/alerts to the base URL.
  const wsUrl = rawWsUrl
    ? rawWsUrl.replace(/\/$/, '')
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
  const fullWsUrl = wsUrl.includes('/ws/alerts') ? wsUrl : `${wsUrl}/ws/alerts`;
  const { data: wsMessage, error, isConnected } = useWebSocket<Alert>(fullWsUrl);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [toastAlert, setToastAlert] = useState<Alert | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const severityMap = {
    critical: { icon: '🔥', label: 'Critical', styles: 'bg-rose-500/20 text-rose-300' },
    warning: { icon: '⚠️', label: 'Warning', styles: 'bg-amber-500/20 text-amber-300' },
    info: { icon: 'ℹ️', label: 'Info', styles: 'bg-sky-500/20 text-sky-300' },
  } as const;

  useEffect(() => {
    if (!wsMessage) return;

    if (wsMessage.type === 'anomaly' || wsMessage.type === 'catchup') {
      console.log('[AnomalyFeed] Alert received:', wsMessage.type, wsMessage.data);
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
      <div className="w-full h-full flex items-center justify-center bg-red-500/10 rounded">
        <div className="text-center">
          <p className="text-red-400 font-semibold">WebSocket Error</p>
          <p className="text-red-300 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-800/50 rounded">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-cyan-400 border-t-transparent mb-3"></div>
          <p className="text-slate-400">Connecting to alerts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-800/20 rounded">
      {toastAlert && (
        <div className="pointer-events-none absolute right-4 top-4 z-20 w-72 rounded-2xl border border-cyan-400/30 bg-slate-950/95 p-4 shadow-2xl shadow-black/50 animate-in fade-in slide-in-from-top-2">
          <p className="text-xs uppercase tracking-[0.24em] text-cyan-300">New Alert</p>
          <p className="mt-2 text-sm font-semibold text-white">{toastAlert.type}</p>
          <p className="mt-1 text-sm text-slate-400">{toastAlert.zone}</p>
          <p className="mt-2 text-xs text-slate-500">{new Date(toastAlert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
        </div>
      )}
      <div className="flex-1 overflow-y-auto space-y-1">
        {alerts.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500">
            Waiting for alerts...
          </div>
        ) : (
          alerts.map((alert) => (
            <div key={alert.id} className="p-3 border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors last:border-b-0">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className={`flex-shrink-0 px-2 py-0.5 text-xs font-bold rounded-full ${
                      alert.severity === 'critical'
                        ? 'bg-rose-500/20 text-rose-300'
                        : alert.severity === 'warning'
                        ? 'bg-amber-500/20 text-amber-300'
                        : 'bg-blue-500/20 text-blue-300'
                    }`}
                  >
                    {alert.severity.charAt(0).toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium text-white text-sm truncate">{alert.type}</p>
                    <p className="text-xs text-slate-500 truncate">{alert.zone}</p>
                  </div>
                </div>
                <p className="flex-shrink-0 text-xs text-slate-600">
                  {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};