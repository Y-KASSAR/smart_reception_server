import { useEffect, useState } from "react";
import { wsClient } from "../services/websocket";

/**
 * Hook that subscribes to one WebSocket event type and tracks connection status.
 *
 * Usage:
 *   const { connected, last } = useWebSocketEvent<AlertPayload>("alert_push");
 */
export function useWebSocketEvent<T = any>(eventName: string) {
  const [last, setLast] = useState<T | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const offEvent = wsClient.on(eventName, (data) => setLast(data as T));
    const offStatus = wsClient.onStatus(setConnected);
    return () => {
      offEvent();
      offStatus();
    };
  }, [eventName]);

  return { connected, last };
}

/**
 * Hook returning a rolling buffer (most-recent-first) of events.
 */
export function useWebSocketEventLog<T = any>(eventName: string, maxItems = 100) {
  const [items, setItems] = useState<T[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const offEvent = wsClient.on(eventName, (data) => {
      setItems((prev) => {
        const next = [data as T, ...prev];
        return next.length > maxItems ? next.slice(0, maxItems) : next;
      });
    });
    const offStatus = wsClient.onStatus(setConnected);
    return () => {
      offEvent();
      offStatus();
    };
  }, [eventName, maxItems]);

  return { connected, items, clear: () => setItems([]) };
}
