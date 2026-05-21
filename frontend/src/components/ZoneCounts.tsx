import type { ZoneCount } from '../types';

interface Props {
  zones: ZoneCount[];
}

function isChargingZone(zoneId: string): boolean {
  return zoneId.startsWith('charging_');
}

function formatZoneName(zoneId: string): string {
  return zoneId.replace(/_/g, ' ');
}

export function ZoneCounts({ zones }: Props) {
  if (zones.length === 0) {
    return <p className="empty-state">No zone data.</p>;
  }

  const sorted = [...zones].sort(
    (a, b) => b.entry_count - a.entry_count || a.zone_id.localeCompare(b.zone_id)
  );

  return (
    <div className="zone-table-wrap">
      <table className="zone-table">
        <thead>
          <tr>
            <th>Zone</th>
            <th style={{ textAlign: 'right' }}>Entries</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((z) => (
            <tr
              key={z.zone_id}
              className={isChargingZone(z.zone_id) ? 'row--charging' : undefined}
            >
              <td className="zone-name">{formatZoneName(z.zone_id)}</td>
              <td className="zone-count">{z.entry_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
