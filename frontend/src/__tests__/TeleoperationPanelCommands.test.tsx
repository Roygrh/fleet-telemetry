/**
 * Focused tests for the command button guard logic in TeleoperationPanel.
 *
 * These tests mock the useTeleoperation hook entirely so we can control
 * activeSessionId, wsStatus, and session status precisely — something that
 * cannot be done with the real hook without a live WebSocket.
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TeleoperationPanel } from '../components/TeleoperationPanel';
import { useTeleoperation } from '../hooks/useTeleoperation';

vi.mock('../hooks/useTeleoperation');

// API module is imported by the component via the hook; mock to satisfy module
// resolution even though the mocked hook never calls it.
vi.mock('../services/api', () => ({
  fetchTeleoperationSessions: vi.fn().mockResolvedValue([]),
  createTeleoperationSession: vi.fn(),
  claimTeleoperationSession: vi.fn(),
  releaseTeleoperationSession: vi.fn(),
}));

const BASE_SESSION = {
  id: 1,
  session_id: 'aaaa-bbbb-cccc-dddd',
  vehicle_id: 'v-01',
  status: 'active' as const,
  operator_id: 'operator-1',
  reason: null,
  created_at: '2026-06-24T00:00:00Z',
  claimed_at: '2026-06-24T00:01:00Z',
  released_at: null,
  last_command: null,
  last_sensor_payload: null,
};

function buildHook(overrides: Record<string, unknown> = {}) {
  return {
    sessions: [BASE_SESSION],
    activeSessionId: 'aaaa-bbbb-cccc-dddd',
    sensorData: null,
    wsStatus: 'connected' as const,
    error: null,
    createSession: vi.fn(),
    claimSession: vi.fn(),
    releaseSession: vi.fn(),
    connectOperator: vi.fn(),
    disconnectOperator: vi.fn(),
    sendCommand: vi.fn(),
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('TeleoperationPanel — command button guards', () => {
  beforeEach(() => {
    vi.mocked(useTeleoperation).mockReturnValue(buildHook());
  });

  it('command buttons are enabled when WS is connected and session is active', () => {
    render(<TeleoperationPanel />);
    expect(screen.getByText('Forward')).not.toBeDisabled();
    expect(screen.getByText('Stop')).not.toBeDisabled();
  });

  it('command buttons are disabled when wsStatus is not connected', () => {
    vi.mocked(useTeleoperation).mockReturnValue(buildHook({ wsStatus: 'disconnected' }));
    render(<TeleoperationPanel />);
    expect(screen.getByText('Forward')).toBeDisabled();
    expect(screen.getByText('Stop')).toBeDisabled();
  });

  it('command buttons are disabled when session status is not active', () => {
    vi.mocked(useTeleoperation).mockReturnValue(
      buildHook({ sessions: [{ ...BASE_SESSION, status: 'released' }] })
    );
    render(<TeleoperationPanel />);
    // activeSessionId still set and wsStatus connected, but session.status = released
    expect(screen.getByText('Forward')).toBeDisabled();
    expect(screen.getByText('Stop')).toBeDisabled();
  });

  it('command panel is absent after release clears activeSessionId', () => {
    vi.mocked(useTeleoperation).mockReturnValue(
      buildHook({ activeSessionId: null, wsStatus: 'disconnected' })
    );
    render(<TeleoperationPanel />);
    expect(screen.queryByText('Forward')).not.toBeInTheDocument();
    expect(screen.queryByText('Stop')).not.toBeInTheDocument();
  });
});
