import React, { useEffect, useState } from 'react';
import { KPICards } from './components/KPICards';
import { OccupancyChart } from './components/OccupancyChart';
import { AnomalyFeed } from './components/AnomalyFeed';
import { FunnelChart } from './components/FunnelChart';
import { SalespersonLeaderboard } from './components/SalespersonLeaderboard';
import ErrorBoundary from './components/ErrorBoundary';

const App = () => {
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const activeCameraCount = import.meta.env.VITE_ACTIVE_CAMERAS ? parseInt(import.meta.env.VITE_ACTIVE_CAMERAS, 10) : 4;
  const buildVersion = import.meta.env.VITE_BUILD_VERSION || '1.0.0';
  const environment = import.meta.env.VITE_ENVIRONMENT || 'Production';

  useEffect(() => {
    const interval = window.setInterval(() => setLastUpdated(new Date()), 30000);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="relative overflow-hidden">
        {/* Background gradients */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.16),_transparent_30%)]" />
        
        <div className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {/* Header */}
          <header className="mb-8 rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/30 backdrop-blur-xl">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.24em] text-cyan-300/80">Store Intelligence</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Dashboard</h1>
                <p className="mt-3 max-w-2xl text-sm text-slate-400 sm:text-base">
                  Real-time footfall, conversion metrics, and anomaly alerts powered by computer vision and sensor fusion.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:w-auto">
                <div className="rounded-2xl bg-slate-950/90 px-4 py-3 text-center ring-1 ring-white/10">
                  <p className="text-sm text-slate-400">Live Status</p>
                  <p className="mt-1 font-semibold text-emerald-400">Connected</p>
                </div>
                <div className="rounded-2xl bg-slate-950/90 px-4 py-3 text-center ring-1 ring-white/10">
                  <p className="text-sm text-slate-400">Updated</p>
                  <p className="mt-1 font-semibold text-sky-400">Every 30s</p>
                </div>
              </div>
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-3">
              <div className="rounded-3xl bg-white/5 p-4 ring-1 ring-cyan-400/10 backdrop-blur-xl">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-400">System Status</p>
                <p className="mt-3 text-2xl font-semibold text-white">Operational</p>
              </div>
              <div className="rounded-3xl bg-white/5 p-4 ring-1 ring-slate-400/10 backdrop-blur-xl">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Active Cameras</p>
                <p className="mt-3 text-2xl font-semibold text-cyan-300">{activeCameraCount}</p>
              </div>
              <div className="rounded-3xl bg-white/5 p-4 ring-1 ring-slate-400/10 backdrop-blur-xl">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-400">Last Updated</p>
                <p className="mt-3 text-2xl font-semibold text-sky-300">{lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
              </div>
            </div>
          </header>

          <div className="grid gap-6">
            {/* KPI Cards Section */}
            <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl">
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-white">Key Performance Indicators</h2>
                <p className="mt-1 text-sm text-slate-400">Real-time metrics at a glance</p>
              </div>
              <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load KPI Cards</div>}>
                <KPICards />
              </ErrorBoundary>
            </section>

            {/* Charts Grid: Occupancy + Alerts */}
            <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
              {/* Occupancy Chart */}
              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl flex flex-col">
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-white">Occupancy Trends</h2>
                  <p className="mt-1 text-sm text-slate-400">Last 60 minutes of store traffic</p>
                </div>
                <div className="flex-1 min-h-[420px] w-full">
                  <ErrorBoundary fallback={<div className="h-full p-4 text-red-400 text-center flex items-center justify-center">Failed to load Occupancy Chart</div>}>
                    <OccupancyChart />
                  </ErrorBoundary>
                </div>
              </section>

              {/* Active Alerts / Anomaly Feed */}
              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl flex flex-col">
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-white">Live Alerts</h2>
                  <p className="mt-1 text-sm text-slate-400">Real-time anomaly events</p>
                </div>
                <div className="flex-1 min-h-[420px] w-full">
                  <ErrorBoundary fallback={<div className="h-full p-4 text-red-400 text-center flex items-center justify-center">Failed to load Anomaly Feed</div>}>
                    <AnomalyFeed />
                  </ErrorBoundary>
                </div>
              </section>
            </div>

            {/* Charts Grid: Funnel + Leaderboard */}
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Conversion Funnel */}
              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl flex flex-col">
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-white">Conversion Funnel</h2>
                  <p className="mt-1 text-sm text-slate-400">Customer journey through purchase stages</p>
                </div>
                <div className="flex-1 min-h-[340px] w-full">
                  <ErrorBoundary fallback={<div className="h-full p-4 text-red-400 text-center flex items-center justify-center">Failed to load Funnel Chart</div>}>
                    <FunnelChart />
                  </ErrorBoundary>
                </div>
              </section>

              {/* Salesperson Leaderboard */}
              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl flex flex-col">
                <div className="mb-6">
                  <h2 className="text-xl font-semibold text-white">Top Performers</h2>
                  <p className="mt-1 text-sm text-slate-400">Daily leaderboard by GMV</p>
                </div>
                <div className="flex-1 min-h-[340px] w-full">
                  <ErrorBoundary fallback={<div className="h-full p-4 text-red-400 text-center flex items-center justify-center">Failed to load Leaderboard</div>}>
                    <SalespersonLeaderboard />
                  </ErrorBoundary>
                </div>
              </section>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
};

export default App;