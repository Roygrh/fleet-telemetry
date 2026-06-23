import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../hooks/usePolling', () => ({
  usePolling: vi.fn(),
}));

import { useFleetData } from '../hooks/useFleetData';
import { usePolling } from '../hooks/usePolling';

const mockUsePolling = vi.mocked(usePolling);

const mockVehicles = [
  {
    vehicle_id: 'v-01',
    current_status: 'idle' as const,
    battery_pct: 80,
    last_seen_at: null,
    latest_anomaly: null,
  },
];
const mockFleetState = { idle: 1, moving: 0, charging: 0, fault: 0, total: 1 };
const mockZoneCountsResponse = { zones: [{ zone_id: 'dock_a', entry_count: 5 }] };
const mockAnomalies: never[] = [];

function stubFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      let data: unknown;
      if (url.includes('/api/vehicles')) data = mockVehicles;
      else if (url.includes('/api/fleet/state')) data = mockFleetState;
      else if (url.includes('/api/zones/counts')) data = mockZoneCountsResponse;
      else if (url.includes('/api/anomalies')) data = mockAnomalies;
      else data = {};
      return Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
    }),
  );
}

function stubFetchFailure() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockRejectedValue(new Error('Network failure')),
  );
}

describe('useFleetData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stubFetch();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('starts in loading state before the first poll completes', () => {
    renderHook(() => useFleetData());
    const { result } = renderHook(() => useFleetData());
    expect(result.current.loading).toBe(true);
    expect(result.current.fleetState).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('transitions out of loading after a successful poll', async () => {
    const { result } = renderHook(() => useFleetData());
    const poll = mockUsePolling.mock.calls[mockUsePolling.mock.calls.length - 1][0] as () => Promise<void>;

    await act(async () => {
      await poll();
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.fleetState).toEqual(mockFleetState);
    expect(result.current.vehicles).toEqual(mockVehicles);
    expect(result.current.error).toBeNull();
  });

  it('populates zone counts from the API response', async () => {
    const { result } = renderHook(() => useFleetData());
    const poll = mockUsePolling.mock.calls[mockUsePolling.mock.calls.length - 1][0] as () => Promise<void>;

    await act(async () => {
      await poll();
    });

    expect(result.current.zoneCounts).toEqual(mockZoneCountsResponse.zones);
  });

  it('sets lastUpdated after a successful poll', async () => {
    const { result } = renderHook(() => useFleetData());
    const poll = mockUsePolling.mock.calls[mockUsePolling.mock.calls.length - 1][0] as () => Promise<void>;

    await act(async () => {
      await poll();
    });

    expect(result.current.lastUpdated).toBeInstanceOf(Date);
  });

  it('captures error message when fetch fails', async () => {
    stubFetchFailure();
    const { result } = renderHook(() => useFleetData());
    const poll = mockUsePolling.mock.calls[mockUsePolling.mock.calls.length - 1][0] as () => Promise<void>;

    await act(async () => {
      await poll();
    });

    expect(result.current.error).toBe('Network failure');
    expect(result.current.loading).toBe(false);
  });
});
