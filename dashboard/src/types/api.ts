export interface OccupancyData {
  timestamp: string;
  count: number;
}

export interface KPIData {
  currentOccupancy: number;
  occupancyTrend: 'up' | 'down' | 'stable';
  totalEntriesToday: number;
  entriesTodaySparkline: number[]; // last 30 minutes, for example
  conversionRate: number; // percentage
  activeAnomalies: number;
}

export interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  type: string;
  zone: string;
  timestamp: string;
}

export interface WebSocketEvent<T> {
  type: string;
  data: T;
  connected_clients?: number;
  server_time?: string;
}

export interface FunnelData {
  step: string;
  value: number;
}

export interface SalespersonData {
  id: string;
  name: string;
  gmv: number;
  transactions: number;
}