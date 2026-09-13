import React from 'react';
import { Play, Github, Terminal, ArrowRight, Activity, ShieldCheck, Compass, Mic, Laptop, GitMerge } from 'lucide-react';
import { MacWindowFrame } from './MacWindowFrame';

interface HeroProps {
  onWatchDemo: () => void;
  onInspectScreenshot: () => void;
}

export const Hero: React.FC<HeroProps> = ({ onWatchDemo, onInspectScreenshot }) => {
  const microProofs = [
    { label: 'VOICE', icon: Mic, desc: 'Whisper STT & neural speech' },
    { label: 'LIVE WEB', icon: Compass, desc: 'Real-time multi-source search' },
    { label: 'COMPUTER CONTROL', icon: Laptop, desc: 'Direct macOS system automation' },
    { label: 'CONTEXT', icon: GitMerge, desc: 'Multi-turn task memory' },
    { label: 'ANAKIN', icon: Activity, desc: 'Live web intelligence layer' },
    { label: 'VERIFICATION', icon: ShieldCheck, desc: 'Closed-loop truth validation' },
  ];

  return (
    <section id="overview" className="relative pt-32 pb-20 md:pt-40 md:pb-28 overflow-hidden">
      {/* Strategic Ambient Glows */}
      <div className="absolute top-10 left-1/2 -translate-x-1/2 w-[800px] h-[450px] radial-cyan-glow pointer-events-none" />
      <div className="absolute top-40 right-10 w-[500px] h-[400px] radial-blue-glow pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Eyebrow & Badges */}
        <div className="flex flex-wrap items-center justify-center gap-2.5 mb-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-mono font-medium tracking-wide">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            <span>ANAKIN FORGE 2026 SUBMISSION</span>
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.04] border border-white/10 text-slate-400 text-xs font-mono">
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>LOCAL RUNTIME: macOS</span>
          </div>
        </div>

        {/* Headlines */}
        <div className="text-center max-w-4xl mx-auto mb-10">
          <h1 className="text-5xl sm:text-7xl md:text-8xl font-black tracking-tight text-white mb-4">
            NOVA
          </h1>

          <p className="text-3xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-slate-100 via-cyan-100 to-sky-300 leading-tight sm:leading-none mb-6">
            “Don’t just tell me how.<br />
            <span className="text-cyan-400 underline decoration-cyan-500/40 decoration-wavy decoration-2">Do it.</span>”
          </p>

          <p className="text-base sm:text-lg md:text-xl text-slate-300 max-w-3xl mx-auto font-normal leading-relaxed">
            NOVA is a voice-first autonomous computer-use AI agent designed to understand goals,
            interact with the computer and live web, execute multi-step workflows, and verify the result.
          </p>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center justify-center gap-4 mt-8">
            <button
              onClick={onWatchDemo}
              className="inline-flex items-center gap-2.5 px-6 py-3.5 rounded-xl text-sm font-semibold text-black bg-gradient-to-r from-cyan-400 via-sky-400 to-blue-400 hover:from-cyan-300 hover:to-blue-300 shadow-xl shadow-cyan-500/25 transition-all transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>WATCH NOVA IN ACTION</span>
            </button>

            <a
              href="https://github.com/nikhil-singh91/NOVA_SETUP"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl text-sm font-medium text-slate-200 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 transition-all transform hover:-translate-y-0.5"
            >
              <Github className="w-4 h-4" />
              <span>VIEW ON GITHUB</span>
              <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
            </a>
          </div>
        </div>

        {/* Real NOVA Dashboard Visual (Real Evidence) */}
        <div className="relative max-w-5xl mx-auto mt-12 sm:mt-16">
          <div className="relative transform hover:scale-[1.008] transition-transform duration-500">
            <MacWindowFrame
              title="NOVA Operations Control Center — Terminal Cockpit"
              subtitle="macOS Native Runtime (python main.py)"
              badge="VERIFIED LOCAL RUNTIME"
              onZoom={onInspectScreenshot}
              className="ring-1 ring-white/15"
            >
              <div
                className="relative cursor-pointer group"
                onClick={onInspectScreenshot}
                title="Click to inspect real running cockpit in full resolution"
              >
                <img
                  src="/assets/nova-dashboard.png"
                  alt="Real NOVA Operations Control Center terminal cockpit showing multi-provider AI, system performance, memory layer, Mac control, and live activity feed"
                  className="w-full h-auto block object-cover"
                  loading="eager"
                />

                {/* Subtle Overlay Badge on Hover */}
                <div className="absolute inset-0 bg-cyan-950/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[1px]">
                  <div className="px-4 py-2 rounded-xl bg-black/80 border border-cyan-500/40 text-cyan-300 text-xs font-mono font-medium flex items-center gap-2 shadow-xl">
                    <Activity className="w-4 h-4 text-cyan-400 animate-pulse" />
                    <span>Click to inspect 4K raw cockpit evidence</span>
                  </div>
                </div>
              </div>
            </MacWindowFrame>
          </div>

          {/* Genuine Telemetry Legend */}
          <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 px-3 py-2 mt-3 bg-white/[0.02] border border-white/5 rounded-lg">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Telemetry: Gemini 607ms • Groq 626ms • OpenRouter 1.14s</span>
            </span>
            <span className="text-slate-400">
              Raw system screenshot: 2940 × 1912 Retina (Zero synthetic mockups)
            </span>
          </div>
        </div>

        {/* Hero Micro-Proof Strip (Genuine capabilities, no fake metrics) */}
        <div className="mt-16 pt-8 border-t border-white/10">
          <div className="text-center mb-5">
            <span className="text-xs font-mono uppercase tracking-widest text-slate-400">
              CORE AGENTIC CAPABILITIES — ZERO FABRICATED METRICS
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {microProofs.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.label}
                  className="p-3.5 rounded-xl bg-surface-glass border border-surface-glass-border hover:border-cyan-500/30 transition-all flex flex-col items-center text-center group"
                >
                  <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-2 group-hover:scale-110 transition-transform">
                    <Icon className="w-4 h-4 text-cyan-400" />
                  </div>
                  <span className="font-mono text-xs font-bold text-slate-200 tracking-wider">
                    {item.label}
                  </span>
                  <span className="text-[11px] text-slate-400 mt-1 leading-snug">
                    {item.desc}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};
