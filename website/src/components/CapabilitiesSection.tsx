import React, { useState } from 'react';
import { CAPABILITIES_DATA } from '../data/capabilitiesData';
import { Mic, Laptop, Globe, Compass, GitMerge, ListTree, ShieldCheck, Sliders, CheckCircle } from 'lucide-react';

export const CapabilitiesSection: React.FC = () => {
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);

  const getIcon = (iconName: string) => {
    switch (iconName) {
      case 'Mic': return Mic;
      case 'Laptop': return Laptop;
      case 'Globe': return Globe;
      case 'Compass': return Compass;
      case 'GitMerge': return GitMerge;
      case 'ListTree': return ListTree;
      case 'ShieldCheck': return ShieldCheck;
      case 'Sliders': return Sliders;
      default: return Laptop;
    }
  };

  return (
    <section id="capabilities" className="py-24 relative overflow-hidden bg-[#07090e]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            ENGINEERING SPECIFICATION
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-3">
            What NOVA can do
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Eight verified operational capabilities spanning speech, desktop automation, live web intelligence,
            context retention, and closed-loop verification.
          </p>
        </div>

        {/* 8 Capability Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {CAPABILITIES_DATA.map((item) => {
            const Icon = getIcon(item.iconName);
            const isHovered = hoveredCard === item.id;

            return (
              <div
                key={item.id}
                onMouseEnter={() => setHoveredCard(item.id)}
                onMouseLeave={() => setHoveredCard(null)}
                className={`p-6 rounded-2xl transition-all duration-300 flex flex-col justify-between ${
                  isHovered
                    ? 'bg-[#111624] border-cyan-500/50 shadow-xl shadow-cyan-950/30 -translate-y-1'
                    : 'bg-white/[0.02] border-white/10'
                } border group`}
              >
                <div>
                  {/* Top Bar: Icon & Badge */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-11 h-11 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 group-hover:scale-110 group-hover:bg-cyan-500/20 transition-all">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded uppercase font-semibold tracking-wider bg-white/[0.05] text-slate-400 group-hover:text-cyan-300 group-hover:bg-cyan-500/10 transition-colors">
                      {item.badge}
                    </span>
                  </div>

                  {/* Title & Subtitle */}
                  <div className="mb-3">
                    <span className="text-[11px] font-mono text-cyan-400/80 block font-semibold">
                      CAPABILITY {item.number}
                    </span>
                    <h3 className="text-lg font-bold text-white group-hover:text-cyan-300 transition-colors">
                      {item.title}
                    </h3>
                    <p className="text-xs font-mono text-slate-400 mt-0.5">
                      {item.subtitle}
                    </p>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed mb-4">
                    {item.description}
                  </p>
                </div>

                {/* Subsystem Feature Highlights */}
                <div className="pt-4 border-t border-white/5 space-y-2">
                  {item.features.map((feat, fIdx) => (
                    <div key={fIdx} className="flex items-start gap-2 text-[11px] text-slate-400">
                      <CheckCircle className="w-3 h-3 text-cyan-400/70 shrink-0 mt-0.5" />
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
