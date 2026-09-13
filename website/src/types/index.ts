export interface ScreenshotItem {
  id: string;
  title: string;
  badge: string;
  imageSrc: string;
  caption: string;
  description: string;
  keyHighlights: string[];
  terminalTelemetry?: {
    voiceState?: string;
    aiProvider?: string;
    subsystem?: string;
    status?: string;
    latency?: string;
  };
}

export interface CapabilityItem {
  id: string;
  number: string;
  title: string;
  subtitle: string;
  description: string;
  badge: string;
  iconName: string;
  features: string[];
}

export interface WorkflowStep {
  step: number;
  label: string;
  title: string;
  actor: 'USER' | 'NOVA' | 'ANAKIN' | 'VERIFY';
  description: string;
  subsystem?: string;
  logOutput?: string;
}

export interface ArchitectureNode {
  id: string;
  category: 'core' | 'intelligence' | 'execution' | 'verification';
  title: string;
  tagline: string;
  details: string;
  subsystems: string[];
}
