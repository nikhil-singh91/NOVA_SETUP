import React, { useState } from 'react';
import { ANAKIN_FLOW_STEPS, ROLE_COMPARISON, REAL_LOG_TIMELINE } from '../data/anakinData';
import { MacWindowFrame } from './MacWindowFrame';
import { Compass, CheckCircle2, Terminal, Cpu, Eye } from 'lucide-react';

interface AnakinProps {
  onInspectAnakinScreenshot: () => void;
}

export const AnakinIntegrationSection: React.FC<AnakinProps> = ({ onInspectAnakinScreenshot }) => {
  const [activeStep, setActiveStep] = useState<number>(4); // Default to Anakin node

  return (
    <section id="anakin" className="py-28 relative overflow-hidden bg-[#06080e] border-t border-b border-cyan-500/20">
      {/* Background Radial Glow */}
      <div className="absolute top-1/4 right-0 w-[600px] h-[600px] bg-cyan-500/10 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 left-0 w-[500px] h-[500px] bg-sky-600/10 rounded-full blur-[140px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Section Eyebrow & Title */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-xs font-mono font-semibold tracking-wider uppercase mb-4 shadow-lg shadow-cyan-950/50">
            <Compass className="w-3.5 h-3.5 text-cyan-400" />
            <span>LIVE WEB INTELLIGENCE LAYER</span>
          </div>

          <h2 className="text-4xl sm:text-6xl font-black text-white tracking-tight mb-4">
            NOVA <span className="text-cyan-400 font-light">×</span> Anakin
          </h2>

          <p className="text-2xl sm:text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-sky-200 to-white mb-6">
            Give an AI agent access to the live web.
          </p>

          <p className="text-base sm:text-lg text-slate-300 leading-relaxed">
            Anakin is integrated into NOVA as its live web intelligence layer. When a request requires
            current web information, NOVA routes the task to Anakin's web capabilities, retrieves current
            sources, brings the results into NOVA’s task context, and continues reasoning over them.
          </p>
        </div>

        {/* Clear Architectural Responsibility Separation */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-20">
          {/* NOVA Domain */}
          <div className="p-6 sm:p-8 rounded-2xl bg-white/[0.02] border border-white/10 relative">
            <div className="flex items-center justify-between pb-4 mb-6 border-b border-white/10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                  <Cpu className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">NOVA</h3>
                  <span className="text-xs text-cyan-400 font-mono">Agent Orchestration & OS Control</span>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2 py-1 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                LOCAL AGENT
              </span>
            </div>

            <div className="space-y-3">
              {ROLE_COMPARISON.nova.map((item, idx) => (
                <div key={idx} className="flex items-start gap-3 text-xs">
                  <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-slate-200 block">{item.title}</span>
                    <span className="text-slate-400">{item.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ANAKIN Domain */}
          <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-b from-sky-950/20 to-surface-100 border border-cyan-500/30 relative">
            <div className="flex items-center justify-between pb-4 mb-6 border-b border-cyan-500/20">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400">
                  <Compass className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">ANAKIN</h3>
                  <span className="text-xs text-sky-400 font-mono">Live Web Intelligence Layer</span>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2 py-1 rounded bg-sky-500/20 text-sky-300 border border-sky-500/40">
                EXTERNAL KNOWLEDGE
              </span>
            </div>

            <div className="space-y-4">
              {ROLE_COMPARISON.anakin.map((item, idx) => (
                <div key={idx} className="flex items-start gap-3 text-xs">
                  <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-slate-200 block">{item.title}</span>
                    <span className="text-slate-400">{item.desc}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-8 p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-[11px] font-mono text-sky-300">
              <strong>Architectural Boundary:</strong> Anakin does not replace NOVA. NOVA orchestrates the computer, voice, and reasoning; Anakin provides live web grounding and multi-source citations.
            </div>
          </div>
        </div>

        {/* Animated Flow Visualization */}
        <div className="mb-20">
          <div className="text-center mb-8">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
              END-TO-END EXECUTION LOOP (CLICK ANY NODE TO INSPECT)
            </span>
            <h3 className="text-2xl font-bold text-white mt-1">
              Live Web Intelligence Flow
            </h3>
          </div>

          {/* Interactive Flow Nodes Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 lg:grid-cols-11 gap-1.5 p-2 rounded-2xl bg-white/[0.02] border border-white/10">
            {ANAKIN_FLOW_STEPS.map((step, idx) => {
              const isCurrent = activeStep === idx;
              return (
                <button
                  key={step.id}
                  onClick={() => setActiveStep(idx)}
                  className={`p-2 rounded-xl text-left transition-all relative ${
                    isCurrent
                      ? 'bg-cyan-500/20 border-cyan-400 text-white shadow-lg shadow-cyan-950/50 scale-105 z-10'
                      : 'bg-white/[0.02] border-white/5 text-slate-400 hover:text-slate-200 hover:bg-white/[0.05]'
                  } border`}
                >
                  <span className="text-[9px] font-mono text-slate-500 block">
                    0{idx + 1}
                  </span>
                  <span className="text-[11px] font-mono font-bold block truncate mt-0.5">
                    {step.label}
                  </span>
                  <span className="text-[9px] text-cyan-400/80 block truncate">
                    {step.role}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Selected Flow Step Inspector */}
          <div className="mt-4 p-5 rounded-2xl bg-[#0c101a] border border-cyan-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                  STEP 0{activeStep + 1}: {ANAKIN_FLOW_STEPS[activeStep].label}
                </span>
                <span className="text-xs font-mono text-slate-400">
                  Role: {ANAKIN_FLOW_STEPS[activeStep].role}
                </span>
              </div>
              <p className="text-sm text-slate-200">
                {ANAKIN_FLOW_STEPS[activeStep].desc}
              </p>
            </div>

            <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
              <button
                onClick={() => setActiveStep((prev) => (prev > 0 ? prev - 1 : ANAKIN_FLOW_STEPS.length - 1))}
                className="px-3 py-1 text-xs font-mono bg-white/5 hover:bg-white/10 text-slate-300 rounded border border-white/10 transition-colors"
              >
                Previous
              </button>
              <button
                onClick={() => setActiveStep((prev) => (prev < ANAKIN_FLOW_STEPS.length - 1 ? prev + 1 : 0))}
                className="px-3 py-1 text-xs font-mono bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 rounded border border-cyan-500/30 transition-colors"
              >
                Next Step
              </button>
            </div>
          </div>
        </div>

        {/* Real Anakin Workflow Evidence (from actual screenshot) */}
        <div className="mt-16 pt-12 border-t border-white/10">
          <div className="text-center max-w-2xl mx-auto mb-10">
            <span className="text-xs font-mono uppercase tracking-widest text-cyan-400">
              REAL SYSTEM EVIDENCE
            </span>
            <h3 className="text-2xl sm:text-3xl font-black text-white mt-1">
              Live Terminal Activity Feed
            </h3>
            <p className="text-xs sm:text-sm text-slate-400 mt-2">
              The exact sequence executed by NOVA when a user asks: <span className="text-cyan-300 font-mono">"Nova, can you search the phone under 5000?"</span>
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            {/* Left: Terminal Log Stream */}
            <div className="lg:col-span-5 p-5 rounded-2xl bg-[#0b0e17] border border-white/15 font-mono text-xs space-y-3.5 shadow-2xl">
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <span className="text-slate-400 text-[11px] flex items-center gap-2">
                  <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                  <span>LIVE NOVA ACTIVITY FEED</span>
                </span>
                <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  VERIFIED RUN
                </span>
              </div>

              {REAL_LOG_TIMELINE.map((item, idx) => (
                <div key={idx} className="space-y-0.5 border-l-2 border-white/10 pl-3 py-0.5">
                  <div className="flex items-center gap-2 text-[10px] text-slate-500">
                    <span>{item.time}</span>
                    <span className={`font-bold ${item.color}`}>{item.type}</span>
                  </div>
                  <div className="text-slate-200 text-[11px] leading-relaxed break-words">
                    {item.content}
                  </div>
                </div>
              ))}
            </div>

            {/* Right: The Actual Screenshot Evidence Preview */}
            <div className="lg:col-span-7">
              <MacWindowFrame
                title="NOVA Voice + Anakin Research Evidence"
                subtitle="Live Execution Result"
                badge="REAL SYSTEM RUN"
                onZoom={onInspectAnakinScreenshot}
              >
                <div
                  className="relative cursor-pointer group bg-black"
                  onClick={onInspectAnakinScreenshot}
                  title="Click to view raw 4K screenshot"
                >
                  <img
                    src="/assets/nova-voice.png"
                    alt="Real NOVA screenshot showing Anakin web research started, returned 5 sources, and live web research successful"
                    className="w-full h-auto block object-cover"
                  />
                  <div className="absolute inset-0 bg-cyan-950/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[1px]">
                    <div className="px-4 py-2 rounded-xl bg-black/80 border border-cyan-500/40 text-cyan-300 text-xs font-mono font-medium flex items-center gap-2">
                      <Eye className="w-4 h-4 text-cyan-400" />
                      <span>Inspect Raw Terminal Evidence</span>
                    </div>
                  </div>
                </div>
              </MacWindowFrame>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
