import type { Vehicle } from '../types';
import { AnomalyBadge } from './AnomalyBadge';
import { StatusBadge } from './StatusBadge';

interface Props {
  vehicles: Vehicle[];
}

function formatBattery(pct: number | null): string {
  return pct !== null ? `${pct.toFixed(1)}%` : 'No data yet';
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function VehicleTable({ vehicles }: Props) {
  if (vehicles.length === 0) {
    return <p className="empty-state">No vehicles found.</p>;
  }

  const sorted = [...vehicles].sort((a, b) =>
    a.vehicle_id.localeCompare(b.vehicle_id)
  );

  return (
    <div className="vehicle-table-wrap">
      <table className="vehicle-table">
        <thead>
          <tr>
            <th>Vehicle</th>
            <th>Status</th>
            <th>Battery</th>
            <th>Last Seen</th>
            <th>Latest Anomaly</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((v) => {
            const lowBattery = v.battery_pct !== null && v.battery_pct < 15;
            return (
              <tr
                key={v.vehicle_id}
                className={v.current_status === 'fault' ? 'row--fault' : undefined}
              >
                <td className="vehicle-id">{v.vehicle_id}</td>
                <td><StatusBadge status={v.current_status} /></td>
                <td className={lowBattery ? 'cell-battery--low' : undefined}>
                  {formatBattery(v.battery_pct)}
                </td>
                <td className="cell-timestamp">{formatTimestamp(v.last_seen_at)}</td>
                <td>
                  {v.latest_anomaly
                    ? <AnomalyBadge anomaly={v.latest_anomaly} />
                    : <span className="cell-no-anomaly">—</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
