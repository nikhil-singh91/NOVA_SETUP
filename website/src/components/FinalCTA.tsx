import React from 'react';
import { Github, Play, ArrowRight, Terminal } from 'lucide-react';

interface FinalCTAProps {
  onWatchDemo: () => void;
}

export const FinalCTA: React.FC<FinalCTAProps> = ({ onWatchDemo }) => {
  return (
    <section className="py-28 relative overflow-hidden bg-[#07090e] border-t border-white/5">
      {/* Background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[350px] radial-cyan-glow opacity-80 pointer-events-none" />

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        <h2 className="text-4xl sm:text-6xl font-black text-white tracking-tight mb-6">
          Ready to let your computer<br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-sky-400">
            become an agent?
          </span>
        </h2>

        <p className="text-base sm:text-xl text-slate-300 max-w-2xl mx-auto mb-10 leading-relaxed font-normal">
          Explore the open architecture, inspect live execution traces, or run the local terminal cockpit on macOS.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <a
            href="https://github.com/nikhil-singh91/NOVA_SETUP"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2.5 px-7 py-4 rounded-xl text-sm font-semibold text-black bg-gradient-to-r from-cyan-400 via-sky-400 to-blue-400 hover:from-cyan-300 hover:to-blue-300 shadow-xl shadow-cyan-500/25 transition-all transform hover:-translate-y-0.5"
          >
            <Github className="w-4 h-4" />
            <span>VIEW SOURCE ON GITHUB</span>
            <ArrowRight className="w-4 h-4" />
          </a>

          <button
            onClick={onWatchDemo}
            className="inline-flex items-center gap-2.5 px-7 py-4 rounded-xl text-sm font-medium text-slate-200 hover:text-white bg-white/[0.05] hover:bg-white/[0.1] border border-white/10 transition-all transform hover:-translate-y-0.5"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>WATCH DEMO</span>
          </button>
        </div>

        {/* Local Command Tip */}
        <div className="mt-12 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-black/60 border border-white/10 text-xs font-mono text-slate-400">
          <Terminal className="w-3.5 h-3.5 text-cyan-400" />
          <span>Local launch: <code className="text-cyan-300 font-bold">python main.py</code> inside macOS terminal</span>
        </div>
      </div>
    </section>
  );
};
