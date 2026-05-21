import { useEffect, useRef } from 'react';

/**
 * Calls `callback` immediately on mount, then once every `intervalMs`.
 * Uses a ref so the interval is never rescheduled when the callback identity
 * changes — only when the interval duration itself changes.
 */
export function usePolling(callback: () => void, intervalMs: number): void {
  const savedCallback = useRef<() => void>(callback);

  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    savedCallback.current();
    const id = setInterval(() => savedCallback.current(), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}
