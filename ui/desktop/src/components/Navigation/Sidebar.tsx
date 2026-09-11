import React from 'react';
import { ScreenTab } from '../../types';
import {
  Home,
  MessageSquare,
  Mic,
  Layers,
  Activity,
  Server,
  Settings,
  Sparkles,
} from 'lucide-react';

interface SidebarProps {
  currentTab: ScreenTab;
  onTabChange: (tab: ScreenTab) => void;
  isBackendConnected: boolean;
  isMicrophoneActive: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  isBackendConnected,
  isMicrophoneActive,
}) => {
  const navItems: { id: ScreenTab; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'voice', label: 'Voice', icon: Mic },
    { id: 'tasks', label: 'Tasks', icon: Layers },
    { id: 'activity', label: 'Activity', icon: Activity },
    { id: 'system', label: 'System', icon: Server },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="w-60 h-full flex flex-col justify-between glass-panel border-r border-white/5 p-4 select-none shrink-0 z-20">
      {/* Top Branding & Status */}
      <div>
        <div className="flex items-center gap-3 px-2 py-3 mb-5 border-b border-white/5 pb-4">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 via-indigo-600 to-purple-600 flex items-center justify-center shadow-md shadow-indigo-500/20">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <h1 className="text-base font-bold font-display tracking-wider text-white">
                NOVA
              </h1>
              <span
                className={`w-2 h-2 rounded-full ${
                  isBackendConnected ? 'bg-emerald-400 shadow-[0_0_8px_#10b981]' : 'bg-rose-500 shadow-[0_0_8px_#ef4444]'
                }`}
                title={isBackendConnected ? 'Backend Connected' : 'Backend Disconnected'}
              />
            </div>
            <p className="text-[10px] text-slate-400 font-mono tracking-wider">AI ASSISTANT</p>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 text-left ${
                  isActive
                    ? 'bg-indigo-500/20 text-indigo-200 border border-indigo-500/30 shadow-sm font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
                {isActive && (
                  <span className="ml-auto w-1 h-1 rounded-full bg-indigo-400 shadow-[0_0_6px_#818cf8]" />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Area */}
      <div className="pt-3 border-t border-white/5 space-y-2 px-1">
        {/* Mic & Backend Status Badges */}
        <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
          <div className="flex items-center gap-1.5">
            <Mic className={`w-3.5 h-3.5 ${isMicrophoneActive ? 'text-cyan-400 animate-pulse' : 'text-slate-500'}`} />
            <span className={isMicrophoneActive ? 'text-cyan-300' : 'text-slate-500'}>
              {isMicrophoneActive ? 'LISTENING' : 'MIC IDLE'}
            </span>
          </div>
          <span className={isBackendConnected ? 'text-emerald-400' : 'text-rose-400'}>
            {isBackendConnected ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>

        <button
          onClick={() => onTabChange('settings')}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-400 hover:text-slate-200 text-xs transition-colors"
        >
          <Settings className="w-3.5 h-3.5" />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
};
