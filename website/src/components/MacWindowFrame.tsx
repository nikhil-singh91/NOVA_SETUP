import React from 'react';
import { Maximize2 } from 'lucide-react';

interface MacWindowFrameProps {
  title?: string;
  subtitle?: string;
  badge?: string;
  onZoom?: () => void;
  children: React.ReactNode;
  className?: string;
}

export const MacWindowFrame: React.FC<MacWindowFrameProps> = ({
  title = 'NOVA Operations Control Center',
  subtitle = 'Terminal Cockpit — macOS',
  badge = 'ACTIVE',
  onZoom,
  children,
  className = ''
}) => {
  return (
    <div className={`relative rounded-xl overflow-hidden border border-white/10 bg-[#0c0f17] shadow-2xl shadow-cyan-950/20 group ${className}`}>
      {/* macOS Chrome Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#121622] border-b border-white/5 select-none">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-[#ff5f56] border border-[#e0443e]/40 transition-transform group-hover:scale-110" />
          <div className="w-3 h-3 rounded-full bg-[#ffbd2e] border border-[#dea123]/40 transition-transform group-hover:scale-110" />
          <div className="w-3 h-3 rounded-full bg-[#27c93f] border border-[#1aab29]/40 transition-transform group-hover:scale-110" />
          <span className="ml-3 text-xs font-mono text-slate-400 font-medium tracking-wide flex items-center gap-2">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            {title}
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-3">
          <span className="text-[11px] font-mono text-slate-500">{subtitle}</span>
          {badge && (
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold tracking-wider uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              {badge}
            </span>
          )}
          {onZoom && (
            <button
              onClick={onZoom}
              className="p-1 text-slate-400 hover:text-white hover:bg-white/10 rounded transition-colors"
              title="Expand full resolution"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Window Body */}
      <div className="relative overflow-hidden">
        {children}
      </div>
    </div>
  );
};
