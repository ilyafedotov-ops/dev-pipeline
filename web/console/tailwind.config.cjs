/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0b1220',
          panel: '#111a2e',
          muted: '#0f172a'
        },
        fg: {
          DEFAULT: '#e2e8f0',
          muted: '#94a3b8'
        },
        border: {
          DEFAULT: 'rgba(148,163,184,0.15)'
        }
      }
    },
  },
  plugins: [],
};
