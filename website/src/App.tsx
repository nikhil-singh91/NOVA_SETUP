import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { ProblemSection } from './components/ProblemSection';
import { WhatIsNova } from './components/WhatIsNova';
import { RealNovaGallery } from './components/RealNovaGallery';
import { CapabilitiesSection } from './components/CapabilitiesSection';
import { AnakinIntegrationSection } from './components/AnakinIntegrationSection';
import { AgentLoopSection } from './components/AgentLoopSection';
import { ArchitectureSection } from './components/ArchitectureSection';
import { WorkflowSimulation } from './components/WorkflowSimulation';
import { ComputerUseSection } from './components/ComputerUseSection';
import { ContextEngineSection } from './components/ContextEngineSection';
import { DemoSection } from './components/DemoSection';
import { PrivacySection } from './components/PrivacySection';
import { TechStackSection } from './components/TechStackSection';
import { HackathonSection } from './components/HackathonSection';
import { FinalCTA } from './components/FinalCTA';
import { Footer } from './components/Footer';
import { ScreenshotModal } from './components/ScreenshotModal';
import { ScreenshotItem } from './types';
import { SCREENSHOTS_DATA } from './data/screenshotsData';

export function App() {
  const [activeModalScreenshot, setActiveModalScreenshot] = useState<ScreenshotItem | null>(null);

  const scrollToDemo = () => {
    const el = document.getElementById('demo');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Sticky/Floating Navigation */}
      <Navbar onWatchDemo={scrollToDemo} />

      <main className="flex-grow">
        {/* 1. Hero Section with Real NOVA Dashboard */}
        <Hero
          onWatchDemo={scrollToDemo}
          onInspectScreenshot={() => setActiveModalScreenshot(SCREENSHOTS_DATA[0])}
        />

        {/* 2. The Problem: AI can answer. But can it act? */}
        <ProblemSection />

        {/* 3. Meet NOVA: Turns natural language into computer actions */}
        <WhatIsNova />

        {/* 4. Real NOVA: 3 authentic Retina screenshots evidence gallery */}
        <RealNovaGallery
          onSelectScreenshot={(item) => setActiveModalScreenshot(item)}
        />

        {/* 5. Capabilities: 8 verified capability cards */}
        <CapabilitiesSection />

        {/* 6. NOVA × Anakin: Live Web Intelligence Centerpiece */}
        <AnakinIntegrationSection
          onInspectAnakinScreenshot={() => setActiveModalScreenshot(SCREENSHOTS_DATA[1])}
        />

        {/* 7. Why This Is An Agent: Understand → Plan → Act → Observe → Verify */}
        <AgentLoopSection />

        {/* 8. Architecture: Inside NOVA blueprint */}
        <ArchitectureSection />

        {/* 9. Actual Workflow: Interactive 7-step timeline */}
        <WorkflowSimulation />

        {/* 10. Computer Use: The computer becomes actionable */}
        <ComputerUseSection />

        {/* 11. Context Engine: Context changes everything */}
        <ContextEngineSection />

        {/* 12. Demo Section */}
        <DemoSection
          onInspectCockpit={() => setActiveModalScreenshot(SCREENSHOTS_DATA[0])}
        />

        {/* 13. Privacy & Local-First Philosophy */}
        <PrivacySection />

        {/* 14. Technology: Built with */}
        <TechStackSection />

        {/* 15. Hackathon: Built for Anakin Forge 2026 */}
        <HackathonSection />

        {/* 16. Final CTA */}
        <FinalCTA onWatchDemo={scrollToDemo} />
      </main>

      {/* 17. Minimal Premium Footer */}
      <Footer />

      {/* Fullscreen Lightbox Inspector Modal */}
      <ScreenshotModal
        screenshot={activeModalScreenshot}
        onClose={() => setActiveModalScreenshot(null)}
      />
    </div>
  );
}

export default App;
