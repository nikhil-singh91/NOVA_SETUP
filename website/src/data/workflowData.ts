import { WorkflowStep } from '../types';

export const ACTUAL_WORKFLOW_STEPS: WorkflowStep[] = [
  {
    step: 1,
    label: 'STEP 01',
    title: 'Natural Language Understanding',
    actor: 'NOVA',
    subsystem: 'Intent Matcher & NLP Core',
    description: 'NOVA captures the spoken prompt, parses semantic intent, and resolves constraints (category: smartphone, budget limit: ₹20,000 INR).',
    logOutput: 'UNDERSTOOD: Intent: Live Web Research | Query: "best smartphones under 20000" | Subsystem: Anakin Live Web Intelligence'
  },
  {
    step: 2,
    label: 'STEP 02',
    title: 'Live Web Requirement Detection',
    actor: 'NOVA',
    subsystem: 'Capability Registry',
    description: 'Internal knowledge is marked as insufficient for volatile market pricing. The system checks external capability adapters and flags live web grounding as mandatory.',
    logOutput: 'ROUTING: Volatile pricing detected → Live Web Grounding required → Selecting Anakin Service Adapter'
  },
  {
    step: 3,
    label: 'STEP 03',
    title: 'Anakin Intelligence Dispatch',
    actor: 'ANAKIN',
    subsystem: 'Anakin Web Intelligence API',
    description: 'NOVA constructs a structured query payload and dispatches it to Anakin Live Web Intelligence API for real-time aggregation across current retailer & tech review indices.',
    logOutput: 'ACTION: Anakin web research started for "best smartphones under 20000 INR"'
  },
  {
    step: 4,
    label: 'STEP 04',
    title: 'Current Source Ingestion',
    actor: 'ANAKIN',
    subsystem: 'Anakin Web Crawler & Normalizer',
    description: 'Anakin scans verified domains, indexes current release dates, processor specs, and real-time discounted prices, returning 5 verified source payloads with citations.',
    logOutput: 'ACTION: Anakin returned 5 sources [Bajaj Finance, Indian Express, 91mobiles, Smartprix, TechRadar]'
  },
  {
    step: 5,
    label: 'STEP 05',
    title: 'Contextual Reasoning & Synthesis',
    actor: 'NOVA',
    subsystem: 'Multi-Provider LLM + Memory',
    description: 'NOVA merges retrieved source data into RecentInteractionContext, analyzes specifications (Dimensity 6020, 120Hz display, 5G bands), and ranks contenders by value.',
    logOutput: 'SYNTHESIS: Ranking 7 contenders: POCO M7 5G, Redmi 13C 5G, Samsung Galaxy A06, Redmi A4+, Moto G35'
  },
  {
    step: 6,
    label: 'STEP 06',
    title: 'Multi-Modal Result Output',
    actor: 'NOVA',
    subsystem: 'Terminal Cockpit + Speech TTS',
    description: 'Formatted markdown table rendered on the terminal cockpit feed, while companion voice speaks a crisp summary of top recommendations with source citations.',
    logOutput: 'RESULT: Top pick POCO M7 5G (₹9,999) + 4 contenders. Formatted table output to activity feed.'
  },
  {
    step: 7,
    label: 'STEP 07',
    title: 'Execution Loop Verification',
    actor: 'VERIFY',
    subsystem: 'Action Verification Layer',
    description: 'System verifies that 5 sources were validated, citations are non-empty, and results are safely stored in active context for immediate follow-up commands.',
    logOutput: 'VERIFY: ✓ Live web research successful | Context state updated (recent_research_id: anakin_5000_ok)'
  }
];
