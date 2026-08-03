/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        cream: {
          50:  '#fffdf9',
          100: '#faf6f0',
          200: '#f3ece0',
          300: '#e8ddd0',
        },
        brand: {
          50:  '#f5edf8',
          100: '#e9d8f2',
          200: '#d0afe3',
          300: '#b07fcf',
          400: '#8f55b8',
          500: '#6b2d9e',
          600: '#55207e',
          700: '#421862',
          800: '#32124b',
          900: '#220c33',
        },
        gold: {
          400: '#e0b84a',
          500: '#c9a027',
          600: '#a67e1a',
        },
      },
    },
  },
  plugins: [],
}
