import React from 'react';
import { PrivacyState } from '../../types';
import { Mic, Eye, Video, Camera, Square, Shield } from 'lucide-react';

interface TopBarProps {
  privacy: PrivacyState;
  onCancelTask: () => void;
  isTaskRunning: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  privacy,
  onCancelTask,
  isTaskRunning,
}) => {
  return (
    <header className="h-14 border-b border-white/5 px-6 flex items-center justify-between glass-panel z-10">
      {/* Title & Context */}
      <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
        <Shield className="w-3.5 h-3.5 text-cyan-400" />
        <span>NOVA DESKTOP ENVIRONMENT</span>
      </div>

      {/* Privacy Sensor Badges & Task Actions */}
      <div className="flex items-center gap-3">
        {/* Active Microphone Indicator */}
        {privacy.microphone_active && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-mono animate-pulse">
            <Mic className="w-3 h-3 text-cyan-400" />
            <span>MIC ACTIVE</span>
          </div>
        )}

        {/* Active Screen Observation Indicator */}
        {privacy.screen_observation_active && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-mono animate-pulse">
            <Eye className="w-3 h-3 text-violet-400" />
            <span>OBSERVING SCREEN</span>
          </div>
        )}

        {/* Active Screen Recording Indicator */}
        {privacy.screen_recording_active && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/15 border border-rose-500/40 text-rose-300 text-xs font-mono animate-pulse">
            <Video className="w-3 h-3 text-rose-400" />
            <span>RECORDING</span>
          </div>
        )}

        {/* Active Camera Indicator */}
        {privacy.camera_active && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-mono animate-pulse">
            <Camera className="w-3 h-3 text-amber-400" />
            <span>CAMERA</span>
          </div>
        )}

        {/* Instant Cancellation Button */}
        {isTaskRunning && (
          <button
            onClick={onCancelTask}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-xs font-medium transition-colors shadow-sm"
            title="Cancel active task execution"
          >
            <Square className="w-3 h-3 text-rose-400 fill-rose-400" />
            <span>STOP TASK</span>
          </button>
        )}
      </div>
    </header>
  );
};
