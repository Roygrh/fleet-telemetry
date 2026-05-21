export type VehicleStatus = 'idle' | 'moving' | 'charging' | 'fault';

export interface Anomaly {
  id: number;
  vehicle_id: string;
  timestamp: string;
  anomaly_type: string;
  description: string;
  telemetry_event_id: number | null;
}

export interface Vehicle {
  vehicle_id: string;
  current_status: VehicleStatus;
  battery_pct: number | null;
  last_seen_at: string | null;
  latest_anomaly: Anomaly | null;
}

export interface FleetState {
  idle: number;
  moving: number;
  charging: number;
  fault: number;
  total: number;
}

export interface ZoneCount {
  zone_id: string;
  entry_count: number;
}

export interface ZoneCountResponse {
  zones: ZoneCount[];
}
