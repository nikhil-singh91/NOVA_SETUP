export const ANAKIN_FLOW_STEPS = [
  { id: 'user', label: 'USER', role: 'Initiator', desc: 'Voice input: "Nova, can you search the phone under 5000?"' },
  { id: 'nova', label: 'NOVA', role: 'Listener', desc: 'Local Whisper engine captures audio and passes to Intent Matcher' },
  { id: 'understand', label: 'UNDERSTAND', role: 'Classifier', desc: 'Resolves Intent: Live Web Research (Query: "the phone under 5000")' },
  { id: 'cap-check', label: 'CAPABILITY CHECK', role: 'Registry', desc: 'Checks CapabilityRegistry; confirms Anakin API is configured & healthy' },
  { id: 'anakin', label: 'ANAKIN', role: 'Intelligence Layer', desc: 'Routes query to Anakin Live Web Intelligence API' },
  { id: 'live-web', label: 'LIVE WEB', role: 'Retrieval', desc: 'Anakin scans active web indexes, e-commerce listings, and tech reviews' },
  { id: 'sources', label: 'CURRENT SOURCES', role: 'Evidence', desc: 'Anakin returns 5 structured sources with citations [1†L1-L9], [2†L31-L38]' },
  { id: 'nova-context', label: 'NOVA CONTEXT', role: 'Memory Sync', desc: 'Sources loaded into RecentInteractionContext for multi-turn follow-ups' },
  { id: 'reason', label: 'REASON', role: 'Synthesis', desc: 'NOVA reasons over live data, generating comparison table & top picks' },
  { id: 'act', label: 'ACT', role: 'Execution', desc: 'Terminal activity feed updates; voice response speaks synthesis' },
  { id: 'verify', label: 'VERIFY', role: 'Closed Loop', desc: '✓ Live web research successful (Found 5 sources, verified complete)' }
];

export const ROLE_COMPARISON = {
  nova: [
    { title: 'Voice & Speech Pipeline', desc: 'Whisper STT capture, confidence scoring, and companion voice synthesis' },
    { title: 'Intent Classification', desc: 'Maps spoken requests to system actions, browser tasks, or research intents' },
    { title: 'Context & Memory Engine', desc: 'Tracks active window state, previous queries, and multi-turn references' },
    { title: 'Task Planning & Execution', desc: 'Decomposes complex goals into sequential sub-tasks across OS and web' },
    { title: 'macOS Native Control', desc: 'Operates local apps, windows, media controls, and keystrokes' },
    { title: 'Browser Interaction', desc: 'Controls Chrome/Safari tabs, clicks, scrolls, and views web pages' },
    { title: 'Action Verification', desc: 'Inspects process outputs to confirm task reality before reporting success' }
  ],
  anakin: [
    { title: 'Live Web Search', desc: 'Sub-second search across live internet databases for fresh information' },
    { title: 'Multi-Source Retrieval', desc: 'Aggregates content, prices, and articles from verified external domains' },
    { title: 'Deep Agentic Web Research', desc: 'Multi-stage autonomous exploration for comprehensive market comparisons' },
    { title: 'Structured Web Sources', desc: 'Delivers normalized WebSource objects with exact citations and timestamps' }
  ]
};

export const REAL_LOG_TIMELINE = [
  {
    time: '17:12:50',
    type: 'HEARD',
    color: 'text-cyan-400',
    content: '"Nova, can you search the phone under 5000?"'
  },
  {
    time: '17:12:50',
    type: 'UNDERSTOOD',
    color: 'text-purple-400',
    content: 'Intent: Live Web Research | Query: the phone under 5000 | Mode: search | Subsystem: Anakin Live Web Intelligence'
  },
  {
    time: '17:12:50',
    type: 'ACTION',
    color: 'text-yellow-400',
    content: "Anakin web research started for 'the phone under 5000'"
  },
  {
    time: '17:12:51',
    type: 'ACTION',
    color: 'text-yellow-400',
    content: 'Anakin returned 5 sources'
  },
  {
    time: '17:12:52',
    type: 'VERIFY',
    color: 'text-emerald-400',
    content: '✓ Live web research successful'
  },
  {
    time: '17:12:52',
    type: 'RESULT',
    color: 'text-emerald-300',
    content: '✓ Found 5 sources'
  }
];
