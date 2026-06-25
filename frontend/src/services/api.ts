import type { Anomaly, FleetState, TeleoperationSession, Vehicle, ZoneCount, ZoneCountResponse } from '../types';

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

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchTeleoperationSessions(): Promise<TeleoperationSession[]> {
  return apiFetch<TeleoperationSession[]>('/api/teleoperation/sessions');
}

export async function createTeleoperationSession(
  vehicle_id: string,
  reason?: string,
): Promise<TeleoperationSession> {
  return apiPost<TeleoperationSession>('/api/teleoperation/sessions', { vehicle_id, reason });
}

export async function claimTeleoperationSession(
  session_id: string,
  operator_id: string = 'operator-1',
): Promise<TeleoperationSession> {
  return apiPost<TeleoperationSession>(
    `/api/teleoperation/sessions/${session_id}/claim`,
    { operator_id },
  );
}

export async function releaseTeleoperationSession(
  session_id: string,
): Promise<TeleoperationSession> {
  return apiPost<TeleoperationSession>(`/api/teleoperation/sessions/${session_id}/release`);
}
