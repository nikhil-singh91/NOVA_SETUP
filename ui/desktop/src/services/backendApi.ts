/**
 * Backend API Client and Real-time WebSocket Service for NOVA UI V1.
 */

import { UIEventPayload } from '../types';

const API_BASE = 'http://127.0.0.1:8765';
const WS_URL = 'ws://127.0.0.1:8765/events';

type EventListener = (event: UIEventPayload) => void;
type ConnectionStatusListener = (connected: boolean) => void;

class BackendApiService {
  private ws: WebSocket | null = null;
  private eventListeners: Set<EventListener> = new Set();
  private statusListeners: Set<ConnectionStatusListener> = new Set();
  private reconnectTimer: any = null;
  private isConnected: boolean = false;

  constructor() {
    this.connect();
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.notifyStatus(true);
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const payload: UIEventPayload = JSON.parse(event.data);
          this.notifyEvent(payload);
        } catch (err) {
          console.debug('Failed to parse WebSocket event:', err);
        }
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this.notifyStatus(false);
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.isConnected = false;
        this.notifyStatus(false);
      };
    } catch (err) {
      this.isConnected = false;
      this.notifyStatus(false);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 2500);
    }
  }

  public subscribeEvents(listener: EventListener): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  public subscribeConnectionStatus(listener: ConnectionStatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.isConnected);
    return () => this.statusListeners.delete(listener);
  }

  private notifyEvent(event: UIEventPayload): void {
    this.eventListeners.forEach((fn) => {
      try {
        fn(event);
      } catch (e) {
        console.error('Error in event subscriber:', e);
      }
    });
  }

  private notifyStatus(status: boolean): void {
    this.statusListeners.forEach((fn) => {
      try {
        fn(status);
      } catch (e) {
        console.error('Error in status subscriber:', e);
      }
    });
  }

  public async submitCommand(text: string, source = 'chat_input'): Promise<{ success: boolean; message?: string }> {
    try {
      const resp = await fetch(`${API_BASE}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, source }),
      });
      if (resp.ok) {
        return { success: true };
      }
      return { success: false, message: 'Server rejected command.' };
    } catch (err) {
      // If HTTP server is unreachable, send fallback over WebSocket
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ text, source }));
        return { success: true };
      }
      return { success: false, message: 'Backend disconnected.' };
    }
  }

  public async cancelTasks(): Promise<{ success: boolean }> {
    try {
      const resp = await fetch(`${API_BASE}/cancel`, { method: 'POST' });
      return { success: resp.ok };
    } catch {
      return { success: false };
    }
  }

  public async triggerVoice(): Promise<{ success: boolean }> {
    try {
      const resp = await fetch(`${API_BASE}/voice/trigger`, { method: 'POST' });
      return { success: resp.ok };
    } catch {
      return { success: false };
    }
  }

  public async fetchPermissions(): Promise<Record<string, string>> {
    try {
      const resp = await fetch(`${API_BASE}/permissions`);
      if (resp.ok) {
        const data = await resp.json();
        return data.permissions || {};
      }
    } catch {
      // Fallback
    }
    return {
      microphone: 'GRANTED',
      accessibility: 'GRANTED',
      screen_recording: 'GRANTED',
      camera: 'GRANTED',
      automation: 'GRANTED',
    };
  }

  public async fetchSystemStatus(): Promise<any> {
    try {
      const resp = await fetch(`${API_BASE}/system/status`);
      if (resp.ok) {
        return await resp.json();
      }
    } catch {
      // Fallback
    }
    return null;
  }

  public async fetchHealth(): Promise<boolean> {
    try {
      const resp = await fetch(`${API_BASE}/health`);
      return resp.ok;
    } catch {
      return false;
    }
  }
}

export const backendApi = new BackendApiService();
