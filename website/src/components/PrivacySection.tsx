import React from 'react';
import { ShieldCheck, Key, HardDrive, EyeOff } from 'lucide-react';

export const PrivacySection: React.FC = () => {
  const privacyPillars = [
    {
      icon: HardDrive,
      title: 'Local-First Architecture',
      desc: 'NOVA runs directly on your local macOS environment. Task planning, memory indexing, and speech recognition (Whisper) occur locally on-device without cloud telemetry.'
    },
    {
      icon: Key,
      title: 'Environment Key Isolation',
      desc: 'All API keys (Anakin, Gemini, Groq, OpenRouter) remain in local .env files. Secrets are never hardcoded, transmitted to third-party dashboards, or exposed in public bundles.'
    },
    {
      icon: EyeOff,
      title: 'Ephemeral Perception Data',
      desc: 'Screen inspection and audio levels are processed ephemerally in active memory for immediate task fulfillment, with zero perpetual cloud recording or background telemetry scraping.'
    },
    {
      icon: ShieldCheck,
      title: 'Explicit Network Routing',
      desc: 'External networks are reached exclusively when a specific task demands live web grounding (Anakin API) or LLM reasoning. Local commands stay strictly local.'
    }
  ];

  return (
    <section className="py-24 relative overflow-hidden bg-[#080b12] border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            SECURITY & CONTROL
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            Designed with control in mind.
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Autonomous computer use requires strict engineering boundaries. NOVA enforces isolation,
            transparent execution logging, and local-first execution.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl mx-auto">
          {privacyPillars.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.title}
                className="p-6 rounded-2xl bg-white/[0.02] border border-white/10 hover:border-cyan-500/30 transition-all flex items-start gap-4"
              >
                <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 shrink-0">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white mb-1.5">{p.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{p.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
