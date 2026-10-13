/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        obs: {
          bg: {
            base: "var(--obs-bg-base)",
            surface: "var(--obs-bg-surface)",
            elevated: "var(--obs-bg-surface-elevated)",
          },
          border: {
            subtle: "var(--obs-border-subtle)",
            active: "var(--obs-border-active)",
          },
          text: {
            primary: "var(--obs-text-primary)",
            secondary: "var(--obs-text-secondary)",
            muted: "var(--obs-text-muted)",
          },
        },
        risk: {
          low: "var(--risk-low)",
          moderate: "var(--risk-moderate)",
          high: "var(--risk-high)",
        },
        circadian: {
          sleep: "var(--circadian-sleep)",
          deep: "var(--circadian-deep)",
          rem: "var(--circadian-rem)",
          hrv: "var(--circadian-hrv)",
          bp: "var(--circadian-bp)",
          med: "var(--circadian-med)",
          activity: "var(--circadian-activity)",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        serif: ["'Source Serif 4'", "Georgia", "serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};
