import React from 'react';
import { Play, Terminal, ExternalLink } from 'lucide-react';
import { MacWindowFrame } from './MacWindowFrame';

// ============================================================================
// CONFIGURABLE DEMO VIDEO URL
// Replace with the final YouTube / Loom / Drive link when ready.
// Example: export const DEMO_VIDEO_URL = "https://www.youtube.com/embed/YOUR_ID";
// ============================================================================
export const DEMO_VIDEO_URL = "";

interface DemoSectionProps {
  onInspectCockpit: () => void;
}

export const DemoSection: React.FC<DemoSectionProps> = ({ onInspectCockpit }) => {

  return (
    <section id="demo" className="py-24 relative overflow-hidden bg-[#07090e] border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            RECORDED SYSTEM RUNTIME
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            See NOVA in action.
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Watch NOVA capture spoken voice commands, dispatch live queries to Anakin, operate macOS applications,
            and report verified execution logs in the terminal cockpit.
          </p>
        </div>

        {/* Video Player Container */}
        <div className="max-w-4xl mx-auto">
          {DEMO_VIDEO_URL ? (
            <div className="relative rounded-2xl overflow-hidden border border-cyan-500/30 shadow-2xl aspect-video bg-black">
              <iframe
                src={DEMO_VIDEO_URL}
                title="NOVA Live Demo Video"
                className="w-full h-full"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            </div>
          ) : (
            <MacWindowFrame
              title="NOVA System Walkthrough Video"
              subtitle="macOS Terminal Cockpit Recording"
              badge="DEMO PLAYER"
              onZoom={onInspectCockpit}
            >
              <div className="relative aspect-video bg-[#090d16] flex flex-col items-center justify-center p-6 text-center group overflow-hidden">
                {/* Background terminal backdrop preview */}
                <div className="absolute inset-0 opacity-25 filter blur-[2px]">
                  <img
                    src="/assets/nova-dashboard.png"
                    alt="NOVA cockpit backdrop"
                    className="w-full h-full object-cover"
                  />
                </div>

                <div className="relative z-10 max-w-md mx-auto space-y-4">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-gradient-to-tr from-cyan-500 to-sky-400 text-black flex items-center justify-center shadow-xl shadow-cyan-500/30 mx-auto transform group-hover:scale-110 transition-transform">
                    <Play className="w-8 h-8 fill-current ml-1" />
                  </div>

                  <div>
                    <h3 className="text-xl sm:text-2xl font-bold text-white mb-2">
                      Demo Video Coming Here
                    </h3>
                    <p className="text-xs sm:text-sm text-slate-300">
                      High-definition recording showcasing voice recognition, Anakin live web research, and direct macOS automation.
                    </p>
                  </div>

                  <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
                    <button
                      onClick={onInspectCockpit}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-medium bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 transition-colors"
                    >
                      <Terminal className="w-3.5 h-3.5" />
                      <span>Inspect Live Cockpit Screenshots</span>
                    </button>
                    <a
                      href="https://github.com/nikhil-singh91/NOVA_SETUP"
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-mono font-medium bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 transition-colors"
                    >
                      <span>Explore Repository</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              </div>
            </MacWindowFrame>
          )}
        </div>
      </div>
    </section>
  );
};
