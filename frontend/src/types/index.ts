export type VehicleStatus = 'idle' | 'moving' | 'charging' | 'fault';
export type TeleoperationStatus = 'requested' | 'claimed' | 'active' | 'released' | 'completed' | 'failed';

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

export interface VehicleSensorPayload {
  vehicle_id: string;
  mode: string;
  speed_mps: number;
  battery_pct: number;
  obstacle_distance_m: number;
  connection_quality: string;
  camera_frame_label: string;
  last_command_echo: string | null;
}

export interface TeleoperationSession {
  id: number;
  session_id: string;
  vehicle_id: string;
  status: TeleoperationStatus;
  operator_id: string | null;
  reason: string | null;
  created_at: string;
  claimed_at: string | null;
  released_at: string | null;
  last_command: string | null;
  last_sensor_payload: VehicleSensorPayload | null;
}
