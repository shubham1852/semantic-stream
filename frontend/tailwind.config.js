/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // ── SemanticStream Design System ──────────────────────────────────────
      colors: {
        // Backgrounds
        'bg-primary':    '#0A0E1A',
        'bg-secondary':  '#0F1426',
        'bg-card':       '#151C34',

        // Accents
        'accent':        '#4F46E5',   // Indigo
        'accent-light':  '#818CF8',
        'accent-glow':   'rgba(79,70,229,0.35)',

        // Semantic data colors
        'data-green':    '#00FF87',   // Phosphor green — success / live / data
        'data-amber':    '#F59E0B',   // Warning
        'data-red':      '#EF4444',   // Error / Uniform ABR
        'data-blue':     '#60A5FA',   // Info

        // Priority tier colors (P1–P5)
        'tier-p1':  '#00FF87',   // Face — bright green
        'tier-p2':  '#4ADE80',   // Text — mid green
        'tier-p3':  '#F59E0B',   // Motion — amber
        'tier-p4':  '#818CF8',   // Objects — indigo-light
        'tier-p5':  '#EF4444',   // Background — red

        // Text
        'text-primary': '#F0F0FF',
        'text-muted':   '#8892A4',

        // Borders
        'border-subtle': 'rgba(79,70,229,0.18)',
      },

      fontFamily: {
        'display': ['"Space Grotesk"', 'sans-serif'],
        'body':    ['"Inter"', 'sans-serif'],
        'mono':    ['"JetBrains Mono"', 'monospace'],
      },

      fontSize: {
        'xs':   ['0.75rem',  { lineHeight: '1rem' }],
        'sm':   ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem',     { lineHeight: '1.5rem' }],
        'lg':   ['1.125rem', { lineHeight: '1.75rem' }],
        'xl':   ['1.25rem',  { lineHeight: '1.75rem' }],
        '2xl':  ['1.5rem',   { lineHeight: '2rem' }],
        '3xl':  ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl':  ['2.25rem',  { lineHeight: '2.5rem' }],
        '5xl':  ['3rem',     { lineHeight: '1' }],
        '6xl':  ['3.75rem',  { lineHeight: '1' }],
      },

      borderRadius: {
        'card':   '12px',
        'btn':    '8px',
        'badge':  '20px',
      },

      boxShadow: {
        'card':       '0 4px 24px rgba(0,0,0,0.4)',
        'card-hover': '0 8px 32px rgba(79,70,229,0.25)',
        'glow':       '0 0 20px rgba(79,70,229,0.4)',
        'glow-green': '0 0 20px rgba(0,255,135,0.3)',
      },

      backdropBlur: {
        'glass': '12px',
      },

      animation: {
        'pulse-slow':     'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'fade-in':        'fadeIn 0.3s ease-out',
        'slide-up':       'slideUp 0.4s ease-out',
        'glow-pulse':     'glowPulse 2s ease-in-out infinite',
        'scan':           'scan 2s linear infinite',
      },

      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(79,70,229,0.3)' },
          '50%':      { boxShadow: '0 0 40px rgba(79,70,229,0.6)' },
        },
        scan: {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },

      spacing: {
        'card-pad': '28px',
        '18': '4.5rem',
        '72': '18rem',
        '84': '21rem',
        '96': '24rem',
      },

      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [],
}
