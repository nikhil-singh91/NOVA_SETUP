import React, { useEffect, useState } from 'react';
import { AvatarState } from '../../types';

interface NovaAvatarProps {
  state: AvatarState;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  className?: string;
  onClick?: () => void;
}

export const NovaAvatar: React.FC<NovaAvatarProps> = ({
  state,
  size = 'md',
  className = '',
  onClick,
}) => {
  const [blink, setBlink] = useState(false);
  const [mouthOpen, setMouthOpen] = useState(0);

  // Periodic natural blinking
  useEffect(() => {
    if (state === 'offline') return;
    const interval = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 160);
    }, 4000 + Math.random() * 2500);
    return () => clearInterval(interval);
  }, [state]);

  // Speaking mouth dynamics
  useEffect(() => {
    if (state !== 'speaking') {
      setMouthOpen(0);
      return;
    }
    const interval = setInterval(() => {
      setMouthOpen(Math.random() * 0.7 + 0.3);
    }, 120);
    return () => clearInterval(interval);
  }, [state]);

  // Dimensions constrained to max 220px for hero
  const dimensionClasses = {
    sm: 'w-12 h-12',
    md: 'w-24 h-24',
    lg: 'w-40 h-40',
    hero: 'w-52 h-52 max-w-[220px] max-h-[220px]',
  }[size];

  // Theme palettes per state
  const stateThemes: Record<AvatarState, { glow: string; halo: string; accent: string; badgeBg: string }> = {
    idle: { glow: '#818cf8', halo: 'rgba(99, 102, 241, 0.2)', accent: '#a5b4fc', badgeBg: 'rgba(99, 102, 241, 0.15)' },
    listening: { glow: '#06b6d4', halo: 'rgba(6, 182, 212, 0.35)', accent: '#67e8f9', badgeBg: 'rgba(6, 182, 212, 0.2)' },
    thinking: { glow: '#a855f7', halo: 'rgba(168, 85, 247, 0.35)', accent: '#d8b4fe', badgeBg: 'rgba(168, 85, 247, 0.2)' },
    planning: { glow: '#6366f1', halo: 'rgba(99, 102, 241, 0.35)', accent: '#818cf8', badgeBg: 'rgba(99, 102, 241, 0.2)' },
    executing: { glow: '#3b82f6', halo: 'rgba(59, 130, 246, 0.35)', accent: '#93c5fd', badgeBg: 'rgba(59, 130, 246, 0.2)' },
    verifying: { glow: '#14b8a6', halo: 'rgba(20, 184, 166, 0.35)', accent: '#5eead4', badgeBg: 'rgba(20, 184, 166, 0.2)' },
    speaking: { glow: '#00f0ff', halo: 'rgba(0, 240, 255, 0.4)', accent: '#38bdf8', badgeBg: 'rgba(0, 240, 255, 0.2)' },
    success: { glow: '#10b981', halo: 'rgba(16, 185, 129, 0.4)', accent: '#6ee7b7', badgeBg: 'rgba(16, 185, 129, 0.2)' },
    confused: { glow: '#f59e0b', halo: 'rgba(245, 158, 11, 0.35)', accent: '#fde68a', badgeBg: 'rgba(245, 158, 11, 0.2)' },
    error: { glow: '#ef4444', halo: 'rgba(239, 68, 68, 0.4)', accent: '#fca5a5', badgeBg: 'rgba(239, 68, 68, 0.2)' },
    offline: { glow: '#475569', halo: 'rgba(71, 85, 105, 0.1)', accent: '#94a3b8', badgeBg: 'rgba(71, 85, 105, 0.2)' },
  };

  const theme = stateThemes[state] || stateThemes.idle;

  // Eyebrow vertical offsets
  const leftEyebrowOffset = state === 'thinking' || state === 'confused' ? -3 : state === 'error' ? 2 : 0;
  const rightEyebrowOffset = state === 'confused' ? 3 : state === 'thinking' ? -3 : state === 'error' ? 2 : 0;

  // Mouth curve
  const mouthCurve = () => {
    if (state === 'speaking') {
      const h = mouthOpen * 6;
      return `M 43 74 Q 50 ${74 + h} 57 74 Q 50 ${74 - h * 0.3} 43 74 Z`;
    }
    if (state === 'success') {
      return 'M 42 73 Q 50 80 58 73';
    }
    if (state === 'confused') {
      return 'M 43 74 Q 50 73 57 75';
    }
    if (state === 'error') {
      return 'M 43 76 Q 50 73 57 76';
    }
    return 'M 43 74 Q 50 77 57 74';
  };

  return (
    <div
      onClick={onClick}
      className={`relative flex items-center justify-center select-none ${dimensionClasses} ${className}`}
      title={`NOVA: ${state.toUpperCase()}`}
    >
      {/* Outer Halo Ring */}
      <div
        className="absolute inset-0 rounded-full animate-slow-orbit transition-all duration-700 pointer-events-none"
        style={{
          border: `1px dashed ${theme.glow}`,
          boxShadow: `0 0 24px ${theme.halo}, inset 0 0 16px ${theme.halo}`,
          opacity: state === 'offline' ? 0.15 : 0.7,
        }}
      />

      {/* Ambient Core Glow */}
      <div
        className="absolute inset-2 rounded-full animate-subtle-glow transition-all duration-700 pointer-events-none"
        style={{
          background: `radial-gradient(circle, ${theme.halo} 0%, rgba(8, 12, 20, 0) 70%)`,
        }}
      />

      {/* Vector SVG Avatar Anatomy */}
      <svg
        viewBox="0 0 100 100"
        className="w-full h-full relative z-10 filter drop-shadow-md animate-subtle-breath"
      >
        <defs>
          <linearGradient id="skinGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#c7d2fe" stopOpacity="0.2" />
            <stop offset="60%" stopColor="#818cf8" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#0f172a" stopOpacity="0.85" />
          </linearGradient>

          <linearGradient id="hairGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#4338ca" />
            <stop offset="50%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>

          <linearGradient id="eyeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor={theme.accent} />
          </linearGradient>
        </defs>

        {/* Neck */}
        <path d="M 45 81 L 45 92 L 55 92 L 55 81 Z" fill="#1e1b4b" opacity="0.8" />
        <path d="M 38 92 Q 50 87 62 92 L 65 98 L 35 98 Z" fill="#0f172a" stroke={theme.glow} strokeWidth="0.4" />

        {/* Hair Back Silhouette */}
        <path
          d="M 30 40 Q 24 64 32 82 Q 50 89 68 82 Q 76 64 70 40 Q 50 18 30 40 Z"
          fill="url(#hairGrad)"
          opacity="0.85"
        />

        {/* Face Base */}
        <path
          d="M 34 42 Q 33 66 50 80 Q 67 66 66 42 Q 66 26 50 26 Q 34 26 34 42 Z"
          fill="url(#skinGrad)"
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="0.6"
        />

        {/* Headband Accent */}
        <path
          d="M 32 36 Q 50 31 68 36"
          fill="none"
          stroke={theme.glow}
          strokeWidth="1"
          opacity="0.85"
        />
        <circle cx="32" cy="36" r="1.2" fill={theme.glow} />
        <circle cx="68" cy="36" r="1.2" fill={theme.glow} />

        {/* Eyebrows */}
        <path
          d={`M 38 ${47 + leftEyebrowOffset} Q 42 ${44 + leftEyebrowOffset} 46 ${47 + leftEyebrowOffset}`}
          fill="none"
          stroke="#94a3b8"
          strokeWidth="1"
          strokeLinecap="round"
        />
        <path
          d={`M 54 ${47 + rightEyebrowOffset} Q 58 ${44 + rightEyebrowOffset} 62 ${47 + rightEyebrowOffset}`}
          fill="none"
          stroke="#94a3b8"
          strokeWidth="1"
          strokeLinecap="round"
        />

        {/* Left Eye */}
        <g>
          {blink ? (
            <path d="M 38 53 Q 42 55 46 53" fill="none" stroke={theme.glow} strokeWidth="1" />
          ) : (
            <>
              <ellipse cx="42" cy="53" rx="4" ry="2.8" fill="#0b1120" stroke="rgba(255,255,255,0.15)" strokeWidth="0.5" />
              <circle cx="42" cy="53" r="1.8" fill="url(#eyeGrad)" />
              <circle cx="42.6" cy="52.4" r="0.6" fill="#ffffff" />
            </>
          )}
        </g>

        {/* Right Eye */}
        <g>
          {blink ? (
            <path d="M 54 53 Q 58 55 62 53" fill="none" stroke={theme.glow} strokeWidth="1" />
          ) : (
            <>
              <ellipse cx="58" cy="53" rx="4" ry="2.8" fill="#0b1120" stroke="rgba(255,255,255,0.15)" strokeWidth="0.5" />
              <circle cx="58" cy="53" r="1.8" fill="url(#eyeGrad)" />
              <circle cx="58.6" cy="52.4" r="0.6" fill="#ffffff" />
            </>
          )}
        </g>

        {/* Nose Line */}
        <path d="M 50 54 L 49.4 61 Q 50 62.5 51.2 62" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.5" strokeLinecap="round" />

        {/* Mouth */}
        <path
          d={mouthCurve()}
          fill={state === 'speaking' ? '#0f172a' : 'none'}
          stroke={theme.accent}
          strokeWidth="1"
          strokeLinecap="round"
        />

        {/* Front Hair Bangs */}
        <path
          d="M 34 36 Q 39 46 36 56 Q 43 35 50 31 Q 57 35 64 56 Q 61 46 66 36 Z"
          fill="url(#hairGrad)"
          opacity="0.9"
        />
      </svg>

      {/* State Badge */}
      {size !== 'sm' && (
        <div
          className="absolute -bottom-2 px-2 py-0.5 rounded-full text-[9px] font-mono tracking-wider font-semibold uppercase border transition-all duration-300 backdrop-blur-md"
          style={{
            color: theme.accent,
            backgroundColor: theme.badgeBg,
            borderColor: theme.glow,
          }}
        >
          {state}
        </div>
      )}
    </div>
  );
};
