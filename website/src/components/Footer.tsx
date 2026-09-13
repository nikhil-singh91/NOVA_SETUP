import React from 'react';
import { Github, ExternalLink } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="py-12 bg-[#05070a] border-t border-white/10 text-slate-400 text-xs font-mono">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-8 border-b border-white/5">
          {/* Brand Info */}
          <div className="flex flex-col items-center md:items-start text-center md:text-left">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-extrabold text-white text-base tracking-tight">NOVA</span>
              <span className="text-[10px] uppercase px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                v5
              </span>
            </div>
            <p className="text-slate-400 text-xs">
              Autonomous Computer-Use AI Agent
            </p>
            <p className="text-slate-400 text-[11px] italic mt-1">
              “Don’t just tell me how. Do it.”
            </p>
          </div>

          {/* Quick Links */}
          <div className="flex flex-wrap items-center justify-center gap-6 text-slate-400">
            <a
              href="https://github.com/nikhil-singh91/NOVA_SETUP"
              target="_blank"
              rel="noreferrer"
              className="hover:text-white transition-colors flex items-center gap-1.5"
            >
              <Github className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>
            <a
              href="#demo"
              className="hover:text-white transition-colors"
            >
              Demo
            </a>
            <a
              href="https://anakin.io/"
              target="_blank"
              rel="noreferrer"
              className="hover:text-cyan-400 transition-colors flex items-center gap-1"
            >
              <span>Anakin</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Bottom Attribution */}
        <div className="pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-400 text-[11px] text-center sm:text-left">
          <div>
            Built for <span className="text-slate-300 font-semibold">Anakin Forge 2026</span> • Created by Nikhil Singh
          </div>
          <div>
            Zero Hallucinated Metrics • Authentic macOS Runtime Evidence
          </div>
        </div>
      </div>
    </footer>
  );
};
