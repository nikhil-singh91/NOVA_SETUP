import React from 'react';
import { NovaAvatar } from '../components/Avatar/NovaAvatar';
import { AvatarState } from '../types';
import { Mic, Square, Volume2, Radio, CheckCircle2 } from 'lucide-react';

interface VoiceScreenProps {
  avatarState: AvatarState;
  userTranscript: string;
  novaTranscript: string;
  isListening: boolean;
  onToggleVoice: () => void;
  onCancelTask: () => void;
  isTaskRunning: boolean;
}

export const VoiceScreen: React.FC<VoiceScreenProps> = ({
  avatarState,
  userTranscript,
  novaTranscript,
  isListening,
  onToggleVoice,
  onCancelTask,
  isTaskRunning,
}) => {
  return (
    <div className="flex-1 h-full flex flex-col items-center justify-between p-8 text-center overflow-y-auto max-w-3xl mx-auto w-full">
      {/* Top Header */}
      <div className="space-y-1">
        <h2 className="text-xl font-bold font-display text-white">Voice Hub</h2>
        <div className="flex items-center justify-center gap-3 text-[11px] text-slate-400 font-mono">
          <span className="flex items-center gap-1">
            <Radio className="w-3 h-3 text-indigo-400" />
            <span>STT: Faster-Whisper</span>
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Volume2 className="w-3 h-3 text-cyan-400" />
            <span>TTS: Kokoro (af_heart)</span>
          </span>
        </div>
      </div>

      {/* Centerpiece Orb & Visualizer */}
      <div className="flex flex-col items-center justify-center space-y-6 my-auto w-full">
        {/* Compact Bounded Centerpiece Avatar (max 220px) */}
        <div className="py-2">
          <NovaAvatar state={avatarState} size="hero" />
        </div>

        {/* Animated Audio Waveform */}
        <div className="flex items-center justify-center gap-1 h-10">
          {[...Array(14)].map((_, i) => (
            <div
              key={i}
              className={`w-1 rounded-full transition-all duration-150 ${
                isListening
                  ? 'bg-cyan-400 shadow-[0_0_6px_#00f0ff]'
                  : avatarState === 'speaking'
                  ? 'bg-indigo-400 shadow-[0_0_6px_#818cf8]'
                  : 'bg-slate-800 h-1.5'
              }`}
              style={{
                height: isListening || avatarState === 'speaking' ? `${Math.sin(i + Date.now() / 120) * 14 + 18}px` : '4px',
                animationDelay: `${i * 0.06}s`,
              }}
            />
          ))}
        </div>

        {/* Live Conversation Transcript Cards */}
        <div className="w-full max-w-md space-y-2.5 text-left">
          {/* User Transcript */}
          <div className="p-3.5 rounded-xl glass-card border border-white/5 space-y-1">
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
              <span>YOU (SPOKEN)</span>
            </div>
            <p className="text-xs font-medium text-slate-200 min-h-[1.25rem]">
              {userTranscript ? `"${userTranscript}"` : isListening ? 'Listening for speech...' : 'Press microphone to speak or say "NOVA..."'}
            </p>
          </div>

          {/* NOVA Spoken Response */}
          {novaTranscript && (
            <div className="p-3.5 rounded-xl glass-card border border-indigo-500/20 bg-indigo-500/5 space-y-1">
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-indigo-300">
                <CheckCircle2 className="w-3 h-3 text-indigo-400" />
                <span>NOVA RESPONSE</span>
              </div>
              <p className="text-xs font-medium text-slate-200 leading-relaxed">
                {novaTranscript}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Controls */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={onToggleVoice}
          className={`px-5 py-2.5 rounded-xl flex items-center gap-2.5 font-semibold text-xs transition-all shadow-md ${
            isListening
              ? 'bg-rose-500 text-white shadow-rose-500/30 animate-pulse'
              : 'bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white shadow-indigo-500/20'
          }`}
        >
          <Mic className="w-4 h-4" />
          <span>{isListening ? 'Stop Listening' : 'Push To Talk'}</span>
        </button>

        {isTaskRunning && (
          <button
            onClick={onCancelTask}
            className="px-4 py-2.5 rounded-xl glass-panel text-rose-300 hover:bg-rose-500/20 border-rose-500/30 flex items-center gap-2 text-xs font-medium transition-colors"
          >
            <Square className="w-3.5 h-3.5 fill-rose-400 text-rose-400" />
            <span>Cancel</span>
          </button>
        )}
      </div>
    </div>
  );
};
