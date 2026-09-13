import React from 'react';
import { Sparkles, ExternalLink, Compass } from 'lucide-react';

export const HackathonSection: React.FC = () => {
  return (
    <section className="py-20 relative overflow-hidden bg-gradient-to-b from-[#080b12] to-[#0c101a] border-t border-cyan-500/20">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-mono font-bold tracking-wider uppercase mb-6">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>HACKATHON SUBMISSION</span>
        </div>

        <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mb-4">
          Built for Anakin Forge 2026
        </h2>

        <p className="text-lg sm:text-xl text-slate-300 font-medium max-w-2xl mx-auto mb-6 leading-relaxed">
          “NOVA is built around the idea that AI agents should not stop at conversation.
          They should be able to read, reason, act, and verify.”
        </p>

        <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto mb-8">
          Created by Nikhil Singh as an autonomous computer-use companion that leverages Anakin’s Live Web Intelligence
          API to ground actions in real-world facts.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <a
            href="https://anakin.io/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-mono font-semibold text-cyan-300 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 transition-all shadow-lg shadow-cyan-950/40"
          >
            <Compass className="w-4 h-4 text-cyan-400" />
            <span>Visit Anakin Official (anakin.io)</span>
            <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
          </a>
        </div>
      </div>
    </section>
  );
};
