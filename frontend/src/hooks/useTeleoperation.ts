import { useCallback, useEffect, useRef, useState } from 'react';
import {
  claimTeleoperationSession,
  createTeleoperationSession,
  fetchTeleoperationSessions,
  releaseTeleoperationSession,
} from '../services/api';
import type { TeleoperationSession, VehicleSensorPayload } from '../types';

export type WsStatus = 'disconnected' | 'connecting' | 'connected' | 'vehicle_not_connected';

interface UseTeleoperationResult {
  sessions: TeleoperationSession[];
  activeSessionId: string | null;
  sensorData: VehicleSensorPayload | null;
  wsStatus: WsStatus;
  error: string | null;
  createSession: (vehicleId: string, reason?: string) => Promise<void>;
  claimSession: (sessionId: string) => Promise<void>;
  releaseSession: (sessionId: string) => Promise<void>;
  connectOperator: (sessionId: string) => void;
  disconnectOperator: () => void;
  sendCommand: (command: string) => void;
}

export function useTeleoperation(): UseTeleoperationResult {
  const [sessions, setSessions] = useState<TeleoperationSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sensorData, setSensorData] = useState<VehicleSensorPayload | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchTeleoperationSessions();
      setSessions(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sessions');
    }
  }, []);

  // Poll sessions every 3 seconds
  useEffect(() => {
    loadSessions();
    pollRef.current = setInterval(loadSessions, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadSessions]);

  const createSession = useCallback(async (vehicleId: string, reason?: string) => {
    try {
      const session = await createTeleoperationSession(vehicleId, reason);
      setSessions(prev => [session, ...prev]);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create session');
    }
  }, []);

  const claimSession = useCallback(async (sessionId: string) => {
    try {
      await claimTeleoperationSession(sessionId);
      await loadSessions();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to claim session');
    }
  }, [loadSessions]);

  // Declared before releaseSession so it can appear in its deps array without a
  // temporal dead zone error (const is not hoisted like function declarations).
  const disconnectOperator = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setWsStatus('disconnected');
    setActiveSessionId(null);
    setSensorData(null);
  }, []);

  const releaseSession = useCallback(async (sessionId: string) => {
    try {
      await releaseTeleoperationSession(sessionId);
      // Disconnect immediately — before loadSessions — so command buttons are
      // disabled as soon as the API confirms the release, without waiting for
      // the sessions network round-trip to complete.
      if (activeSessionId === sessionId) {
        disconnectOperator();
      }
      await loadSessions();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to release session');
    }
  }, [activeSessionId, disconnectOperator, loadSessions]);

  const connectOperator = useCallback((sessionId: string) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const url = `${protocol}//${host}:8000/ws/teleoperation/operator/${sessionId}`;

    setWsStatus('connecting');
    setActiveSessionId(sessionId);
    setSensorData(null);

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus('connected');

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string);
        if (msg.type === 'sensor_update') {
          setSensorData(msg as VehicleSensorPayload);
        } else if (msg.type === 'status' && msg.status === 'vehicle_not_connected') {
          setWsStatus('vehicle_not_connected');
        } else if (msg.type === 'session_closed') {
          // Backend closed the session (HTTP release while this WS was open).
          // Clean up immediately so command buttons disappear without a page refresh.
          setWsStatus('disconnected');
          setActiveSessionId(null);
          setSensorData(null);
          wsRef.current = null;
          ws.close();
          loadSessions();
        }
      } catch {
        // ignore unparseable messages
      }
    };

    ws.onclose = () => {
      setWsStatus('disconnected');
      wsRef.current = null;
    };

    ws.onerror = () => {
      setWsStatus('disconnected');
      setError('WebSocket connection error');
    };
  }, [loadSessions]);

  const sendCommand = useCallback((command: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command }));
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return {
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
  };
}
