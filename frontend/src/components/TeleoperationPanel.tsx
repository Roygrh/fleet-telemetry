import { useState } from 'react';
import { useTeleoperation } from '../hooks/useTeleoperation';
import type { TeleoperationSession } from '../types';

const VEHICLE_IDS = Array.from({ length: 50 }, (_, i) => `v-${String(i + 1).padStart(2, '0')}`);
const COMMANDS = ['forward', 'backward', 'left', 'right', 'stop'] as const;

function statusColor(status: TeleoperationSession['status']): string {
  switch (status) {
    case 'requested':  return 'teleop-status--requested';
    case 'claimed':    return 'teleop-status--claimed';
    case 'active':     return 'teleop-status--active';
    case 'released':   return 'teleop-status--released';
    case 'completed':  return 'teleop-status--completed';
    case 'failed':     return 'teleop-status--failed';
    default:           return '';
  }
}

export function TeleoperationPanel() {
  const {
    sessions,
    activeSessionId,
    sensorData,
    wsStatus,
    error,
    createSession,
    claimSession,
    releaseSession,
    connectOperator,
    disconnectOperator,
    sendCommand,
  } = useTeleoperation();

  const [selectedVehicle, setSelectedVehicle] = useState('v-01');
  const [reason, setReason] = useState('');

  // Commands are only permitted when the WS is connected AND the DB-side session
  // status is still 'active'. This provides a second layer of protection:
  // even if the WS lingers open briefly after release, the stale polled status
  // will disable the buttons on the next render.
  const activeSession = sessions.find(s => s.session_id === activeSessionId);
  const canSendCommand = wsStatus === 'connected' && activeSession?.status === 'active';

  const handleCreate = async () => {
    await createSession(selectedVehicle, reason || undefined);
    setReason('');
  };

  return (
    <div className="panel">
      <div className="panel__header">
        Teleoperation
        <span className={`teleop-ws-badge teleop-ws-badge--${wsStatus}`}>
          {wsStatus.replace('_', ' ')}
        </span>
      </div>

      <div className="teleop-body">
        {error && <div className="teleop-error">{error}</div>}

        {/* Session creation */}
        <div className="teleop-create">
          <select
            value={selectedVehicle}
            onChange={e => setSelectedVehicle(e.target.value)}
            className="teleop-select"
            aria-label="Vehicle selector"
          >
            {VEHICLE_IDS.map(vid => (
              <option key={vid} value={vid}>{vid}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Reason (optional)"
            value={reason}
            onChange={e => setReason(e.target.value)}
            className="teleop-input"
            aria-label="Reason"
          />
          <button onClick={handleCreate} className="teleop-btn teleop-btn--primary">
            Request Session
          </button>
        </div>

        {/* Session list */}
        {sessions.length > 0 && (
          <table className="teleop-table">
            <thead>
              <tr>
                <th>Vehicle</th>
                <th>Status</th>
                <th>Operator</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.session_id} className={activeSessionId === s.session_id ? 'teleop-row--active' : ''}>
                  <td className="vehicle-id">{s.vehicle_id}</td>
                  <td>
                    <span className={`teleop-status-badge ${statusColor(s.status)}`}>
                      {s.status}
                    </span>
                  </td>
                  <td>{s.operator_id ?? '—'}</td>
                  <td className="teleop-actions">
                    {s.status === 'requested' && (
                      <button
                        onClick={() => claimSession(s.session_id)}
                        className="teleop-btn teleop-btn--claim"
                      >
                        Claim
                      </button>
                    )}
                    {(s.status === 'claimed' || s.status === 'active') && activeSessionId !== s.session_id && (
                      <button
                        onClick={() => connectOperator(s.session_id)}
                        className="teleop-btn teleop-btn--connect"
                      >
                        Connect
                      </button>
                    )}
                    {s.status === 'active' && activeSessionId === s.session_id && (
                      <button
                        onClick={disconnectOperator}
                        className="teleop-btn teleop-btn--disconnect"
                      >
                        Disconnect
                      </button>
                    )}
                    {(s.status === 'requested' || s.status === 'claimed' || s.status === 'active') && (
                      <button
                        onClick={() => releaseSession(s.session_id)}
                        className="teleop-btn teleop-btn--release"
                      >
                        Release
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {sessions.length === 0 && (
          <div className="empty-state">No teleoperation sessions. Request one above.</div>
        )}

        {/* Active control panel */}
        {activeSessionId && (
          <div className="teleop-control-panel">
            <div className="teleop-control-panel__title">
              Control — session {activeSessionId.slice(0, 8)}…
            </div>

            <div className="teleop-commands" aria-label="Command buttons">
              {COMMANDS.map(cmd => (
                <button
                  key={cmd}
                  onClick={() => sendCommand(cmd)}
                  disabled={!canSendCommand}
                  className={`teleop-cmd teleop-cmd--${cmd}`}
                >
                  {cmd.charAt(0).toUpperCase() + cmd.slice(1)}
                </button>
              ))}
            </div>

            {sensorData && (
              <div className="teleop-sensor-feed">
                <div className="teleop-sensor-feed__title">Sensor Feed</div>
                <div className="teleop-sensor-grid">
                  <span className="teleop-sensor-label">Mode</span>
                  <span className="teleop-sensor-value">{sensorData.mode}</span>

                  <span className="teleop-sensor-label">Speed</span>
                  <span className="teleop-sensor-value">{sensorData.speed_mps} m/s</span>

                  <span className="teleop-sensor-label">Battery</span>
                  <span className={`teleop-sensor-value ${sensorData.battery_pct < 20 ? 'cell-battery--low' : ''}`}>
                    {sensorData.battery_pct}%
                  </span>

                  <span className="teleop-sensor-label">Obstacle</span>
                  <span className="teleop-sensor-value">{sensorData.obstacle_distance_m} m</span>

                  <span className="teleop-sensor-label">Signal</span>
                  <span className="teleop-sensor-value">{sensorData.connection_quality}</span>

                  <span className="teleop-sensor-label">Camera</span>
                  <span className="teleop-sensor-value">{sensorData.camera_frame_label?.replace('_', ' ')}</span>

                  <span className="teleop-sensor-label">Last cmd</span>
                  <span className="teleop-sensor-value">{sensorData.last_command_echo ?? '—'}</span>
                </div>
              </div>
            )}

            {!sensorData && wsStatus === 'connected' && (
              <div className="teleop-sensor-feed">
                <span className="teleop-waiting">Waiting for vehicle sensor data…</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
