import React from 'react';
import { Mic, GitMerge, ListTree, Laptop, Globe, Compass, Sliders, ShieldCheck } from 'lucide-react';

export const WhatIsNova: React.FC = () => {
  const pillars = [
    { icon: Mic, title: 'Voice Interaction', desc: 'Whisper STT with continuous listening & companion speech feedback' },
    { icon: GitMerge, title: 'Contextual Understanding', desc: 'RecentInteractionContext resolves follow-ups like "this tab" or "that result"' },
    { icon: ListTree, title: 'Task Planning', desc: 'Decomposes complex human intents into deterministic action steps' },
    { icon: Laptop, title: 'Computer Control', desc: 'Direct macOS system automation, application launches, and key commands' },
    { icon: Globe, title: 'Browser Interaction', desc: 'Chrome and Safari navigation, tab switching, and web session management' },
    { icon: Compass, title: 'Live Web Intelligence', desc: 'Anakin API integration for real-time citations and deep web research' },
    { icon: Sliders, title: 'Media & System Control', desc: 'Volume adjustment, non-repeating music playback, and hardware stats' },
    { icon: ShieldCheck, title: 'Action Verification', desc: 'Truthful verification stage to ensure actions completed in reality' },
  ];

  return (
    <section className="py-24 relative overflow-hidden bg-[#07090e]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            SYSTEM ESSENCE
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-3">
            Meet NOVA.
          </h2>
          <p className="text-xl sm:text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-sky-200 to-white mb-6">
            NOVA turns natural language into computer actions.
          </p>
          <p className="text-base sm:text-lg text-slate-300 leading-relaxed">
            Unlike chatbots that generate speculative text instructions, NOVA is built as an autonomous operator.
            It receives natural speech, determines the optimal execution subsystem, drives macOS and browser workflows,
            retrieves live web intelligence through Anakin, and verifies ground truth.
          </p>
        </div>

        {/* 8 Integrated Pillars Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {pillars.map((pillar, i) => {
            const Icon = pillar.icon;
            return (
              <div
                key={pillar.title}
                className="p-5 rounded-xl bg-white/[0.02] border border-white/10 hover:border-cyan-500/30 hover:bg-white/[0.04] transition-all group"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 group-hover:scale-110 transition-transform">
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">0{i + 1}</span>
                </div>
                <h3 className="text-base font-bold text-white mb-2 group-hover:text-cyan-300 transition-colors">
                  {pillar.title}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {pillar.desc}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
