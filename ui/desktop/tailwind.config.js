/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        nova: {
          bg: '#080c14',
          surface: '#0d121f',
          elevated: '#131b2e',
          accent: '#6366f1',
          accentGlow: 'rgba(99, 102, 241, 0.35)',
          cyan: '#00f0ff',
          purple: '#8b5cf6',
          violet: '#a855f7',
          emerald: '#10b981',
          amber: '#f59e0b',
          rose: '#ef4444',
          border: 'rgba(255, 255, 255, 0.08)',
          borderHover: 'rgba(99, 102, 241, 0.3)',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backdropBlur: {
        xs: '2px',
        md: '12px',
        lg: '16px',
        xl: '24px',
      }
    },
  },
  plugins: [],
}
