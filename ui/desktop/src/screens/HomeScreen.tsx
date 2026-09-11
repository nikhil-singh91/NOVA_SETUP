import React, { useState } from 'react';
import { NovaAvatar } from '../components/Avatar/NovaAvatar';
import { AvatarState } from '../types';
import { Send, FolderPlus, Code, Compass, Play, FileText, AlertCircle } from 'lucide-react';

interface HomeScreenProps {
  avatarState: AvatarState;
  statusMessage: string;
  onSubmitCommand: (text: string) => void;
  onNavigateTab?: (tab: any) => void;
}

export const HomeScreen: React.FC<HomeScreenProps> = ({
  avatarState,
  statusMessage,
  onSubmitCommand,
}) => {
  const [inputText, setInputText] = useState('');

  // Dynamic time of day greeting
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const quickActions = [
    { label: 'Open VS Code', icon: Code, command: 'Open VS Code' },
    { label: 'Create DSA Folder', icon: FolderPlus, command: 'Create a folder called DSA on Desktop' },
    { label: 'Play Music', icon: Play, command: 'Play Kesariya' },
    { label: 'Write Leave App', icon: FileText, command: 'Write an application for college leave' },
    { label: 'Search Web', icon: Compass, command: 'Search Google for Python tutorials' },
    { label: 'Explain Screen Error', icon: AlertCircle, command: 'Explain this error' },
  ];

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSubmitCommand(inputText.trim());
    setInputText('');
  };

  return (
    <div className="flex-1 h-full flex flex-col justify-between p-8 overflow-y-auto max-w-4xl mx-auto w-full">
      {/* Top Greeting & Centerpiece Avatar */}
      <div className="flex-1 flex flex-col items-center justify-center text-center space-y-5 my-auto">
        {/* Compact Bounded Centerpiece Avatar (max 220px) */}
        <div className="py-2">
          <NovaAvatar state={avatarState} size="hero" />
        </div>

        {/* Dynamic Greeting */}
        <div className="space-y-1.5">
          <h2 className="text-2xl md:text-3xl font-bold font-display tracking-tight text-white">
            {getGreeting()}, <span className="bg-gradient-to-r from-indigo-300 via-purple-300 to-cyan-300 bg-clip-text text-transparent">Nikhil</span>
          </h2>
          <p className="text-xs md:text-sm text-slate-400 max-w-md mx-auto">
            {statusMessage || 'How can I help you today?'}
          </p>
        </div>

        {/* Quick Capabilities Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5 w-full max-w-xl pt-2">
          {quickActions.map((action, idx) => {
            const Icon = action.icon;
            return (
              <button
                key={idx}
                onClick={() => onSubmitCommand(action.command)}
                className="flex items-center gap-2.5 p-3 rounded-xl glass-card text-left text-xs font-medium text-slate-300 hover:text-indigo-200 transition-all duration-150 border border-white/5 hover:border-indigo-500/30 group"
              >
                <div className="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-indigo-500/20 text-slate-400 group-hover:text-indigo-300 transition-colors shrink-0">
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <span className="truncate">{action.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Command Composer */}
      <form onSubmit={handleSend} className="w-full max-w-2xl mx-auto relative pt-4">
        <div className="relative flex items-center">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Ask NOVA anything... (e.g. 'Open VS Code' or 'Create a C++ project')"
            className="w-full pl-5 pr-24 py-3.5 rounded-2xl glass-panel text-sm text-white placeholder-slate-500 focus:border-indigo-500/50 transition-colors shadow-lg border border-white/10"
          />
          <div className="absolute right-2 flex items-center gap-1.5">
            <button
              type="submit"
              disabled={!inputText.trim()}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 disabled:opacity-30 disabled:cursor-not-allowed text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-indigo-500/20"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Run</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};
