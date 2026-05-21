interface Props {
  message: string;
}

export function ErrorState({ message }: Props) {
  return (
    <div className="error-state">
      <span className="error-state__icon">⚠</span>
      <p className="error-state__title">Could not load fleet data</p>
      <p className="error-state__detail">{message}</p>
      <p className="error-state__hint">The dashboard will retry automatically.</p>
    </div>
  );
}
