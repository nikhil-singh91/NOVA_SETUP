import React, { useEffect, useState } from 'react';
import { backendApi } from '../services/backendApi';
import { CheckCircle2, AlertCircle, Terminal } from 'lucide-react';

export const PermissionsScreen: React.FC = () => {
  const [permissions, setPermissions] = useState<Record<string, string>>({
    accessibility: 'UNKNOWN',
    microphone: 'GRANTED',
    screen_recording: 'GRANTED',
    camera: 'GRANTED',
    automation: 'GRANTED',
  });

  useEffect(() => {
    backendApi.fetchPermissions().then((perms) => {
      setPermissions((prev) => ({ ...prev, ...perms }));
    });
  }, []);

  const permissionList = [
    {
      id: 'accessibility',
      name: 'Accessibility (AXIsProcessTrusted)',
      status: permissions.accessibility || 'UNKNOWN',
      reason: 'Required for mouse clicking coordinates, typing keystrokes, and tracking the active window.',
    },
    {
      id: 'microphone',
      name: 'Microphone Access',
      status: permissions.microphone || 'GRANTED',
      reason: 'Required for real-time voice listening, Silero VAD, and Whisper transcription.',
    },
    {
      id: 'screen_recording',
      name: 'Screen Recording',
      status: permissions.screen_recording || 'GRANTED',
      reason: 'Required for Computer Agent V2 on-demand OCR inspection and screen video recording.',
    },
    {
      id: 'camera',
      name: 'Camera Access',
      status: permissions.camera || 'GRANTED',
      reason: 'Required for Photo Booth viewfinder and photo snapshot capture.',
    },
    {
      id: 'automation',
      name: 'Automation / AppleEvents',
      status: permissions.automation || 'GRANTED',
      reason: 'Required for Google Chrome, Safari, Finder, and System Events hardware automation.',
    },
  ];

  return (
    <div className="flex-1 h-full flex flex-col p-6 overflow-y-auto space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-white/5">
        <h2 className="text-lg font-bold font-display text-white">Permissions Dashboard</h2>
        <p className="text-xs text-slate-400">macOS security & hardware sensor privacy status</p>
      </div>

      {/* Permissions List */}
      <div className="space-y-3 max-w-3xl">
        {permissionList.map((perm) => {
          const isGranted = perm.status === 'GRANTED';
          return (
            <div
              key={perm.id}
              className="p-4 rounded-xl glass-card border-white/5 flex items-start justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-200">{perm.name}</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{perm.reason}</p>
              </div>

              {/* Status Badge */}
              <div className="shrink-0">
                <span
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold ${
                    isGranted
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  }`}
                >
                  {isGranted ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <AlertCircle className="w-3.5 h-3.5 text-amber-400" />}
                  <span>{perm.status}</span>
                </span>
              </div>
            </div>
          );
        })}

        {/* Verification Command Box */}
        <div className="p-4 rounded-xl bg-white/5 border border-white/5 space-y-2 mt-6">
          <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>CLI DIAGNOSTIC COMMAND</span>
          </div>
          <code className="block text-xs font-mono text-cyan-300 bg-black/40 p-2.5 rounded-lg">
            python main.py doctor
          </code>
        </div>
      </div>
    </div>
  );
};
