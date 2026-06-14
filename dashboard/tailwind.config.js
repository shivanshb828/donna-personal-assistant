export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#0D1014',
          900: '#1A1E29',
          800: '#252A38',
          700: '#363C4E',
          600: '#4A5062',
          400: '#8B8FA8',
          200: '#C8CADE',
          100: '#E8EAF2',
        },
        parchment: {
          50: '#FAFAF7',
          100: '#F5F3EF',
          200: '#EAE6DE',
          300: '#D9D3C6',
          400: '#B8AF9E',
        },
        legal: {
          navy: '#1B3A6B',
          'navy-mid': '#2B5299',
          'navy-light': '#EEF2F9',
          'navy-hover': '#163060',
          gold: '#9A6F0A',
          'gold-mid': '#B8860B',
          'gold-light': '#FDF5E4',
          'gold-border': '#E8C97A',
          crimson: '#8B1A1A',
          'crimson-light': '#FDF0F0',
          'crimson-border': '#F0B8B8',
          forest: '#1A5C38',
          'forest-light': '#EFF7F2',
          'forest-border': '#A8D9BC',
          amber: '#92400E',
          'amber-light': '#FFF8F0',
          'amber-border': '#F6C890',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        serif: ['"Playfair Display"', 'Georgia', 'Times New Roman', 'serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
      },
      animation: {
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-right': 'slideRight 0.3s ease-out',
        'fade-in': 'fadeIn 0.25s ease-out',
        'blink': 'blink 1.2s ease-in-out infinite',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideRight: {
          '0%': { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' },
        },
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
        'card-md': '0 4px 12px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.04)',
        'panel': '0 8px 24px rgba(0,0,0,0.10), 0 2px 6px rgba(0,0,0,0.06)',
      },
    },
  },
  plugins: [],
}
