import React, { useState } from 'react';
import { ActivityItem } from '../types';
import { Activity, Terminal, Info } from 'lucide-react';

interface ActivityScreenProps {
  activities: ActivityItem[];
}

export const ActivityScreen: React.FC<ActivityScreenProps> = ({ activities }) => {
  const [debugMode, setDebugMode] = useState(false);

  return (
    <div className="flex-1 h-full flex flex-col p-6 overflow-y-auto space-y-6">
      {/* Header Bar */}
      <div className="flex items-center justify-between pb-4 border-b border-white/5">
        <div>
          <h2 className="text-lg font-bold font-display text-white">Activity Log</h2>
          <p className="text-xs text-slate-400">Live timeline of actions, subsystem events & decisions</p>
        </div>

        {/* Debug Mode Toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDebugMode(!debugMode)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono transition-colors border ${
              debugMode
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                : 'glass-panel text-slate-400 border-white/5 hover:text-slate-200'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>DEBUG MODE {debugMode ? 'ON' : 'OFF'}</span>
          </button>
        </div>
      </div>

      {/* Activity Timeline List */}
      <div className="space-y-3 max-w-3xl">
        {activities.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-center text-slate-500 py-12 space-y-2">
            <Activity className="w-8 h-8 text-cyan-500/30 animate-pulse" />
            <p className="text-sm">No activity recorded in this session yet.</p>
          </div>
        ) : (
          activities.map((item, idx) => (
            <div
              key={idx}
              className="p-4 rounded-xl glass-card border-white/5 flex items-start gap-3.5 hover:border-cyan-500/30 transition-all"
            >
              <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 shrink-0 mt-0.5">
                <Info className="w-3.5 h-3.5" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-slate-200">{item.message}</p>
                  <span className="text-[10px] font-mono text-slate-500 shrink-0 ml-2">
                    {new Date(item.timestamp * 1000).toLocaleTimeString()}
                  </span>
                </div>

                {debugMode && (
                  <div className="mt-2 pt-2 border-t border-white/5 flex items-center gap-3 text-[10px] font-mono text-slate-400">
                    <span>EVENT: {item.event_type}</span>
                    <span>AVATAR: {item.avatar_state}</span>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
