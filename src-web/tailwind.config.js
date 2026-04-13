/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "geo-bg":      "#0d1117",
        "geo-surface": "#161b22",
        "geo-border":  "#30363d",
        "geo-text":    "#e6edf3",
        "geo-muted":   "#8b949e",
        "geo-accent":  "#1f6feb",
        "geo-green":   "#3fb950",
        "geo-red":     "#f85149",
      },
    },
  },
  plugins: [],
}
