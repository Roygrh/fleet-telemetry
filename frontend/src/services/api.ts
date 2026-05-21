import type { Anomaly, FleetState, Vehicle, ZoneCount, ZoneCountResponse } from '../types';

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchVehicles(): Promise<Vehicle[]> {
  return apiFetch<Vehicle[]>('/api/vehicles');
}

export async function fetchFleetState(): Promise<FleetState> {
  return apiFetch<FleetState>('/api/fleet/state');
}

export async function fetchZoneCounts(): Promise<ZoneCount[]> {
  const data = await apiFetch<ZoneCountResponse>('/api/zones/counts');
  return data.zones;
}

export async function fetchAnomalies(): Promise<Anomaly[]> {
  return apiFetch<Anomaly[]>('/api/anomalies');
}
