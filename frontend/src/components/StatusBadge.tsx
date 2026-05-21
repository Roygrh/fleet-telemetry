import type { VehicleStatus } from '../types';

interface Props {
  status: VehicleStatus;
}

const LABEL: Record<VehicleStatus, string> = {
  idle: 'Idle',
  moving: 'Moving',
  charging: 'Charging',
  fault: 'Fault',
};

export function StatusBadge({ status }: Props) {
  return (
    <span className={`status-badge status--${status}`}>
      {LABEL[status]}
    </span>
  );
}
