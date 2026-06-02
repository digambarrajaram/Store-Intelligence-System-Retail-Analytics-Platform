import React from 'react';
import { KPICards } from './components/KPICards';
import { OccupancyChart } from './components/OccupancyChart';
import { AnomalyFeed } from './components/AnomalyFeed';
import { FunnelChart } from './components/FunnelChart';
import { SalespersonLeaderboard } from './components/SalespersonLeaderboard';
import ErrorBoundary from './components/ErrorBoundary';

const App = () => {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.18),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.16),_transparent_30%)]" />
        <div className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <header className="mb-8 rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/30 backdrop-blur-xl">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.24em] text-cyan-300/80">Store Intelligence</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Store Intelligence Dashboard</h1>
                <p className="mt-3 max-w-2xl text-sm text-slate-400 sm:text-base">
                  Real-time footfall, sales conversion, and alert insights for your store operations.
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
          </header>

          <div className="grid gap-6">
            <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-white">Key Metrics</h2>
                  <p className="mt-1 text-sm text-slate-400">A quick view of occupancy, conversion, and anomaly status.</p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <span className="rounded-full bg-slate-800 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-300">High confidence</span>
                  <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-cyan-200">Real-time</span>
                </div>
              </div>
              <div className="mt-6">
                <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load KPI Cards</div>}>
                  <KPICards />
                </ErrorBoundary>
              </div>
            </section>

            <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl">
                <h2 className="text-xl font-semibold text-white">Occupancy Trends</h2>
                <p className="mt-1 text-sm text-slate-400">Last 60 minutes of customer entries and peak flow.</p>
                <div className="mt-6 min-h-[420px]">
                  <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Occupancy Chart</div>}>
                    <OccupancyChart />
                  </ErrorBoundary>
                </div>
              </section>

              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl">
                <h2 className="text-xl font-semibold text-white">Active Alerts</h2>
                <p className="mt-1 text-sm text-slate-400">Live anomaly events streamed from the store sensors.</p>
                <div className="mt-6 min-h-[420px]">
                  <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Anomaly Feed</div>}>
                    <AnomalyFeed />
                  </ErrorBoundary>
                </div>
              </section>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl">
                <h2 className="text-xl font-semibold text-white">Conversion Funnel</h2>
                <p className="mt-1 text-sm text-slate-400">Track how visitors move through the purchase funnel.</p>
                <div className="mt-6 min-h-[340px]">
                  <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Funnel Chart</div>}>
                    <FunnelChart />
                  </ErrorBoundary>
                </div>
              </section>

              <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/20 backdrop-blur-xl">
                <h2 className="text-xl font-semibold text-white">Salesperson Leaderboard</h2>
                <p className="mt-1 text-sm text-slate-400">See the top performers driving the highest sales.</p>
                <div className="mt-6 min-h-[340px]">
                  <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Salesperson Leaderboard</div>}>
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