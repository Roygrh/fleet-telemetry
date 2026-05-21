import './App.css';
import { ErrorState } from './components/ErrorState';
import { FleetSummary } from './components/FleetSummary';
import { LoadingState } from './components/LoadingState';
import { VehicleTable } from './components/VehicleTable';
import { ZoneCounts } from './components/ZoneCounts';
import { useFleetData } from './hooks/useFleetData';

function App() {
  const { vehicles, fleetState, zoneCounts, lastUpdated, loading, error } = useFleetData();

  // First poll not yet complete — nothing to show yet.
  if (loading) return <LoadingState />;

  // First poll failed — no data at all, show full-page error.
  if (error && !fleetState) return <ErrorState message={error} />;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Fleet Telemetry Dashboard</h1>
        {lastUpdated && (
          <span className="last-updated">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </header>

      <main className="app-main">
        {/* Inline banner for subsequent poll failures — keeps stale data visible */}
        {error && (
          <div className="error-banner">
            <span>⚠</span> {error}
          </div>
        )}

        {fleetState && <FleetSummary state={fleetState} />}

        <div className="content-grid">
          <div className="panel">
            <div className="panel__header">Vehicles ({vehicles.length})</div>
            <VehicleTable vehicles={vehicles} />
          </div>

          <div className="panel">
            <div className="panel__header">Zone Counts</div>
            <ZoneCounts zones={zoneCounts} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
