import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage, AvatarState } from '../types';
import { NovaAvatar } from '../components/Avatar/NovaAvatar';
import {
  Send,
  Mic,
  Sparkles,
  User,
  CheckCircle2,
  Clock,
  Code,
  Folder,
  Globe,
  Brain,
  Cpu,
} from 'lucide-react';

interface ChatScreenProps {
  messages: ChatMessage[];
  avatarState: AvatarState;
  onSubmitCommand: (text: string) => void;
  onTriggerVoice: () => void;
  isListening: boolean;
}

export const ChatScreen: React.FC<ChatScreenProps> = ({
  messages,
  avatarState,
  onSubmitCommand,
  onTriggerVoice,
  isListening,
}) => {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSubmitCommand(inputText.trim());
    setInputText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const renderActionIcon = (type?: string) => {
    switch (type) {
      case 'app':
        return <Code className="w-3.5 h-3.5 text-cyan-400" />;
      case 'file':
        return <Folder className="w-3.5 h-3.5 text-amber-400" />;
      case 'browser':
        return <Globe className="w-3.5 h-3.5 text-blue-400" />;
      case 'memory':
        return <Brain className="w-3.5 h-3.5 text-purple-400" />;
      default:
        return <Cpu className="w-3.5 h-3.5 text-indigo-400" />;
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col justify-between p-6 overflow-hidden max-w-4xl mx-auto w-full">
      {/* Header Bar */}
      <div className="flex items-center justify-between pb-3 border-b border-white/5 shrink-0">
        <div>
          <h2 className="text-base font-bold font-display text-white">Conversation</h2>
          <p className="text-[11px] text-slate-400">Direct interactive command & response stream</p>
        </div>
        <div className="flex items-center gap-2">
          <NovaAvatar state={avatarState} size="sm" />
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4 pr-1">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-500 space-y-3 py-12">
            <Sparkles className="w-8 h-8 text-indigo-400/40 animate-pulse" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-300">Ready for commands</p>
              <p className="text-xs text-slate-500 max-w-xs">
                Type any natural language command or press the mic button.
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.sender === 'user';
            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-2xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
              >
                {/* Avatar / Sender Icon */}
                <div
                  className={`w-7 h-7 rounded-xl flex items-center justify-center text-[11px] font-semibold shrink-0 mt-0.5 ${
                    isUser
                      ? 'bg-slate-700 text-slate-200'
                      : 'bg-gradient-to-tr from-indigo-500 to-purple-600 text-white shadow-sm'
                  }`}
                >
                  {isUser ? <User className="w-3.5 h-3.5" /> : 'N'}
                </div>

                {/* Message Content Bubble */}
                <div className="space-y-1.5 min-w-0">
                  <div
                    className={`p-3.5 rounded-2xl text-xs md:text-sm leading-relaxed ${
                      isUser
                        ? 'bg-indigo-600 text-white rounded-tr-none shadow-sm'
                        : 'glass-card text-slate-200 rounded-tl-none border-white/10'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.text}</p>

                    {/* Compact Action Card if present */}
                    {msg.actionCard && (
                      <div className="mt-2.5 p-2.5 rounded-xl bg-black/30 border border-white/5 flex items-center gap-2.5 text-xs font-mono">
                        <div className="p-1 rounded-lg bg-white/5">
                          {renderActionIcon(msg.actionCard.type)}
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-200 truncate">{msg.actionCard.title}</p>
                          <p className="text-[10px] text-slate-400 truncate">{msg.actionCard.description}</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Timestamp & Status */}
                  <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono px-1">
                    <Clock className="w-2.5 h-2.5" />
                    <span>{new Date(msg.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    {msg.status && (
                      <span className="flex items-center gap-1 text-indigo-400">
                        <CheckCircle2 className="w-2.5 h-2.5" />
                        <span>{msg.status}</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Command Composer */}
      <form onSubmit={handleSend} className="relative pt-2 shrink-0">
        <div className="relative flex items-center glass-panel rounded-2xl p-1.5 border border-white/10 shadow-lg">
          <textarea
            rows={1}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask NOVA anything... (Press Enter to send, Shift+Enter for new line)"
            className="w-full pl-3 pr-24 py-2 bg-transparent text-xs md:text-sm text-white placeholder-slate-500 resize-none focus:outline-none max-h-24"
          />
          <div className="absolute right-2 flex items-center gap-1.5">
            <button
              type="button"
              onClick={onTriggerVoice}
              className={`p-2 rounded-xl border transition-colors ${
                isListening
                  ? 'bg-rose-500 text-white border-rose-400 animate-pulse'
                  : 'bg-white/5 text-slate-400 hover:text-indigo-300 hover:bg-white/10 border-white/5'
              }`}
              title="Voice Push-To-Talk"
            >
              <Mic className="w-3.5 h-3.5" />
            </button>
            <button
              type="submit"
              disabled={!inputText.trim()}
              className="p-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 disabled:opacity-30 disabled:cursor-not-allowed text-white transition-all shadow-md shadow-indigo-500/20"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};
