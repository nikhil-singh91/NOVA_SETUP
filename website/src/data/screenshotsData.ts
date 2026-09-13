import { ScreenshotItem } from '../types';

export const SCREENSHOTS_DATA: ScreenshotItem[] = [
  {
    id: 'dashboard',
    title: 'Operations Control Center',
    badge: 'LIVE COCKPIT RUNTIME',
    imageSrc: '/assets/nova-dashboard.png',
    caption: 'NOVA Operations Control Center',
    description: 'Live runtime state, providers, system performance, memory, Mac control and activity feed.',
    keyHighlights: [
      'Multi-Provider AI telemetry: Gemini (607ms), Groq (626ms), OpenRouter (1.14s), Cerebras health monitoring',
      'Local Whisper STT & speech confidence monitoring',
      'Local JSON Memory Layer with active Semantic DB',
      'Real-time CPU, RAM, Python memory (779MB), and 7 active system threads',
      'Interactive terminal control commands: /filter, /clear, /search, /jump, /scroll, /max'
    ],
    terminalTelemetry: {
      voiceState: 'listening (STANDBY)',
      aiProvider: 'OpenRouter / Multi-Fallback',
      subsystem: 'Core Orchestration Cockpit',
      status: 'HEALTHY',
      latency: '607ms'
    }
  },
  {
    id: 'voice',
    title: 'Voice-First Interaction & Task Execution',
    badge: 'REAL RUNTIME FEED',
    imageSrc: '/assets/nova-voice.png',
    caption: 'Voice-first interaction & task loop',
    description: 'NOVA continuously handles voice input and maintains an active task context.',
    keyHighlights: [
      'Heard: "Nova, can you search the phone under 5000?"',
      'Understood: Intent "Live Web Research" routed to Anakin Live Web Intelligence',
      'Action: Anakin web research started for "the phone under 5000"',
      'Action: Anakin returned 5 sources in 1 second',
      'Verify: ✓ Live web research successful',
      'Result: ✓ Found 5 sources'
    ],
    terminalTelemetry: {
      voiceState: 'speaking (58% Conf)',
      aiProvider: 'Anakin Live Web Subsystem',
      subsystem: 'Speech + Anakin Web Intelligence',
      status: 'SUCCESS (N/A)',
      latency: '1.2s round-trip'
    }
  },
  {
    id: 'anakin-research',
    title: 'Live Web Research Synthesis',
    badge: 'ANAKIN GROUNDED RESEARCH',
    imageSrc: '/assets/nova-anakin-research.png',
    caption: 'Live web research synthesis with verified citations',
    description: 'An actual NOVA workflow using live web intelligence to retrieve and summarize current information.',
    keyHighlights: [
      'Grounded in 5 live web sources with citations [1†L1-L9] and [2†L31-L38]',
      'Real-time Indian smartphone market pricing (POCO M7 5G, Redmi 13C, Samsung Galaxy A06, Moto G35)',
      'Structured technical specification comparison table synthesized dynamically',
      'Preserved in RecentInteractionContext for follow-up conversational queries',
      'Seamless transition from web intelligence to voice delivery and macOS control'
    ],
    terminalTelemetry: {
      voiceState: 'speaking (54% Conf)',
      aiProvider: 'Anakin Web Retrieval + Gemini/Groq Reasoner',
      subsystem: 'Live Web Intelligence Layer',
      status: 'GROUNDED SYNTHESIS',
      latency: '5 sources retrieved'
    }
  }
];
