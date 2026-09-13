import React from 'react';

export const TechStackSection: React.FC = () => {
  const techItems = [
    { name: 'Python 3.14', category: 'Core Runtime', role: 'Type-hinted asynchronous orchestrator' },
    { name: 'macOS Native Layer', category: 'System Control', role: 'AppleScript & process automation bridge' },
    { name: 'Whisper STT', category: 'Audio Ingestion', role: 'Local speech-to-text with confidence scoring' },
    { name: 'Neural TTS', category: 'Voice Synthesis', role: 'Companion voice generation and speech feedback' },
    { name: 'Browser Automation', category: 'Web Interaction', role: 'Chrome & Safari tab and DOM control' },
    { name: 'Multi-Provider AI', category: 'Reasoning Core', role: 'Gemini, Groq, OpenRouter, Cerebras fallbacks' },
    { name: 'Anakin API', category: 'Live Intelligence', role: 'Real-time multi-source search & deep research' },
    { name: 'Context Engine', category: 'Memory & State', role: 'RecentInteractionContext multi-turn resolver' },
    { name: 'Task Planning', category: 'Agentic Core', role: 'Goal decomposition and execution scheduler' },
    { name: 'GitHub', category: 'Source Control', role: 'Production engineering and versioning' },
  ];

  return (
    <section className="py-24 relative overflow-hidden bg-[#07090e] border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-3 py-1 rounded-full border border-cyan-500/20">
            SYSTEM FOUNDATION
          </span>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight mt-4 mb-4">
            Built with
          </h2>
          <p className="text-base sm:text-lg text-slate-300">
            Engineered with strict software principles: typed Python 3.14, modular architecture,
            and specialized subsystem adapters.
          </p>
        </div>

        {/* Tech Pills Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 max-w-5xl mx-auto">
          {techItems.map((tech) => (
            <div
              key={tech.name}
              className="p-4 rounded-xl bg-white/[0.02] border border-white/10 hover:border-cyan-500/30 hover:bg-white/[0.04] transition-all flex flex-col justify-between group"
            >
              <div>
                <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider block mb-1">
                  {tech.category}
                </span>
                <h3 className="font-mono text-sm font-bold text-white group-hover:text-cyan-300 transition-colors">
                  {tech.name}
                </h3>
              </div>
              <p className="text-[11px] text-slate-400 mt-2 leading-snug">
                {tech.role}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
