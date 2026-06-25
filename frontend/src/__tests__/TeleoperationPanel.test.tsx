import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { TeleoperationPanel } from '../components/TeleoperationPanel';

// Mock the API service so the component doesn't hit the network.
// The factory must be self-contained (no module-level variable refs) because
// vi.mock is hoisted before const declarations.
vi.mock('../services/api', () => ({
  fetchTeleoperationSessions: vi.fn().mockResolvedValue([]),
  createTeleoperationSession: vi.fn().mockResolvedValue({
    id: 1,
    session_id: 'aaaa-bbbb-cccc-dddd',
    vehicle_id: 'v-01',
    status: 'requested',
    operator_id: null,
    reason: null,
    created_at: '2026-06-24T00:00:00Z',
    claimed_at: null,
    released_at: null,
    last_command: null,
    last_sensor_payload: null,
  }),
  claimTeleoperationSession: vi.fn().mockResolvedValue({
    id: 1,
    session_id: 'aaaa-bbbb-cccc-dddd',
    vehicle_id: 'v-01',
    status: 'claimed',
    operator_id: 'operator-1',
    reason: null,
    created_at: '2026-06-24T00:00:00Z',
    claimed_at: '2026-06-24T00:01:00Z',
    released_at: null,
    last_command: null,
    last_sensor_payload: null,
  }),
  releaseTeleoperationSession: vi.fn().mockResolvedValue({}),
}));

// Minimal WebSocket mock
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => { this.onclose?.(); });
}

let originalWebSocket: typeof WebSocket;

beforeEach(() => {
  originalWebSocket = globalThis.WebSocket;
  // @ts-expect-error mock
  globalThis.WebSocket = MockWebSocket;
});

afterEach(() => {
  globalThis.WebSocket = originalWebSocket;
  vi.clearAllMocks();
});

describe('TeleoperationPanel', () => {
  it('renders the panel header', async () => {
    render(<TeleoperationPanel />);
    expect(screen.getByText('Teleoperation')).toBeInTheDocument();
  });

  it('renders the vehicle selector', async () => {
    render(<TeleoperationPanel />);
    expect(screen.getByLabelText('Vehicle selector')).toBeInTheDocument();
  });

  it('renders the Request Session button', async () => {
    render(<TeleoperationPanel />);
    expect(screen.getByText('Request Session')).toBeInTheDocument();
  });

  it('renders the reason input field', async () => {
    render(<TeleoperationPanel />);
    expect(screen.getByLabelText('Reason')).toBeInTheDocument();
  });

  it('shows empty state when no sessions exist', async () => {
    render(<TeleoperationPanel />);
    await waitFor(() => {
      expect(screen.getByText(/No teleoperation sessions/)).toBeInTheDocument();
    });
  });

  it('renders claimed status badge when a session is claimed', async () => {
    const { fetchTeleoperationSessions } = await import('../services/api');
    vi.mocked(fetchTeleoperationSessions).mockResolvedValueOnce([
      {
        id: 1,
        session_id: 'aaaa-bbbb-cccc-dddd',
        vehicle_id: 'v-01',
        status: 'claimed',
        operator_id: 'operator-1',
        reason: null,
        created_at: '2026-06-24T00:00:00Z',
        claimed_at: '2026-06-24T00:01:00Z',
        released_at: null,
        last_command: null,
        last_sensor_payload: null,
      },
    ]);

    render(<TeleoperationPanel />);
    await waitFor(() => {
      expect(screen.getByText('claimed')).toBeInTheDocument();
    });
  });

  it('command panel only appears after operator WS connects', async () => {
    // Forward/Backward/etc. are rendered only after connectOperator() sets
    // activeSessionId. Without a live WS session, they are absent.
    render(<TeleoperationPanel />);
    expect(screen.queryByText('Forward')).not.toBeInTheDocument();
    expect(screen.queryByText('Stop')).not.toBeInTheDocument();
  });

  it('renders WS status badge as disconnected initially', async () => {
    render(<TeleoperationPanel />);
    expect(screen.getByText('disconnected')).toBeInTheDocument();
  });

  it('renders released status badge when a session is released', async () => {
    const { fetchTeleoperationSessions } = await import('../services/api');
    vi.mocked(fetchTeleoperationSessions).mockResolvedValueOnce([
      {
        id: 1,
        session_id: 'aaaa-bbbb-cccc-dddd',
        vehicle_id: 'v-01',
        status: 'released',
        operator_id: 'operator-1',
        reason: null,
        created_at: '2026-06-24T00:00:00Z',
        claimed_at: '2026-06-24T00:01:00Z',
        released_at: '2026-06-24T00:05:00Z',
        last_command: null,
        last_sensor_payload: null,
      },
    ]);

    render(<TeleoperationPanel />);
    await waitFor(() => {
      expect(screen.getByText('released')).toBeInTheDocument();
    });
    // Released sessions have no action buttons
    expect(screen.queryByText('Claim')).not.toBeInTheDocument();
    expect(screen.queryByText('Connect')).not.toBeInTheDocument();
    expect(screen.queryByText('Release')).not.toBeInTheDocument();
  });
});
