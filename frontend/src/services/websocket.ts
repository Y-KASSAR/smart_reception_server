/**
 * Single shared WebSocket connection to the FastAPI /ws endpoint with
 * automatic exponential-backoff reconnect. Consumers subscribe to event
 * names; multiple listeners per event are supported.
 *
 * Event shapes (set by api/routes/websocket.py):
 *   live_feed             {camera_id, frame_b64, detections, ts}
 *   detection_update      {persons, faces, tracks, ts}
 *   alert_push            {alert_id, type, severity, title, ts}
 *   guest_identified      {guest_id, name, confidence, ts}
 *   recommendation_update {guest_id, recommendations, ts}
 *   heartbeat             {ts, active_tracks, camera_status}
 *   connected             {message, ts}
 */

type Listener = (payload: any) => void;

class WSClient {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<Listener>> = new Map();
  private statusListeners: Set<(connected: boolean) => void> = new Set();
  private backoffMs = 1000;
  private maxBackoffMs = 16000;
  private shouldRun = false;
  private reconnectTimer: number | null = null;

  start() {
    this.shouldRun = true;
    this.connect();
  }

  stop() {
    this.shouldRun = false;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  on(event: string, fn: Listener): () => void {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event)!.add(fn);
    return () => this.listeners.get(event)?.delete(fn);
  }

  onStatus(fn: (connected: boolean) => void): () => void {
    this.statusListeners.add(fn);
    return () => this.statusListeners.delete(fn);
  }

  private setStatus(connected: boolean) {
    this.statusListeners.forEach((fn) => fn(connected));
  }

  private connect() {
    if (!this.shouldRun) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws`;
    try {
      this.ws = new WebSocket(url);
    } catch (e) {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.backoffMs = 1000;
      this.setStatus(true);
    };

    this.ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data);
        const eventName = data.event ?? "unknown";
        const subs = this.listeners.get(eventName);
        if (subs) subs.forEach((fn) => fn(data));
        // Also dispatch a wildcard "*" if any listener wants every message
        const wildcards = this.listeners.get("*");
        if (wildcards) wildcards.forEach((fn) => fn(data));
      } catch (e) {
        // Non-JSON message — ignore
      }
    };

    this.ws.onclose = () => {
      this.setStatus(false);
      this.ws = null;
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      // onclose will fire too; let it handle reconnection
    };
  }

  private scheduleReconnect() {
    if (!this.shouldRun) return;
    const delay = this.backoffMs;
    this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  send(text: string) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(text);
  }
}

export const wsClient = new WSClient();
