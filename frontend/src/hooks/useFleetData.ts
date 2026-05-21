import { useCallback, useState } from 'react';
import { fetchAnomalies, fetchFleetState, fetchVehicles, fetchZoneCounts } from '../services/api';
import type { Anomaly, FleetState, Vehicle, ZoneCount } from '../types';
import { usePolling } from './usePolling';

export interface FleetData {
  vehicles: Vehicle[];
  fleetState: FleetState | null;
  zoneCounts: ZoneCount[];
  anomalies: Anomaly[];
  lastUpdated: Date | null;
  loading: boolean;
  error: string | null;
}

const POLL_INTERVAL_MS = 2000;

export function useFleetData(): FleetData {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [fleetState, setFleetState] = useState<FleetState | null>(null);
  const [zoneCounts, setZoneCounts] = useState<ZoneCount[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async () => {
    try {
      const [v, f, z, a] = await Promise.all([
        fetchVehicles(),
        fetchFleetState(),
        fetchZoneCounts(),
        fetchAnomalies(),
      ]);
      setVehicles(v);
      setFleetState(f);
      setZoneCounts(z);
      setAnomalies(a);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred');
    } finally {
      setLoading((prev) => (prev ? false : prev));
    }
  }, []);

  usePolling(poll, POLL_INTERVAL_MS);

  return { vehicles, fleetState, zoneCounts, anomalies, lastUpdated, loading, error };
}
