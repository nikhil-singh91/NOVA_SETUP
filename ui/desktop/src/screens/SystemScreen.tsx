import React, { useEffect, useState } from 'react';
import { backendApi } from '../services/backendApi';
import { SystemStatusInfo } from '../types';
import {
  Cpu,
  Mic,
  Brain,
  Shield,
  Layers,
  AlertTriangle,
  RefreshCw,
  Terminal,
  Activity,
} from 'lucide-react';

interface SystemScreenProps {
  isBackendConnected: boolean;
}

export const SystemScreen: React.FC<SystemScreenProps> = ({ isBackendConnected }) => {
  const [systemStatus, setSystemStatus] = useState<SystemStatusInfo | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const status = await backendApi.fetchSystemStatus();
      setSystemStatus(status);
    } catch {
      setSystemStatus(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!isBackendConnected) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center text-center p-8 space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <div className="space-y-1 max-w-sm">
          <h3 className="text-base font-bold text-white">Backend Disconnected</h3>
          <p className="text-xs text-slate-400">
            Cannot fetch real subsystem telemetry. Please ensure the NOVA Python backend is running on 127.0.0.1:8765.
          </p>
        </div>
        <button
          onClick={fetchStatus}
          className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-slate-300 flex items-center gap-2 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Retry Connection</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 h-full flex flex-col p-6 overflow-y-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold font-display text-white">System Diagnostics</h2>
          <p className="text-xs text-slate-400">Live operational telemetry across NOVA subsystems</p>
        </div>
        <button
          onClick={fetchStatus}
          className="p-2 rounded-xl glass-panel text-slate-400 hover:text-indigo-300 transition-colors"
          title="Refresh Status"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Grid of Telemetry Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl">
        {/* 1. NOVA Core Card */}
        <div className="p-4 rounded-2xl glass-card space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">NOVA Core</h3>
              <p className="text-[10px] text-slate-400">Runtime Orchestrator</p>
            </div>
          </div>
          <div className="space-y-1.5 text-xs font-mono">
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Status</span>
              <span className="text-emerald-400 font-semibold">{systemStatus?.core.status || 'Active'}</span>
            </div>
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Version</span>
              <span className="text-slate-200">{systemStatus?.core.version || 'v3.5'}</span>
            </div>
          </div>
        </div>

        {/* 2. AI Providers Card */}
        <div className="p-4 rounded-2xl glass-card space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">AI Providers</h3>
              <p className="text-[10px] text-slate-400">Multi-Model Engine</p>
            </div>
          </div>
          <div className="space-y-1.5 text-xs font-mono">
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Primary Provider</span>
              <span className="text-cyan-300 font-semibold">{systemStatus?.providers.primary || 'Gemini'}</span>
            </div>
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Active Model</span>
              <span className="text-slate-200">{systemStatus?.providers.active_model || 'gemini-2.5-flash'}</span>
            </div>
          </div>
        </div>

        {/* 3. Voice System Card */}
        <div className="p-4 rounded-2xl glass-card space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Mic className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Voice Pipeline</h3>
              <p className="text-[10px] text-slate-400">VAD + STT + TTS</p>
            </div>
          </div>
          <div className="space-y-1.5 text-xs font-mono">
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">STT Model</span>
              <span className="text-slate-200">{systemStatus?.voice.stt_model || 'Faster-Whisper'}</span>
            </div>
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">TTS Synthesis</span>
              <span className="text-slate-200">{systemStatus?.voice.tts_voice || 'af_heart (Kokoro)'}</span>
            </div>
          </div>
        </div>

        {/* 4. Memory & Context Card */}
        <div className="p-4 rounded-2xl glass-card space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-xl bg-violet-500/15 border border-violet-500/30 flex items-center justify-center text-violet-400">
              <Brain className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Memory Manager</h3>
              <p className="text-[10px] text-slate-400">Episodic & Semantic Store</p>
            </div>
          </div>
          <div className="space-y-1.5 text-xs font-mono">
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Status</span>
              <span className="text-emerald-400 font-semibold">{systemStatus?.memory.available ? 'Ready' : 'Unavailable'}</span>
            </div>
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Stored Facts</span>
              <span className="text-slate-200">{systemStatus?.memory.stored_entries_count ?? 0} items</span>
            </div>
          </div>
        </div>

        {/* 5. Mac Control Card */}
        <div className="p-4 rounded-2xl glass-card space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Mac Control</h3>
              <p className="text-[10px] text-slate-400">Hardware & UI Interaction</p>
            </div>
          </div>
          <div className="space-y-1.5 text-xs font-mono">
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Accessibility</span>
              <span className="text-emerald-400 font-semibold">{systemStatus?.mac_control.accessibility_granted ? 'Trusted' : 'Missing'}</span>
            </div>
            <div className="flex justify-between p-2 rounded-lg bg-black/20">
              <span className="text-slate-400">Subsystem</span>
              <span className="text-slate-200">Active</span>
            </div>
          </div>
        </div>

        {/* 6. Security Permissions Summary */}
        <div className="p-4 rounded-2xl glass-card space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Permissions</h3>
              <p className="text-[10px] text-slate-400">macOS Privacy Access</p>
            </div>
          </div>
          <div className="space-y-1 text-[11px] font-mono">
            {Object.entries(systemStatus?.permissions || {}).map(([key, val]) => (
              <div key={key} className="flex justify-between p-1.5 rounded bg-black/20">
                <span className="text-slate-400 capitalize">{key.replace('_', ' ')}</span>
                <span className={val === 'GRANTED' ? 'text-emerald-400' : 'text-amber-400'}>{val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CLI Diagnostic Reference */}
      <div className="p-4 rounded-xl glass-panel max-w-5xl space-y-2 border-white/5">
        <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
          <Terminal className="w-3.5 h-3.5 text-indigo-400" />
          <span>RUN TERMINAL DIAGNOSTIC</span>
        </div>
        <code className="block text-xs font-mono text-indigo-300 bg-black/40 p-2.5 rounded-lg border border-white/5">
          python main.py doctor
        </code>
      </div>
    </div>
  );
};
