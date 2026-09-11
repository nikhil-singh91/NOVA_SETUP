import React from 'react';
import { Cpu, Mic, Server } from 'lucide-react';

export const SettingsScreen: React.FC = () => {
  return (
    <div className="flex-1 h-full flex flex-col p-6 overflow-y-auto space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-white/5">
        <h2 className="text-lg font-bold font-display text-white">System Settings</h2>
        <p className="text-xs text-slate-400">Configuration, multi-provider model routing & voice parameters</p>
      </div>

      <div className="space-y-6 max-w-3xl">
        {/* AI Provider Configuration Card */}
        <div className="p-5 rounded-2xl glass-card border-white/10 space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Multi-Provider AI Routing</h3>
              <p className="text-xs text-slate-400">Task-based dynamic selection across Gemini, Groq, Cerebras, OpenRouter</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2 text-xs font-mono">
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-1">
              <span className="text-slate-500">FAST / REASONING</span>
              <p className="text-cyan-300 font-semibold">Groq / Gemini 2.5 Flash</p>
            </div>
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-1">
              <span className="text-slate-500">VISION / OCR</span>
              <p className="text-indigo-300 font-semibold">Gemini 2.5 Pro Vision</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 italic">API keys configured securely via local .env file.</p>
        </div>

        {/* Voice V2 Engine Card */}
        <div className="p-5 rounded-2xl glass-card border-white/10 space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Mic className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Voice V2 Pipeline</h3>
              <p className="text-xs text-slate-400">Silero VAD + Faster-Whisper + Kokoro TTS</p>
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-white/5">
              <span className="text-slate-300">Continuous Wake Word</span>
              <span className="font-mono text-cyan-400">ENABLED ("NOVA")</span>
            </div>
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-white/5">
              <span className="text-slate-300">Speech Synthesis Voice</span>
              <span className="font-mono text-slate-300">af_heart (Natural Female)</span>
            </div>
          </div>
        </div>

        {/* Backend Local Gateway */}
        <div className="p-5 rounded-2xl glass-card border-white/10 space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Server className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Local Gateway Server</h3>
              <p className="text-xs text-slate-400">Loopback binding on 127.0.0.1:8765</p>
            </div>
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl bg-white/5 text-xs font-mono">
            <span className="text-slate-400">HOST & PORT</span>
            <span className="text-emerald-400">http://127.0.0.1:8765</span>
          </div>
        </div>
      </div>
    </div>
  );
};
