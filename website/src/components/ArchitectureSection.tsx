import React, { useState } from 'react';
import { ARCHITECTURE_BRANCHES } from '../data/architectureData';
import { ArrowDown, ChevronRight } from 'lucide-react';

export const ArchitectureSection: React.FC = () => {
  const [selectedBranch, setSelectedBranch] = useState<string>('anakin-web');

  const active = ARCHITECTURE_BRANCHES.find((b) => b.id === selectedBranch) || ARCHITECTURE_BRANCHES[2];

  return (
    <section id="architecture" className="py-24 relative overflow-hidden bg-[#07090e] border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            SYSTEM BLUEPRINT
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            Inside NOVA
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            A modular, clean-architecture autonomous system on macOS. Spoken intent flows through
            context resolution and task planning, branching out to specialized native and web execution adapters.
          </p>
        </div>

        {/* Architecture Pipeline Flow Diagram */}
        <div className="max-w-5xl mx-auto mb-16">
          {/* Top Pipeline: Intake & Planning */}
          <div className="p-4 sm:p-6 rounded-2xl bg-white/[0.02] border border-white/10 mb-6">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block mb-3 text-center sm:text-left">
              INTAKE, INTENT & REASONING PIPELINE
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
              {[
                { title: 'USER', subtitle: 'Voice or Terminal' },
                { title: 'VOICE / TEXT', subtitle: 'Whisper STT (Local)' },
                { title: 'INTENT + GOAL', subtitle: 'IntentMatcher NLP' },
                { title: 'CONTEXT RESOLUTION', subtitle: 'RecentInteractionContext' },
                { title: 'TASK PLANNER', subtitle: 'Capability Router' },
              ].map((node, i) => (
                <div
                  key={node.title}
                  className="p-3 rounded-xl bg-[#0e121d] border border-white/10 text-center relative group hover:border-cyan-500/40 transition-colors"
                >
                  <span className="text-[9px] font-mono text-cyan-400 block">STEP 0{i + 1}</span>
                  <span className="text-xs font-mono font-bold text-white block mt-0.5">{node.title}</span>
                  <span className="text-[10px] text-slate-400 block mt-0.5">{node.subtitle}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-center my-3">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-mono text-xs">
              <ArrowDown className="w-3.5 h-3.5 animate-bounce" />
              <span>DYNAMIC SUBSYSTEM DISPATCH</span>
            </div>
          </div>

          {/* Middle: 5 Execution Branches */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
            {ARCHITECTURE_BRANCHES.map((branch) => {
              const isSelected = selectedBranch === branch.id;
              return (
                <button
                  key={branch.id}
                  onClick={() => setSelectedBranch(branch.id)}
                  className={`p-4 rounded-2xl text-left transition-all duration-300 flex flex-col justify-between ${
                    isSelected
                      ? `bg-gradient-to-b ${branch.color} shadow-xl scale-102`
                      : 'bg-white/[0.02] border-white/10 hover:bg-white/[0.05] text-slate-400'
                  } border`}
                >
                  <div>
                    <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-white/5 font-semibold text-slate-300 block w-fit mb-2">
                      {branch.badge}
                    </span>
                    <h4 className="text-sm font-bold text-white mb-1">
                      {branch.name}
                    </h4>
                  </div>
                  <span className="text-[10px] font-mono text-cyan-400 mt-3 flex items-center gap-1">
                    <span>{isSelected ? 'ACTIVE' : 'INSPECT'}</span>
                    <ChevronRight className="w-3 h-3" />
                  </span>
                </button>
              );
            })}
          </div>

          {/* Branch Inspector Panel */}
          <div className="p-6 rounded-2xl bg-[#0d111b] border border-cyan-500/30 mb-8 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 mb-4 border-b border-white/10">
              <div className="flex items-center gap-3">
                <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                  {active.badge}
                </span>
                <h4 className="text-lg font-bold text-white">{active.name}</h4>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Verified Codebase Modules
              </span>
            </div>

            <p className="text-sm text-slate-300 mb-4">
              {active.role}
            </p>

            <div>
              <span className="text-xs font-mono uppercase text-slate-400 block mb-2">
                Underlying Implementations:
              </span>
              <div className="flex flex-wrap gap-2">
                {active.submodules.map((mod, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/10 text-xs font-mono text-cyan-300"
                  >
                    {mod}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="flex justify-center my-3">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono text-xs">
              <ArrowDown className="w-3.5 h-3.5" />
              <span>EXECUTION VERIFICATION & FEEDBACK</span>
            </div>
          </div>

          {/* Bottom Pipeline: Observe → Verify → Response */}
          <div className="p-4 sm:p-6 rounded-2xl bg-white/[0.02] border border-white/10">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-center">
              <div className="p-3.5 rounded-xl bg-[#0e121d] border border-white/10">
                <span className="text-[10px] font-mono text-cyan-400 block font-bold">STAGE 01</span>
                <span className="text-sm font-mono font-bold text-white block mt-0.5">OBSERVE</span>
                <span className="text-xs text-slate-400 block mt-1">Read process exit code, DOM tree, or Anakin 5-source payload</span>
              </div>
              <div className="p-3.5 rounded-xl bg-emerald-950/20 border border-emerald-500/30">
                <span className="text-[10px] font-mono text-emerald-400 block font-bold">STAGE 02</span>
                <span className="text-sm font-mono font-bold text-emerald-300 block mt-0.5">VERIFY</span>
                <span className="text-xs text-slate-400 block mt-1">Confirm task ground truth before claiming success</span>
              </div>
              <div className="p-3.5 rounded-xl bg-[#0e121d] border border-white/10">
                <span className="text-[10px] font-mono text-cyan-400 block font-bold">STAGE 03</span>
                <span className="text-sm font-mono font-bold text-white block mt-0.5">RESPONSE</span>
                <span className="text-xs text-slate-400 block mt-1">Companion voice synthesis & terminal activity feed update</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
