import React from 'react';
import { ExternalLink, Search, Compass, MousePointer, Type, Sliders, Eye, CheckCircle2 } from 'lucide-react';

export const ComputerUseSection: React.FC = () => {
  const actions = [
    { name: 'OPEN', icon: ExternalLink, desc: 'Launch native apps (Chrome, Safari, Terminal, Notes) via macOS system bridge' },
    { name: 'SEARCH', icon: Search, desc: 'Query live web engines with Anakin API or spotlight native documents' },
    { name: 'NAVIGATE', icon: Compass, desc: 'Switch browser tabs, open research URLs, and resolve deep destination links' },
    { name: 'SCROLL', icon: MousePointer, desc: 'Scroll pages smoothly to ingest long-form technical articles and product specs' },
    { name: 'TYPE', icon: Type, desc: 'Safely simulate targeted keyboard keystrokes and search queries in active apps' },
    { name: 'CONTROL', icon: Sliders, desc: 'Adjust macOS system volume, display brightness, and companion audio playback' },
    { name: 'READ', icon: Eye, desc: 'Extract web text content, normalize sources, and parse structured tables' },
    { name: 'VERIFY', icon: CheckCircle2, desc: 'Inspect window states and exit codes to ensure commands took real effect' },
  ];

  return (
    <section className="py-24 relative overflow-hidden bg-[#07090e] border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            NATIVE DESKTOP INTERFACE
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            The computer becomes actionable.
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            NOVA is designed to bridge the gap between natural language and computer interaction.
            Rather than asking you to copy-paste terminal commands or manually browse links, NOVA acts directly on macOS.
          </p>
        </div>

        {/* Action Matrix Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 max-w-5xl mx-auto">
          {actions.map((act) => {
            const Icon = act.icon;
            return (
              <div
                key={act.name}
                className="p-5 rounded-2xl bg-white/[0.02] border border-white/10 hover:border-cyan-500/30 hover:bg-[#0c101a] transition-all group"
              >
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-3 group-hover:scale-110 transition-transform">
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="font-mono text-sm font-bold text-white tracking-wider mb-1 group-hover:text-cyan-300">
                  {act.name}
                </h3>
                <p className="text-xs text-slate-400 leading-snug">
                  {act.desc}
                </p>
              </div>
            );
          })}
        </div>

        {/* Realistic Safety Callout */}
        <div className="mt-12 max-w-3xl mx-auto p-4 rounded-xl bg-white/[0.02] border border-white/10 text-center text-xs font-mono text-slate-400">
          <span className="text-cyan-400 font-bold">Safety Guarantee: </span>
          All native actions run through a SafetyGuard filter prohibiting destructive disk commands or unreviewed privilege escalation.
        </div>
      </div>
    </section>
  );
};
