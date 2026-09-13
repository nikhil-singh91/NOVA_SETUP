import React from 'react';
import { ArrowDown, Terminal } from 'lucide-react';

export const ContextEngineSection: React.FC = () => {
  return (
    <section className="py-24 relative overflow-hidden bg-[#080b12] border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            RECENT INTERACTION CONTEXT
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            Context changes everything.
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            NOVA maintains task context across conversational turns. Pronouns and relative references
            such as <span className="text-cyan-300 font-mono">"in this tab"</span>, <span className="text-cyan-300 font-mono">"that result"</span>,
            or <span className="text-cyan-300 font-mono">"compare the first two"</span> are resolved into the active task state without forcing you to repeat previous instructions.
          </p>
        </div>

        {/* Multi-Turn Context Resolution Walkthrough */}
        <div className="max-w-4xl mx-auto p-6 sm:p-8 rounded-3xl bg-[#0b0e17] border border-cyan-500/30 shadow-2xl space-y-6">
          {/* Turn 1 */}
          <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-full bg-cyan-500/20 text-cyan-400 text-xs font-mono font-bold flex items-center justify-center shrink-0">
                1
              </span>
              <div>
                <span className="text-[10px] font-mono text-slate-500 block">USER INSTRUCTION</span>
                <span className="text-sm sm:text-base font-semibold text-white font-mono">“Open Chrome.”</span>
              </div>
            </div>
            <div className="text-xs font-mono text-cyan-400 sm:text-right">
              <span className="text-slate-500 block text-[10px]">NOVA RESOLUTION</span>
              Launches Google Chrome via MacControl & records active PID
            </div>
          </div>

          <div className="flex justify-center">
            <ArrowDown className="w-4 h-4 text-cyan-500/60" />
          </div>

          {/* Turn 2 */}
          <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-full bg-cyan-500/20 text-cyan-400 text-xs font-mono font-bold flex items-center justify-center shrink-0">
                2
              </span>
              <div>
                <span className="text-[10px] font-mono text-slate-500 block">USER INSTRUCTION</span>
                <span className="text-sm sm:text-base font-semibold text-white font-mono">
                  “In <span className="text-cyan-300 underline decoration-cyan-400">this tab</span>, search for laptops under ₹50,000.”
                </span>
              </div>
            </div>
            <div className="text-xs font-mono text-cyan-400 sm:text-right">
              <span className="text-slate-500 block text-[10px]">NOVA RESOLUTION</span>
              Binds "this tab" to active Chrome window; invokes Anakin live search
            </div>
          </div>

          <div className="flex justify-center">
            <ArrowDown className="w-4 h-4 text-cyan-500/60" />
          </div>

          {/* Turn 3 */}
          <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
            <div className="flex items-center gap-3">
              <span className="w-7 h-7 rounded-full bg-cyan-400 text-black text-xs font-mono font-bold flex items-center justify-center shrink-0">
                3
              </span>
              <div>
                <span className="text-[10px] font-mono text-cyan-400 block font-bold">FOLLOW-UP INSTRUCTION</span>
                <span className="text-sm sm:text-base font-bold text-white font-mono">
                  “Compare <span className="text-cyan-300 underline decoration-cyan-400">the first two</span>.”
                </span>
              </div>
            </div>
            <div className="text-xs font-mono text-emerald-400 sm:text-right">
              <span className="text-slate-400 block text-[10px]">ANAPHORIC BINDING</span>
              Extracts items [0] and [1] from cached Anakin WebSource list & runs comparison
            </div>
          </div>

          {/* Memory Engine Architecture Badge */}
          <div className="mt-4 p-4 rounded-xl bg-[#101422] border border-white/10 flex items-center gap-3 text-xs font-mono text-slate-300">
            <Terminal className="w-4 h-4 text-cyan-400 shrink-0" />
            <span>
              Backed by <span className="text-white font-bold">RecentInteractionContext</span> + local JSON persistent memory store with zero third-party telemetry leaks.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};
