import React, { useState } from 'react';
import { SCREENSHOTS_DATA } from '../data/screenshotsData';
import { ScreenshotItem } from '../types';
import { MacWindowFrame } from './MacWindowFrame';
import { CheckCircle, ExternalLink, Eye, Terminal } from 'lucide-react';

interface RealNovaGalleryProps {
  onSelectScreenshot: (item: ScreenshotItem) => void;
}

export const RealNovaGallery: React.FC<RealNovaGalleryProps> = ({ onSelectScreenshot }) => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const current = SCREENSHOTS_DATA[activeTab];

  return (
    <section className="py-24 relative overflow-hidden bg-[#090c14] border-t border-b border-white/5">
      {/* Background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[500px] radial-cyan-glow opacity-60 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            AUTHENTIC GROUND TRUTH
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-3">
            Not a concept. A running agent.
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            These are genuine Retina screenshots captured directly from the live macOS terminal runtime.
            Notice the live AI provider health, memory database, active Whisper state, and real Anakin web intelligence queries.
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
          {SCREENSHOTS_DATA.map((item, idx) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(idx)}
              className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-mono transition-all ${
                activeTab === idx
                  ? 'bg-cyan-500/15 border-cyan-500/50 text-cyan-300 shadow-lg shadow-cyan-950/40 font-semibold'
                  : 'bg-white/[0.03] border-white/10 text-slate-400 hover:text-white hover:bg-white/[0.06]'
              } border`}
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>{item.caption}</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-black/40 text-slate-400">
                0{idx + 1}
              </span>
            </button>
          ))}
        </div>

        {/* Active Screenshot Display in Mac Window Frame */}
        <div className="max-w-5xl mx-auto">
          <MacWindowFrame
            title={`NOVA Cockpit — ${current.caption}`}
            subtitle={current.badge}
            badge="AUTHENTIC RUNTIME"
            onZoom={() => onSelectScreenshot(current)}
          >
            <div
              className="relative cursor-pointer group bg-black"
              onClick={() => onSelectScreenshot(current)}
              title="Click to expand high-resolution evidence"
            >
              <img
                src={current.imageSrc}
                alt={current.caption}
                className="w-full h-auto block object-contain"
              />

              {/* Hover overlay hint */}
              <div className="absolute inset-0 bg-cyan-950/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                <div className="px-4 py-2.5 rounded-xl bg-black/85 border border-cyan-500/40 text-cyan-300 text-xs font-mono font-medium flex items-center gap-2 shadow-2xl">
                  <Eye className="w-4 h-4 text-cyan-400" />
                  <span>Click to inspect 4K raw cockpit evidence</span>
                </div>
              </div>
            </div>
          </MacWindowFrame>

          {/* Screenshot Details & Real Evidence Callouts */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 p-6 rounded-2xl bg-white/[0.02] border border-white/10">
            <div className="md:col-span-2 space-y-3">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  {current.badge}
                </span>
                <h3 className="text-lg font-bold text-white">{current.caption}</h3>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">
                {current.description}
              </p>

              <div className="pt-2">
                <h4 className="text-xs font-mono uppercase text-slate-400 mb-2">
                  Observed Runtime Evidence:
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {current.keyHighlights.map((hl, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                      <CheckCircle className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                      <span>{hl}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Subsystem Telemetry Badge */}
            <div className="p-4 rounded-xl bg-surface-200 border border-white/10 flex flex-col justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 block mb-2">
                  Active Cockpit Telemetry
                </span>
                <div className="space-y-2 text-xs font-mono">
                  <div>
                    <span className="text-slate-500 block">Voice State:</span>
                    <span className="text-cyan-300 font-medium">
                      {current.terminalTelemetry?.voiceState}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Subsystem / Status:</span>
                    <span className="text-emerald-400 font-medium">
                      {current.terminalTelemetry?.status}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Intelligence Provider:</span>
                    <span className="text-slate-200">
                      {current.terminalTelemetry?.aiProvider}
                    </span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => onSelectScreenshot(current)}
                className="mt-4 w-full py-2 px-3 rounded-lg text-xs font-mono font-medium text-cyan-400 hover:text-white bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 transition-colors flex items-center justify-center gap-1.5"
              >
                <span>Inspect Full 4K</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
