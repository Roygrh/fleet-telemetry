import type { Anomaly } from '../types';

interface Props {
  anomaly: Anomaly;
}

function toLabel(anomalyType: string): string {
  return anomalyType
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function AnomalyBadge({ anomaly }: Props) {
  const cls = anomaly.anomaly_type.toLowerCase();
  const ts = new Date(anomaly.timestamp).toLocaleString();

  return (
    <span
      className={`anomaly-badge anomaly--${cls}`}
      title={`${anomaly.description} — ${ts}`}
    >
      {toLabel(anomaly.anomaly_type)}
    </span>
  );
}
