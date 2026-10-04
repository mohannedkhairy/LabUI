// Tailwind build config for the BENCH design language (see base.html).
// Rebuild after editing templates:  npm run build:css
module.exports = {
  darkMode: "class",
  content: [
    "./submission_strategy/jfr/web/templates/**/*.html",
    "./submission_strategy/jfr/web/static/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Public Sans"', "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        // Warm neutral ramp. Light→dark, so `bg-ink-50` / `dark:bg-ink-900`
        // in existing templates keep meaning what they meant.
        ink: {
          50: "#faf7f1", 100: "#f1ebe1",
          200: "#e3dacb", 300: "#c8bca8",
          400: "#9a9184", 500: "#6e675d",
          600: "#4e4941", 700: "#3a352e",
          800: "#262320", 900: "#1a1815",
          950: "#100f0d",
        },
        // Signal vermillion — the one loud colour, used sparingly.
        brand: {
          50: "#fdf0ec", 100: "#fbddd4", 200: "#f7bcab",
          300: "#f1937a", 400: "#e96a48", 500: "#de4b2c",
          600: "#c33a1e", 700: "#9e2d17", 800: "#7a2413",
          900: "#5c1c10", 950: "#35100a",
        },
        // Data teal — measurements, positive states, secondary emphasis.
        data: {
          50: "#e6f5f2", 100: "#c3e8e2", 200: "#8fd4c9",
          300: "#55bcae", 400: "#26a094", 500: "#0e7c6e",
          600: "#0a6459", 700: "#095047", 800: "#0a3f39",
          900: "#08322e", 950: "#041e1b",
        },
        // Live chartreuse — streaming / running / "happening now".
        live: {
          50: "#f7fae4", 100: "#edf3c3", 200: "#dde78d",
          300: "#c8d84f", 400: "#b0c42c", 500: "#8fa31e",
          600: "#6f8017", 700: "#556214", 800: "#434d15",
          900: "#394115", 950: "#1d2306",
        },
      },
      boxShadow: {
        soft: "0 1px 0 rgba(23,21,18,0.04), 0 1px 2px rgba(23,21,18,0.04)",
        "soft-dark": "0 1px 0 rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        lift: "0 2px 4px rgba(23,21,18,0.05), 0 12px 28px -14px rgba(23,21,18,0.22)",
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
};
