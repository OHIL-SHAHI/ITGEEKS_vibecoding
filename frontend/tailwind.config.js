/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        palette: {
          bg: '#181414',
          header: '#231d1d',
          surface: '#2b2424',
          card: '#342c2c',
          border: '#524646',
          muted: '#A8A492',
          light: '#FCF2E5',
          accent: '#EC5B38',
          accentHover: '#ff714f',
        }
      },
      fontFamily: {
        sans: ['"Space Grotesk"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
