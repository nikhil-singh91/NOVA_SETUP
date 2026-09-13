import React, { useState } from 'react';
import { Brain, ListTree, Play, Eye, ShieldCheck, ArrowRight, RefreshCw } from 'lucide-react';

export const AgentLoopSection: React.FC = () => {
  const [activeLoopStep, setActiveLoopStep] = useState<number>(2); // ACT by default

  const loopSteps = [
    {
      id: 'understand',
      number: '01',
      title: 'UNDERSTAND',
      subtitle: 'Intent Parsing & Context Binding',
      icon: Brain,
      desc: 'NOVA decodes natural voice or text, parses the intent (e.g. system control, live web research, browser tab), and binds it to active session context.',
      details: 'Resolves pronouns like "this tab" or "that product" against RecentInteractionContext.'
    },
    {
      id: 'plan',
      number: '02',
      title: 'PLAN',
      subtitle: 'Subsystem Routing & Preconditions',
      icon: ListTree,
      desc: 'Determines whether the task requires native macOS commands, Chrome automation, live internet lookup via Anakin, or LLM reasoning.',
      details: 'Identifies prerequisites (e.g. Chrome running, valid API keys in .env, accessibility permissions).'
    },
    {
      id: 'act',
      number: '03',
      title: 'ACT',
      subtitle: 'Targeted Execution',
      icon: Play,
      desc: 'Invokes the selected subsystem: dispatches queries to Anakin SDK, simulates native keypresses, launches apps, or navigates browser pages.',
      details: 'Execution runs with safety guards preventing destructive shell commands.'
    },
    {
      id: 'observe',
      number: '04',
      title: 'OBSERVE',
      subtitle: 'Feedback Inspection',
      icon: Eye,
      desc: 'Reads back the output state: inspects returned web sources, checks process exit codes, or reads the active DOM state of the browser.',
      details: 'Captures raw telemetry including latency, token counts, and system thread loads.'
    },
    {
      id: 'verify',
      number: '05',
      title: 'VERIFY',
      subtitle: 'Closed-Loop Ground Truth',
      icon: ShieldCheck,
      desc: 'Validates that the intended effect truly took place before reporting success. If an error or quota limit occurs, it reports an honest alert.',
      details: 'Eliminates chatbot hallucination by refusing to claim false victories.'
    }
  ];

  return (
    <section className="py-24 relative overflow-hidden bg-[#080b12]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            WHY THIS IS AN AGENT
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            From conversation to execution.
          </h2>
          <p className="text-base sm:text-lg text-slate-300 leading-relaxed">
            Traditional conversational AI stops at generating text. NOVA is designed around an execution
            loop: understand the goal, resolve context, choose a capability, perform an action, observe
            the result, and verify it.
          </p>
        </div>

        {/* 5-Node Interactive Loop */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 mb-8">
          {loopSteps.map((step, idx) => {
            const Icon = step.icon;
            const isSelected = activeLoopStep === idx;
            return (
              <button
                key={step.id}
                onClick={() => setActiveLoopStep(idx)}
                className={`p-5 rounded-2xl text-left transition-all duration-300 flex flex-col justify-between ${
                  isSelected
                    ? 'bg-gradient-to-b from-cyan-950/30 to-surface-100 border-cyan-400 shadow-xl shadow-cyan-950/40 -translate-y-1'
                    : 'bg-white/[0.02] border-white/10 hover:bg-white/[0.04] text-slate-400'
                } border group`}
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                      isSelected ? 'bg-cyan-500/20 text-cyan-300' : 'bg-white/5 text-slate-400 group-hover:text-white'
                    }`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-mono font-bold text-slate-400">
                      {step.number}
                    </span>
                  </div>

                  <h3 className={`text-base font-bold tracking-tight mb-1 ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                    {step.title}
                  </h3>
                  <span className="text-[11px] font-mono text-cyan-400/80 block mb-2">
                    {step.subtitle}
                  </span>
                </div>

                <div className="pt-3 border-t border-white/5 flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span>{isSelected ? 'ACTIVE' : 'INSPECT'}</span>
                  <ArrowRight className="w-3 h-3 text-cyan-400" />
                </div>
              </button>
            );
          })}
        </div>

        {/* Loop Detail Card */}
        <div className="p-6 sm:p-8 rounded-2xl bg-[#0e121d] border border-cyan-500/30 max-w-4xl mx-auto shadow-2xl">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 mb-4 border-b border-white/10">
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded bg-cyan-500/20 text-cyan-300 font-mono text-xs font-bold">
                PHASE {loopSteps[activeLoopStep].number}
              </span>
              <h4 className="text-xl font-bold text-white">
                {loopSteps[activeLoopStep].title} — {loopSteps[activeLoopStep].subtitle}
              </h4>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400">
              <RefreshCw className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
              <span>Continuous Execution Cycle</span>
            </div>
          </div>

          <p className="text-sm sm:text-base text-slate-200 leading-relaxed mb-4">
            {loopSteps[activeLoopStep].desc}
          </p>

          <div className="p-3.5 rounded-xl bg-cyan-500/5 border border-cyan-500/20 text-xs font-mono text-cyan-300">
            <strong>Runtime Behavior:</strong> {loopSteps[activeLoopStep].details}
          </div>
        </div>

        {/* Conclusion Callout */}
        <div className="text-center mt-12">
          <p className="text-lg sm:text-xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-slate-200 via-cyan-200 to-sky-300">
            “That loop is what turns a conversation into an agentic workflow.”
          </p>
        </div>
      </div>
    </section>
  );
};
