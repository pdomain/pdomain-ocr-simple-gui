/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // bg tokens
        "bg-page": "var(--bg-page)",
        "bg-surface": "var(--bg-surface)",
        "bg-raised": "var(--bg-raised)",
        "bg-sunk": "var(--bg-sunk)",
        // border tokens
        "border-1": "var(--border-1)",
        "border-2": "var(--border-2)",
        "border-3": "var(--border-3)",
        // ink tokens
        "ink-1": "var(--ink-1)",
        "ink-2": "var(--ink-2)",
        "ink-3": "var(--ink-3)",
        "ink-4": "var(--ink-4)",
        // accent
        accent: "var(--accent)",
        "accent-ink": "var(--accent-ink)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        xxs: ["10px", { lineHeight: "1.2" }],
        xs2: ["11px", { lineHeight: "1.3" }],
      },
    },
  },
  plugins: [],
};
