/**
 * Type definitions for NOVA UI V1.
 */

export type AvatarState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'planning'
  | 'executing'
  | 'verifying'
  | 'speaking'
  | 'success'
  | 'confused'
  | 'error'
  | 'offline';

export type ScreenTab =
  | 'home'
  | 'chat'
  | 'voice'
  | 'tasks'
  | 'activity'
  | 'system'
  | 'settings';

export interface PrivacyState {
  microphone_active: boolean;
  screen_observation_active: boolean;
  screen_recording_active: boolean;
  camera_active: boolean;
  task_executing: boolean;
}

export interface UIEventPayload {
  event_id: string;
  event_type: string;
  timestamp: number;
  avatar_state: AvatarState;
  message: string;
  task_id?: string;
  data?: Record<string, any>;
  privacy?: PrivacyState;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'nova';
  text: string;
  timestamp: number;
  status?: string;
  actionCard?: {
    title: string;
    description: string;
    type?: 'app' | 'file' | 'browser' | 'system' | 'provider';
  };
}

export interface TaskStep {
  step_index: number;
  capability_name: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  error?: string;
}

export interface ActiveTask {
  task_id: string;
  goal: string;
  status: 'planning' | 'running' | 'completed' | 'failed' | 'cancelled';
  steps: TaskStep[];
  current_step_index: number;
  total_steps: number;
}

export interface ActivityItem {
  timestamp: number;
  event_type: string;
  avatar_state: AvatarState;
  message: string;
}

export interface SystemStatusInfo {
  core: {
    status: string;
    version: string;
    uptime_seconds?: number;
    tasks_executed?: number;
  };
  providers: {
    primary: string;
    active_model: string;
    fallback_available: boolean;
    available_providers: string[];
  };
  voice: {
    available: boolean;
    vad_engine: string;
    stt_model: string;
    tts_voice: string;
    is_listening: boolean;
  };
  memory: {
    available: boolean;
    stored_entries_count: number;
    short_term_count?: number;
    long_term_count?: number;
  };
  mac_control: {
    available: boolean;
    accessibility_granted: boolean;
  };
  permissions: {
    accessibility: 'GRANTED' | 'MISSING' | 'UNKNOWN';
    microphone: 'GRANTED' | 'MISSING' | 'UNKNOWN';
    screen_recording: 'GRANTED' | 'MISSING' | 'UNKNOWN';
    camera: 'GRANTED' | 'MISSING' | 'UNKNOWN';
    automation: 'GRANTED' | 'MISSING' | 'UNKNOWN';
  };
}
