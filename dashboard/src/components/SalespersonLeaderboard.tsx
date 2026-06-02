import React from 'react';
import { usePolling } from '../hooks/usePolling';
import { SalespersonData } from '../types/api';

const fetchSalespersonData = async (): Promise<SalespersonData[]> => {
  // Get today's date in YYYY-MM-DD format
  const today = new Date().toISOString().split('T')[0];
  const apiUrl = import.meta.env.VITE_API_URL ? import.meta.env.VITE_API_URL.trim() : '/api/v1';
  const response = await fetch(`${apiUrl}/insights/salesperson?date=${today}`);
  if (!response.ok) {
    throw new Error('Failed to fetch salesperson data');
  }
  const data = await response.json();
  // Map API response to match SalespersonData interface
  return data.map((person: any, index: number) => ({
    id: person.salesperson_name || `person_${index}`, // Use name as ID or generate fallback
    name: person.salesperson_name,
    gmv: person.total_gmv,
    transactions: person.order_count
  }));
};

export const SalespersonLeaderboard = () => {
  const { data, error, isLoading } = usePolling<SalespersonData[]>(fetchSalespersonData, 30000, {
    immediate: true,
  });

  React.useEffect(() => {
    if (data) {
      console.log('[SalespersonLeaderboard] Data loaded:', { count: data.length, data });
    }
  }, [data]);

  const [sortConfig, setSortConfig] = React.useState<{ key: keyof SalespersonData; direction: 'asc' | 'desc' } | null>(null);

  const sortedData = React.useMemo(() => {
    if (!sortConfig || !data) return data;
    return [...data].sort((a, b) => {
      if (sortConfig.key === 'gmv') {
        return sortConfig.direction === 'asc'
          ? a.gmv - b.gmv
          : b.gmv - a.gmv;
      }
      if (sortConfig.key === 'transactions') {
        return sortConfig.direction === 'asc'
          ? a.transactions - b.transactions
          : b.transactions - a.transactions;
      }
      if (sortConfig.key === 'name') {
        return sortConfig.direction === 'asc'
          ? a.name.localeCompare(b.name)
          : b.name.localeCompare(a.name);
      }
      return sortConfig.direction === 'asc'
        ? a.name.localeCompare(b.name)
        : b.name.localeCompare(a.name);
    });
  }, [data, sortConfig]);

  const requestSort = (key: keyof SalespersonData) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-800/50 rounded">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-cyan-400 border-t-transparent mb-3"></div>
          <p className="text-slate-400">Loading leaderboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-red-500/10 rounded">
        <div className="text-center">
          <p className="text-red-400 font-semibold">Error loading data</p>
          <p className="text-red-300 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!sortedData || sortedData.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-800/30 rounded">
        <p className="text-slate-400">No salesperson data available</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col bg-slate-800/20 rounded overflow-hidden">
      <div className="flex-1 overflow-y-auto">
        <table className="w-full divide-y divide-slate-700">
          <thead className="sticky top-0 bg-slate-950/60 backdrop-blur-sm">
            <tr>
              <th className="px-4 py-3 text-left">
                <button
                  onClick={() => requestSort('name')}
                  className="text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-300 transition-colors flex items-center gap-1"
                >
                  Salesperson
                  {sortConfig?.key === 'name' && (
                    <span className="text-cyan-400">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  )}
                </button>
              </th>
              <th className="px-4 py-3 text-right">
                <button
                  onClick={() => requestSort('gmv')}
                  className="text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-300 transition-colors flex items-center justify-end gap-1 w-full"
                >
                  GMV
                  {sortConfig?.key === 'gmv' && (
                    <span className="text-cyan-400">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  )}
                </button>
              </th>
              <th className="px-4 py-3 text-right">
                <button
                  onClick={() => requestSort('transactions')}
                  className="text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-300 transition-colors flex items-center justify-end gap-1 w-full"
                >
                  Orders
                  {sortConfig?.key === 'transactions' && (
                    <span className="text-cyan-400">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
                  )}
                </button>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {sortedData.map((person, rank) => (
              <tr key={person.id} className="hover:bg-slate-700/20 transition-colors">
                <td className="px-4 py-3 whitespace-nowrap">
                  <div className="flex items-center gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-xs font-bold text-white">
                      {rank + 1}
                    </div>
                    <span className="text-sm font-medium text-white">{person.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-right">
                  <span className="text-sm font-semibold text-cyan-300">${person.gmv.toLocaleString()}</span>
                </td>
                <td className="px-4 py-3 whitespace-nowrap text-right">
                  <span className="text-sm text-slate-300">{person.transactions}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};