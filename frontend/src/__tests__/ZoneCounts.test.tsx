import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ZoneCounts } from '../components/ZoneCounts';
import type { ZoneCount } from '../types';

describe('ZoneCounts', () => {
  it('shows empty state when no zones', () => {
    render(<ZoneCounts zones={[]} />);
    expect(screen.getByText('No zone data.')).toBeInTheDocument();
  });

  it('renders table headers', () => {
    const zones: ZoneCount[] = [{ zone_id: 'dock_a', entry_count: 5 }];
    render(<ZoneCounts zones={zones} />);
    expect(screen.getByText('Zone')).toBeInTheDocument();
    expect(screen.getByText('Entries')).toBeInTheDocument();
  });

  it('formats zone IDs by replacing underscores with spaces', () => {
    const zones: ZoneCount[] = [{ zone_id: 'dock_bay_1', entry_count: 3 }];
    render(<ZoneCounts zones={zones} />);
    expect(screen.getByText('dock bay 1')).toBeInTheDocument();
  });

  it('sorts zones by entry count descending', () => {
    const zones: ZoneCount[] = [
      { zone_id: 'zone_low', entry_count: 2 },
      { zone_id: 'zone_high', entry_count: 100 },
      { zone_id: 'zone_mid', entry_count: 50 },
    ];
    render(<ZoneCounts zones={zones} />);
    const rows = screen.getAllByRole('row');
    // rows[0] is the header row; data rows follow
    expect(rows[1]).toHaveTextContent('zone high');
    expect(rows[2]).toHaveTextContent('zone mid');
    expect(rows[3]).toHaveTextContent('zone low');
  });

  it('renders entry counts', () => {
    const zones: ZoneCount[] = [{ zone_id: 'area_1', entry_count: 42 }];
    render(<ZoneCounts zones={zones} />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });
});
