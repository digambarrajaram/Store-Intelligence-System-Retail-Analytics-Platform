import { KPICards } from './components/KPICards';
import { OccupancyChart } from './components/OccupancyChart';
import { AnomalyFeed } from './components/AnomalyFeed';
import { FunnelChart } from './components/FunnelChart';
import { SalespersonLeaderboard } from './components/SalespersonLeaderboard';
import ErrorBoundary from './components/ErrorBoundary';

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-900 text-white p-4">
      <h1 className="text-2xl font-bold mb-6">Store Intelligence Dashboard</h1>
      <div className="grid gap-6">
        {/* KPI Cards Row */}
        <div className="col-span-2">
          <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load KPI Cards</div>}>
            <KPICards />
          </ErrorBoundary>
        </div>

        {/* Second Row: Occupancy Chart and Anomaly Feed */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-800 bg-opacity-50 rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-4">Occupancy Trends (Last 60 Minutes)</h2>
            <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Occupancy Chart</div>}>
              <OccupancyChart />
            </ErrorBoundary>
          </div>
          <div className="bg-gray-800 bg-opacity-50 rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-4">Active Alerts</h2>
            <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Anomaly Feed</div>}>
              <AnomalyFeed />
            </ErrorBoundary>
          </div>
        </div>

        {/* Third Row: Funnel Chart and Salesperson Leaderboard */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-800 bg-opacity-50 rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-4">Conversion Funnel</h2>
            <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Funnel Chart</div>}>
              <FunnelChart />
            </ErrorBoundary>
          </div>
          <div className="bg-gray-800 bg-opacity-50 rounded-lg p-4">
            <h2 className="text-lg font-semibold mb-4">Salesperson Leaderboard</h2>
            <ErrorBoundary fallback={<div className="p-4 text-red-400 text-center">Failed to load Salesperson Leaderboard</div>}>
              <SalespersonLeaderboard />
            </ErrorBoundary>
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;