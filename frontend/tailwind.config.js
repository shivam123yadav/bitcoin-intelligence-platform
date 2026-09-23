/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      borderColor: ({ theme }) => ({
        DEFAULT: theme('colors.ink.700', '#1a2030'),
        ...theme('colors'),
      }),
      colors: {
        // Intelligence console palette
        ink: {
          950: '#070a10',
          900: '#0a0e16',
          850: '#0d1119',
          800: '#10151f',
          750: '#141a26',
          700: '#1a2030',
          600: '#232b3d',
          500: '#2e3850',
          400: '#465670',
          300: '#6b7a96',
          200: '#9aa6bd',
          100: '#c5cdda',
        },
        // Semantic colors
        signal: {
          // blue — normal info
          50: '#eaf2ff',
          400: '#3b82f6',
          500: '#2b6cf0',
          600: '#1d50c8',
        },
        warn: {
          // amber — medium priority
          50: '#fef6e7',
          400: '#f5a623',
          500: '#e8900a',
          600: '#c47605',
        },
        critical: {
          // red — high priority
          50: '#fdeaea',
          400: '#ef4444',
          500: '#dc2626',
          600: '#b91c1c',
        },
        ok: {
          // green — verified / normal
          50: '#e9f9ef',
          400: '#22c55e',
          500: '#16a34a',
          600: '#15803d',
        },
        intel: {
          // cyan/purple — analytics / ML
          50: '#ecfaff',
          400: '#06b6d4',
          500: '#0891b2',
          600: '#0e7490',
        },
        ml: {
          50: '#f3ecff',
          400: '#8b5cf6',
          500: '#7c3aed',
          600: '#6d28d9',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.02em' }],
      },
      boxShadow: {
        'panel': '0 1px 2px 0 rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.03)',
        'panel-lg': '0 4px 24px -6px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)',
        'glow-signal': '0 0 0 1px rgba(59,130,246,0.4), 0 0 12px -2px rgba(59,130,246,0.25)',
        'glow-critical': '0 0 0 1px rgba(239,68,68,0.4), 0 0 12px -2px rgba(239,68,68,0.25)',
      },
      animation: {
        'fade-in': 'fadeIn 0.25s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'shimmer': 'shimmer 1.5s linear infinite',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        pulseSoft: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0.5' } },
        shimmer: { '0%': { backgroundPosition: '-1000px 0' }, '100%': { backgroundPosition: '1000px 0' } },
      },
    },
  },
  plugins: [],
};
