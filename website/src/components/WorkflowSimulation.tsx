import React, { useState, useEffect } from 'react';
import { ACTUAL_WORKFLOW_STEPS } from '../data/workflowData';
import { Play, Pause, RotateCcw, CheckCircle, Terminal } from 'lucide-react';

export const WorkflowSimulation: React.FC = () => {
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);

  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentStepIndex((prev) => (prev < ACTUAL_WORKFLOW_STEPS.length - 1 ? prev + 1 : 0));
    }, 2800);
    return () => clearInterval(interval);
  }, [isPlaying]);

  const active = ACTUAL_WORKFLOW_STEPS[currentStepIndex];

  return (
    <section id="workflow" className="py-24 relative overflow-hidden bg-[#080b12]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            TIME-TO-VALUE: 15 SECONDS
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            An Actual Workflow
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Experience how a single voice command seamlessly routes through intent parsing, Anakin web grounding,
            multi-source synthesis, and closed-loop verification.
          </p>
        </div>

        {/* Workflow Interactive Player */}
        <div className="max-w-5xl mx-auto p-6 sm:p-8 rounded-3xl bg-[#0b0e17] border border-cyan-500/30 shadow-2xl relative">
          {/* Top Bar: Prompt Simulation */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 mb-6 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-300">
                <Terminal className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider block">
                  SPOKEN USER GOAL
                </span>
                <span className="text-base sm:text-lg font-bold text-white font-mono">
                  “Nova, research the best smartphones under ₹20,000.”
                </span>
              </div>
            </div>

            {/* Play/Pause Controls */}
            <div className="flex items-center gap-2 self-end sm:self-auto">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-mono border border-white/10 transition-colors"
                title={isPlaying ? 'Pause Auto-Play' : 'Resume Auto-Play'}
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{isPlaying ? 'Pause' : 'Play'}</span>
              </button>
              <button
                onClick={() => {
                  setCurrentStepIndex(0);
                  setIsPlaying(false);
                }}
                className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition-colors"
                title="Reset to Step 1"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* 7-Step Navigation Indicator */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 mb-8">
            {ACTUAL_WORKFLOW_STEPS.map((step, idx) => {
              const isPassed = idx < currentStepIndex;
              const isCurrent = idx === currentStepIndex;
              return (
                <button
                  key={step.step}
                  onClick={() => {
                    setCurrentStepIndex(idx);
                    setIsPlaying(false);
                  }}
                  className={`p-2.5 rounded-xl text-left transition-all relative ${
                    isCurrent
                      ? 'bg-cyan-500/20 border-cyan-400 text-white shadow-lg shadow-cyan-950/40 scale-102'
                      : isPassed
                      ? 'bg-white/[0.04] border-cyan-500/30 text-cyan-200'
                      : 'bg-white/[0.02] border-white/5 text-slate-500 hover:text-slate-300'
                  } border`}
                >
                  <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                    <span>{step.label}</span>
                    {isPassed && <CheckCircle className="w-3 h-3 text-cyan-400" />}
                  </div>
                  <span className="text-xs font-bold block truncate">
                    {step.title}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Active Step Showcase Card */}
          <div className="p-6 sm:p-8 rounded-2xl bg-[#101422] border border-cyan-500/40 transition-all">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 mb-4 border-b border-white/10">
              <div className="flex items-center gap-3">
                <span className="px-3 py-1 rounded-lg bg-cyan-500/20 text-cyan-300 font-mono text-xs font-bold border border-cyan-500/30">
                  {active.label} OF 07
                </span>
                <h3 className="text-xl sm:text-2xl font-black text-white">
                  {active.title}
                </h3>
              </div>

              <span className="text-xs font-mono px-2.5 py-1 rounded bg-white/5 text-slate-300 border border-white/10">
                ACTOR: {active.actor} • {active.subsystem}
              </span>
            </div>

            <p className="text-sm sm:text-base text-slate-200 leading-relaxed mb-6">
              {active.description}
            </p>

            {/* Simulated Terminal Output */}
            {active.logOutput && (
              <div className="p-4 rounded-xl bg-[#06080e] border border-white/10 font-mono text-xs text-slate-300 space-y-1">
                <span className="text-[10px] text-slate-400 block uppercase tracking-wider">
                  Terminal Activity Feed Telemetry
                </span>
                <div className="text-cyan-400 break-words">
                  {active.logOutput}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
