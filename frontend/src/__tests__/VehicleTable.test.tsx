import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { VehicleTable } from '../components/VehicleTable';
import type { Vehicle } from '../types';

function makeVehicle(overrides: Partial<Vehicle> = {}): Vehicle {
  return {
    vehicle_id: 'v-01',
    current_status: 'idle',
    battery_pct: 75.0,
    last_seen_at: null,
    latest_anomaly: null,
    ...overrides,
  };
}

describe('VehicleTable', () => {
  it('shows empty state when no vehicles', () => {
    render(<VehicleTable vehicles={[]} />);
    expect(screen.getByText('No vehicles found.')).toBeInTheDocument();
  });

  it('renders table headers', () => {
    render(<VehicleTable vehicles={[makeVehicle()]} />);
    expect(screen.getByText('Vehicle')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Battery')).toBeInTheDocument();
    expect(screen.getByText('Last Seen')).toBeInTheDocument();
    expect(screen.getByText('Latest Anomaly')).toBeInTheDocument();
  });

  it('renders vehicle ID', () => {
    render(<VehicleTable vehicles={[makeVehicle({ vehicle_id: 'v-07' })]} />);
    expect(screen.getByText('v-07')).toBeInTheDocument();
  });

  it('formats battery percentage with one decimal', () => {
    render(<VehicleTable vehicles={[makeVehicle({ battery_pct: 80.5 })]} />);
    expect(screen.getByText('80.5%')).toBeInTheDocument();
  });

  it('shows placeholder when battery is null', () => {
    render(<VehicleTable vehicles={[makeVehicle({ battery_pct: null })]} />);
    expect(screen.getByText('No data yet')).toBeInTheDocument();
  });

  it('sorts vehicles alphabetically by vehicle_id', () => {
    const vehicles = [
      makeVehicle({ vehicle_id: 'v-03' }),
      makeVehicle({ vehicle_id: 'v-01' }),
      makeVehicle({ vehicle_id: 'v-02' }),
    ];
    render(<VehicleTable vehicles={vehicles} />);
    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('v-01');
    expect(rows[2]).toHaveTextContent('v-02');
    expect(rows[3]).toHaveTextContent('v-03');
  });

  it('shows dash placeholder when no anomaly', () => {
    // Provide a non-null last_seen_at so the timestamp cell shows a date,
    // leaving only the anomaly cell with the '—' placeholder.
    const v = makeVehicle({ latest_anomaly: null, last_seen_at: '2024-01-01T12:00:00Z' });
    render(<VehicleTable vehicles={[v]} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('applies fault row class for fault-status vehicles', () => {
    const { container } = render(
      <VehicleTable vehicles={[makeVehicle({ current_status: 'fault' })]} />
    );
    expect(container.querySelector('.row--fault')).not.toBeNull();
  });

  it('renders anomaly badge when anomaly is present', () => {
    const vehicle = makeVehicle({
      latest_anomaly: {
        id: 1,
        vehicle_id: 'v-01',
        timestamp: '2024-01-01T12:00:00Z',
        anomaly_type: 'LOW_BATTERY',
        description: 'Battery below threshold',
        telemetry_event_id: null,
      },
    });
    render(<VehicleTable vehicles={[vehicle]} />);
    expect(screen.getByText('Low Battery')).toBeInTheDocument();
  });
});
