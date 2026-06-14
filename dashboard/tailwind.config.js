export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060D1A',
          900: '#0A1628',
          800: '#0F1F3D',
          700: '#162B52',
          600: '#1E3A6E',
        },
        donna: {
          blue: '#2563EB',
          'blue-light': '#DBEAFE',
          gold: '#D97706',
          'gold-light': '#FEF3C7',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      animation: {
        'slide-up': 'slideUp 0.25s ease-out',
        'slide-right': 'slideRight 0.25s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'live-pulse': 'livePulse 2s ease-in-out infinite',
        'step-glow': 'stepGlow 1.5s ease-in-out infinite',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideRight: {
          '0%': { transform: 'translateX(16px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        livePulse: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(16,185,129,0.4)' },
          '50%': { boxShadow: '0 0 0 8px rgba(16,185,129,0)' },
        },
        stepGlow: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(37,99,235,0.4)' },
          '50%': { boxShadow: '0 0 0 6px rgba(37,99,235,0)' },
        },
      },
    },
  },
  plugins: [],
}
