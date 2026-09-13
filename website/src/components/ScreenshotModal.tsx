import React, { useEffect } from 'react';
import { X, ExternalLink, CheckCircle2 } from 'lucide-react';
import { ScreenshotItem } from '../types';

interface ScreenshotModalProps {
  screenshot: ScreenshotItem | null;
  onClose: () => void;
}

export const ScreenshotModal: React.FC<ScreenshotModalProps> = ({ screenshot, onClose }) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (screenshot) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [screenshot, onClose]);

  if (!screenshot) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-8 bg-black/85 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-6xl max-h-[92vh] flex flex-col bg-[#0b0e17] border border-white/15 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-[#121624] border-b border-white/10">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 text-xs font-mono font-semibold uppercase tracking-wider rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              {screenshot.badge}
            </span>
            <h3 className="text-base sm:text-lg font-semibold text-white">
              {screenshot.title}
            </h3>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={screenshot.imageSrc}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-slate-300 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors border border-white/10"
            >
              <span>Raw 4K</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
              aria-label="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-6">
          {/* Real Screenshot Preview */}
          <div className="rounded-xl overflow-hidden border border-white/10 shadow-lg bg-black">
            <img
              src={screenshot.imageSrc}
              alt={screenshot.caption}
              className="w-full h-auto object-contain max-h-[60vh] mx-auto block"
              loading="eager"
            />
          </div>

          {/* Telemetry and Highlights */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 p-4 rounded-xl bg-white/[0.03] border border-white/10">
              <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-3">
                Verified System Observations
              </h4>
              <ul className="space-y-2">
                {screenshot.keyHighlights.map((hl, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-sm text-slate-300">
                    <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                    <span>{hl}</span>
                  </li>
                ))}
              </ul>
            </div>

            {screenshot.terminalTelemetry && (
              <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-500/20 space-y-3">
                <h4 className="text-xs font-mono uppercase tracking-wider text-cyan-400">
                  Telemetry Snapshot
                </h4>
                <div className="space-y-2 text-xs font-mono">
                  {screenshot.terminalTelemetry.voiceState && (
                    <div>
                      <div className="text-slate-500">Voice State:</div>
                      <div className="text-slate-200 font-semibold">{screenshot.terminalTelemetry.voiceState}</div>
                    </div>
                  )}
                  {screenshot.terminalTelemetry.aiProvider && (
                    <div>
                      <div className="text-slate-500">Subsystem / Provider:</div>
                      <div className="text-cyan-300">{screenshot.terminalTelemetry.aiProvider}</div>
                    </div>
                  )}
                  {screenshot.terminalTelemetry.status && (
                    <div>
                      <div className="text-slate-500">Execution Status:</div>
                      <div className="text-emerald-400 font-semibold">{screenshot.terminalTelemetry.status}</div>
                    </div>
                  )}
                  {screenshot.terminalTelemetry.latency && (
                    <div>
                      <div className="text-slate-500">Speed / Metric:</div>
                      <div className="text-slate-300">{screenshot.terminalTelemetry.latency}</div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
