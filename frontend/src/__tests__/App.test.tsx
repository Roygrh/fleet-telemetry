import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetData } from '../hooks/useFleetData';

vi.mock('../hooks/useFleetData', () => ({
  useFleetData: vi.fn(),
}));

import App from '../App';
import { useFleetData } from '../hooks/useFleetData';

const mockUseFleetData = vi.mocked(useFleetData);

const base: FleetData = {
  vehicles: [],
  fleetState: null,
  zoneCounts: [],
  anomalies: [],
  lastUpdated: null,
  loading: false,
  error: null,
};

const fleetState = { idle: 10, moving: 20, charging: 5, fault: 3, total: 50 };

describe('App', () => {
  beforeEach(() => {
    mockUseFleetData.mockReturnValue(base);
  });

  it('shows loading state while first poll is in progress', () => {
    mockUseFleetData.mockReturnValue({ ...base, loading: true });
    render(<App />);
    expect(screen.getByText('Loading fleet data…')).toBeInTheDocument();
  });

  it('shows full-page error when first poll fails with no data', () => {
    mockUseFleetData.mockReturnValue({ ...base, error: 'Network error', fleetState: null });
    render(<App />);
    expect(screen.getByText('Could not load fleet data')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('shows dashboard header when data is available', () => {
    mockUseFleetData.mockReturnValue({ ...base, fleetState });
    render(<App />);
    expect(screen.getByText('Fleet Telemetry Dashboard')).toBeInTheDocument();
  });

  it('shows fleet summary cards when fleet state is loaded', () => {
    mockUseFleetData.mockReturnValue({ ...base, fleetState });
    render(<App />);
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('shows inline error banner when a subsequent poll fails but data is still visible', () => {
    mockUseFleetData.mockReturnValue({ ...base, error: 'Connection lost', fleetState });
    render(<App />);
    expect(screen.getByText(/Connection lost/)).toBeInTheDocument();
    // Dashboard remains visible
    expect(screen.getByText('Fleet Telemetry Dashboard')).toBeInTheDocument();
  });

  it('shows last updated time when data has been received', () => {
    const lastUpdated = new Date('2024-01-01T12:00:00');
    mockUseFleetData.mockReturnValue({ ...base, fleetState, lastUpdated });
    render(<App />);
    expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
  });

  it('shows Vehicles panel', () => {
    mockUseFleetData.mockReturnValue({ ...base, fleetState });
    render(<App />);
    expect(screen.getByText(/Vehicles/)).toBeInTheDocument();
  });

  it('shows Zone Counts panel', () => {
    mockUseFleetData.mockReturnValue({ ...base, fleetState });
    render(<App />);
    expect(screen.getByText('Zone Counts')).toBeInTheDocument();
  });
});
