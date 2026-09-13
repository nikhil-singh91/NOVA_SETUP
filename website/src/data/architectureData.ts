export interface ArchBranch {
  id: string;
  name: string;
  badge: string;
  role: string;
  submodules: string[];
  color: string;
}

export const ARCHITECTURE_BRANCHES: ArchBranch[] = [
  {
    id: 'mac-control',
    name: 'Mac Control',
    badge: 'NATIVE OS',
    role: 'Desktop application management, AppleScript commands, keypresses, window focus & automation',
    submodules: ['AppLauncher', 'AppleScriptBridge', 'WindowFocusManager', 'SafetyGuard'],
    color: 'from-blue-500/20 to-blue-500/5 text-blue-400 border-blue-500/30'
  },
  {
    id: 'browser-control',
    name: 'Browser Control',
    badge: 'WEB AUTOMATION',
    role: 'Direct macOS Chrome/Safari automation, tab handling, URL navigation, and content extraction',
    submodules: ['ChromeBridge', 'TabManager', 'DomReader', 'ScrollAutomator'],
    color: 'from-cyan-500/20 to-cyan-500/5 text-cyan-400 border-cyan-500/30'
  },
  {
    id: 'anakin-web',
    name: 'Anakin Web Intelligence',
    badge: 'LIVE WEB GROUNDING',
    role: 'External web search, multi-source retrieval, structured research payloads, live price & news citations',
    submodules: ['AnakinService', 'WebSourceNormalizer', 'DeepResearchEngine', 'CitationParser'],
    color: 'from-sky-400/20 to-sky-400/5 text-sky-300 border-sky-400/30'
  },
  {
    id: 'media-system',
    name: 'Media & Audio',
    badge: 'SYSTEM AMBIENCE',
    role: 'Playback management, system volume, non-repeating music, and audio hardware monitoring',
    submodules: ['MediaController', 'VolumeManager', 'AudioLevelMonitor', 'PlaybackQueue'],
    color: 'from-purple-500/20 to-purple-500/5 text-purple-400 border-purple-500/30'
  },
  {
    id: 'ai-providers',
    name: 'AI Multi-Provider Engine',
    badge: 'REASONING CORE',
    role: 'Dynamic multi-provider routing with automated latency & quota fallback (Gemini, Groq, OpenRouter, Cerebras)',
    submodules: ['GeminiAdapter', 'GroqFastReasoner', 'OpenRouterFallback', 'CerebrasMonitor'],
    color: 'from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/30'
  }
];

export const ARCHITECTURE_PIPELINE = [
  { step: '01', name: 'User Interaction', desc: 'Continuous voice via Whisper STT or keyboard input in terminal cockpit' },
  { step: '02', name: 'Intent & Goal Parsing', desc: 'Rule-based fast classification + semantic intent matcher' },
  { step: '03', name: 'Context Resolution', desc: 'RecentInteractionContext links prior entities, tabs, and short-term memory' },
  { step: '04', name: 'Task Planning', desc: 'Decomposes complex requests into targeted capability branch invocations' },
  { step: '05', name: 'Specialized Subsystem Dispatch', desc: 'Executes across Mac, Browser, Anakin, Media, or Multi-Provider' },
  { step: '06', name: 'Observe & Verify', desc: 'Verifies process outcomes, source citations, and system state before reporting' },
  { step: '07', name: 'Response & Cockpit Telemetry', desc: 'Voice synthesis playback and rich telemetry update on live activity feed' }
];
