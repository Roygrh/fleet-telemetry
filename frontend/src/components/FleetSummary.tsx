import type { FleetState, VehicleStatus } from '../types';

interface Props {
  state: FleetState;
}

interface CardProps {
  label: string;
  value: number;
  modifier?: VehicleStatus;
}

function SummaryCard({ label, value, modifier }: CardProps) {
  const cls = modifier ? `summary-card summary-card--${modifier}` : 'summary-card';
  return (
    <div className={cls}>
      <span className="summary-card__value">{value}</span>
      <span className="summary-card__label">{label}</span>
    </div>
  );
}

export function FleetSummary({ state }: Props) {
  return (
    <div className="fleet-summary">
      <SummaryCard label="Idle"     value={state.idle}     modifier="idle" />
      <SummaryCard label="Moving"   value={state.moving}   modifier="moving" />
      <SummaryCard label="Charging" value={state.charging} modifier="charging" />
      <SummaryCard label="Fault"    value={state.fault}    modifier="fault" />
      <SummaryCard label="Total"    value={state.total} />
    </div>
  );
}
