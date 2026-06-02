/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          '900/80': 'rgb(15 23 42 / 0.8)',
          '950/20': 'rgb(3 7 18 / 0.2)',
          '950/30': 'rgb(3 7 18 / 0.3)',
          '950/60': 'rgb(3 7 18 / 0.6)',
          '950/80': 'rgb(3 7 18 / 0.8)',
          '950/90': 'rgb(3 7 18 / 0.9)',
          '800/30': 'rgb(30 41 59 / 0.3)',
          '800/50': 'rgb(30 41 59 / 0.5)',
        },
        cyan: {
          '300/80': 'rgb(165 243 252 / 0.8)',
        },
      },
      backdropBlur: {
        xl: '20px',
      },
      boxShadow: {
        glow: '0 0 20px rgba(56, 189, 248, 0.4)',
      },
    },
  },
  plugins: [],
}