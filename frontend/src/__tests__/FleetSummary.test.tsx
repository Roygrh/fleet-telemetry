import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FleetSummary } from '../components/FleetSummary';
import type { FleetState } from '../types';

const state: FleetState = { idle: 15, moving: 20, charging: 8, fault: 3, total: 50 };

describe('FleetSummary', () => {
  it('renders all five summary cards', () => {
    render(<FleetSummary state={state} />);
    expect(screen.getByText('Idle')).toBeInTheDocument();
    expect(screen.getByText('Moving')).toBeInTheDocument();
    expect(screen.getByText('Charging')).toBeInTheDocument();
    expect(screen.getByText('Fault')).toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
  });

  it('displays correct counts', () => {
    render(<FleetSummary state={state} />);
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
  });

  it('renders zero counts without error', () => {
    const zeros: FleetState = { idle: 0, moving: 0, charging: 0, fault: 0, total: 0 };
    render(<FleetSummary state={zeros} />);
    const zeroEls = screen.getAllByText('0');
    expect(zeroEls).toHaveLength(5);
  });
});
