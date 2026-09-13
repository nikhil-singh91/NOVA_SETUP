import { CapabilityItem } from '../types';

export const CAPABILITIES_DATA: CapabilityItem[] = [
  {
    id: 'voice',
    number: '01',
    title: 'Voice Interaction',
    subtitle: 'Neural Speech & Audio Pipeline',
    description: 'Speak naturally and turn voice requests into actions.',
    badge: 'VOICE-FIRST',
    iconName: 'Mic',
    features: [
      'Local Whisper engine for offline-capable speech recognition',
      'Continuous listening state with real-time confidence scoring',
      'Low-latency voice responses formulated with companion personality',
      'Hands-free operational loop directly from macOS terminal cockpit'
    ]
  },
  {
    id: 'computer-control',
    number: '02',
    title: 'Computer Control',
    subtitle: 'macOS Native Automation Layer',
    description: "Interact with the macOS environment through NOVA's control layer.",
    badge: 'SYSTEM-LEVEL',
    iconName: 'Laptop',
    features: [
      'Direct AppleScript & native OS bridge for system commands',
      'Application launching, window focusing, and state management',
      'Targeted keystroke, shortcut, and text typing simulation',
      'Guarded execution with safety checks on system commands'
    ]
  },
  {
    id: 'browser-automation',
    number: '03',
    title: 'Browser Automation',
    subtitle: 'Web Interface Navigation',
    description: 'Navigate and interact with browser workflows.',
    badge: 'BROWSER-USE',
    iconName: 'Globe',
    features: [
      'Deep integration with Chrome and Safari on macOS',
      'Direct tab switching, page navigation, and URL resolution',
      'Automated scrolling, content scanning, and visual reading',
      'Context-aware interaction with active web sessions'
    ]
  },
  {
    id: 'live-web-intelligence',
    number: '04',
    title: 'Live Web Intelligence',
    subtitle: 'Powered by Anakin API',
    description: 'Retrieve current web information when a task requires live knowledge.',
    badge: 'ANAKIN POWERED',
    iconName: 'Compass',
    features: [
      'Live search and multi-source web retrieval via Anakin API',
      'Real-time grounding with verifiable citations [1†L1-L9]',
      'Deep multi-stage agentic research for market and tech comparisons',
      'Dynamic result caching into NOVA transient task context'
    ]
  },
  {
    id: 'contextual-followups',
    number: '05',
    title: 'Contextual Follow-Ups',
    subtitle: 'RecentInteractionContext Engine',
    description: 'Understand references such as "this tab", "that result", "the first one", and "the current task".',
    badge: 'STATEFUL MEMORY',
    iconName: 'GitMerge',
    features: [
      'Multi-turn task tracking without repeating prior instructions',
      'Anaphoric resolution linking pronouns to previous web/app results',
      'Unified context linking voice queries to active browser state',
      'Local JSON memory layer paired with vector semantic search'
    ]
  },
  {
    id: 'task-planning',
    number: '06',
    title: 'Task Planning',
    subtitle: 'Decomposition & Orchestration',
    description: 'Break user goals into executable steps.',
    badge: 'AGENTIC PLANNER',
    iconName: 'ListTree',
    features: [
      'Translates vague natural language goals into concrete execution steps',
      'Identifies prerequisite conditions before invoking system actions',
      'Dynamic routing to the optimal subsystem (Mac, Browser, Anakin, LLM)',
      'Graceful error handling and alternative path discovery on failure'
    ]
  },
  {
    id: 'action-verification',
    number: '07',
    title: 'Action Verification',
    subtitle: 'Closed-Loop Ground Truth',
    description: 'Check what actually happened instead of blindly claiming success.',
    badge: 'VERIFIED TRUTH',
    iconName: 'ShieldCheck',
    features: [
      'Explicit verify stage in every execution loop cycle',
      'Inspects system state, process output, and returned web sources',
      'Reports honest failures and missing configurations (/alert telemetry)',
      'Eliminates hallucinated actions common in stateless chatbots'
    ]
  },
  {
    id: 'media-system-control',
    number: '08',
    title: 'Media & System Control',
    subtitle: 'macOS Ambient Management',
    description: 'Handle supported media and system-level operations.',
    badge: 'MEDIA CONTROL',
    iconName: 'Sliders',
    features: [
      'System volume, display brightness, and hardware state adjustment',
      'Media playback control (play, pause, next track, volume leveling)',
      'Context-aware non-repeating music playback routines',
      'Active background telemetry tracking CPU, RAM, and Python memory'
    ]
  }
];
