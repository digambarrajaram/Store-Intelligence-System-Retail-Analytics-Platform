import React from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts';
import { usePolling } from '../hooks/usePolling';
import { OccupancyData } from '../types/api';

const fetchOccupancyData = async (): Promise<OccupancyData[]> => {
  const apiUrl = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.trim() : '/api/v1';
  const response = await fetch(`${apiUrl}/occupancy/history?window_minutes=60&interval_minutes=5`);
  if (!response.ok) {
    throw new Error('Failed to fetch occupancy data');
  }
  const payload = await response.json();
  console.log('[OccupancyChart] API Response:', {
    status: response.status,
    payload,
    historyCount: (payload.history || []).length,
    sampleData: (payload.history || [])[0]
  });
  return payload.history || [];
};

export const OccupancyChart = () => {
  const { data, error, isLoading } = usePolling<OccupancyData[]>(fetchOccupancyData, 30000, {
    immediate: true,
  });

  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (data && data.length > 0) {
      console.log('[OccupancyChart] Data loaded successfully:', {
        count: data.length,
        firstItem: data[0],
        lastItem: data[data.length - 1],
        containerHeight: containerRef.current?.offsetHeight,
      });
    }
  }, [data]);

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-800/50 rounded">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-cyan-400 border-t-transparent mb-3"></div>
          <p className="text-slate-400">Loading occupancy chart...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-red-500/10 rounded">
        <div className="text-center">
          <p className="text-red-400 font-semibold">Error loading chart</p>
          <p className="text-red-300 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-800/30 rounded">
        <p className="text-slate-400">No occupancy data available</p>
      </div>
    );
  }

  // Calculate peak for reference line
  const peak = Math.max(...data.map((d) => d.count));
  const dataWithPeak = data.map((d) => ({ ...d, peak }));

  return (
    <div ref={containerRef} className="w-full h-full flex flex-col">
      <ResponsiveContainer width="100%" height="100%" debounce={100}>
        <AreaChart 
          data={dataWithPeak} 
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
          syncId="store-metrics"
        >
          <defs>
            <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#475569" vertical={false} />
          <XAxis 
            dataKey="timestamp" 
            stroke="#94a3b8" 
            style={{ fontSize: '12px' }}
            tickFormatter={(timestamp) => {
              try {
                const date = new Date(timestamp);
                return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
              } catch {
                return timestamp;
              }
            }} 
          />
          <YAxis 
            stroke="#94a3b8" 
            style={{ fontSize: '12px' }}
            domain={[0, peak * 1.1]}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: '#0f172a', 
              border: '1px solid #475569', 
              borderRadius: '6px',
              color: '#f1f5f9'
            }} 
            labelStyle={{ color: '#f1f5f9' }}
            formatter={(value) => [`${value} customers`, 'Occupancy']}
          />
          <Area 
            type="monotone" 
            dataKey="count" 
            stroke="#06b6d4" 
            fill="url(#colorCount)" 
            isAnimationActive={false}
            name="Store Occupancy"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

