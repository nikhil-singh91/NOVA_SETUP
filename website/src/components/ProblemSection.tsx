import React from 'react';
import { ArrowDown, Check, X, Bot, Sparkles } from 'lucide-react';

export const ProblemSection: React.FC = () => {
  return (
    <section className="py-24 relative overflow-hidden border-t border-white/5 bg-[#080b12]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            THE ARCHITECTURAL PARADIGM SHIFT
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            AI can answer.<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-sky-400">
              But can it act?
            </span>
          </h2>
          <p className="text-base sm:text-lg text-slate-400">
            Conversational chatbots trap intelligence inside a chat box. NOVA breaks free by connecting
            language understanding directly to macOS control, live web intelligence, and closed-loop verification.
          </p>
        </div>

        {/* Side-by-Side Comparison */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-5xl mx-auto">
          {/* Traditional AI */}
          <div className="p-6 sm:p-8 rounded-2xl bg-white/[0.02] border border-white/10 hover:border-red-500/20 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-6 mb-6 border-b border-white/10">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">Traditional AI Chatbot</h3>
                    <span className="text-xs text-slate-500 font-mono">Passive & Stateless Text Generator</span>
                  </div>
                </div>
                <span className="text-xs font-mono px-2 py-1 rounded bg-red-500/10 text-red-400 border border-red-500/20">
                  PASSIVE
                </span>
              </div>

              {/* Loop */}
              <div className="space-y-4 font-mono text-sm max-w-xs mx-auto text-center py-4">
                <div className="p-3 rounded-lg bg-white/[0.04] border border-white/5 text-slate-300">
                  <span className="text-xs text-slate-500 block">STEP 1</span>
                  User Asks a Question
                </div>
                <ArrowDown className="w-4 h-4 mx-auto text-slate-600" />
                <div className="p-3 rounded-lg bg-white/[0.04] border border-white/5 text-slate-300">
                  <span className="text-xs text-slate-500 block">STEP 2</span>
                  Model Generates Text Answer
                </div>
                <ArrowDown className="w-4 h-4 mx-auto text-slate-600" />
                <div className="p-3.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 font-semibold">
                  <span className="text-xs text-red-400 block">BURDEN REMAINS</span>
                  User must manually open browser, copy text, type, and do the actual work
                </div>
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-white/5 space-y-2 text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <X className="w-4 h-4 text-red-400 shrink-0" />
                <span>Zero system automation or desktop awareness</span>
              </div>
              <div className="flex items-center gap-2">
                <X className="w-4 h-4 text-red-400 shrink-0" />
                <span>Knowledge cutoff limits or static training data</span>
              </div>
              <div className="flex items-center gap-2">
                <X className="w-4 h-4 text-red-400 shrink-0" />
                <span>No ability to inspect if the recommendation worked</span>
              </div>
            </div>
          </div>

          {/* NOVA Agent */}
          <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-b from-cyan-950/20 to-surface-100 border border-cyan-500/30 hover:border-cyan-400/50 shadow-xl shadow-cyan-950/30 transition-all flex flex-col justify-between relative overflow-hidden">
            <div className="absolute top-0 right-0 w-40 h-40 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

            <div>
              <div className="flex items-center justify-between pb-6 mb-6 border-b border-cyan-500/20">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">NOVA Autonomous Agent</h3>
                    <span className="text-xs text-cyan-400 font-mono">End-to-End Computer-Use Operator</span>
                  </div>
                </div>
                <span className="text-xs font-mono px-2 py-1 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                  AUTONOMOUS
                </span>
              </div>

              {/* Loop */}
              <div className="space-y-3 font-mono text-sm max-w-xs mx-auto text-center py-2">
                <div className="p-2.5 rounded-lg bg-white/[0.05] border border-cyan-500/20 text-cyan-200">
                  <span className="text-[10px] text-cyan-400 block font-bold">1. ASK (VOICE OR TEXT)</span>
                  "Nova, search the phone under 5000"
                </div>
                <ArrowDown className="w-3.5 h-3.5 mx-auto text-cyan-500/60" />
                <div className="p-2.5 rounded-lg bg-white/[0.05] border border-cyan-500/20 text-cyan-200">
                  <span className="text-[10px] text-cyan-400 block font-bold">2. UNDERSTAND & CONTEXT</span>
                  Resolve intent & check capability health
                </div>
                <ArrowDown className="w-3.5 h-3.5 mx-auto text-cyan-500/60" />
                <div className="p-2.5 rounded-lg bg-white/[0.05] border border-cyan-500/20 text-cyan-200">
                  <span className="text-[10px] text-cyan-400 block font-bold">3. PLAN</span>
                  Determine route: Anakin API for live data
                </div>
                <ArrowDown className="w-3.5 h-3.5 mx-auto text-cyan-500/60" />
                <div className="p-2.5 rounded-lg bg-white/[0.05] border border-cyan-500/20 text-cyan-200">
                  <span className="text-[10px] text-cyan-400 block font-bold">4. ACT</span>
                  Retrieve 5 sources & synthesize response
                </div>
                <ArrowDown className="w-3.5 h-3.5 mx-auto text-cyan-500/60" />
                <div className="p-2.5 rounded-lg bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 font-bold">
                  <span className="text-[10px] text-emerald-400 block">5. VERIFY</span>
                  ✓ Live web research successful & stored in context
                </div>
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-cyan-500/20 space-y-2 text-xs text-slate-300">
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>Controls macOS apps, Chrome/Safari, and system volume</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>Grounds decisions in current internet truth via Anakin</span>
              </div>
              <div className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Closed execution loop verifies actual system results</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
