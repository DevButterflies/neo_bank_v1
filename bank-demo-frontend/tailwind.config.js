/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0B1014",
        panel: "#121A21",
        raised: "#182229",
        line: "#243039",
        text: "#E7ECEF",
        muted: "#8697A6",
        faint: "#5C6A76",
        ledger: "#2FBF9F",
        ledgerDim: "#1D5F50",
        amber: "#E8A33D",
        danger: "#E5566A",
        info: "#5B8DEF",
      },
      fontFamily: {
        head: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      borderRadius: {
        sm: "3px",
        md: "5px",
      },
    },
  },
  plugins: [],
};
