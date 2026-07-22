module.exports = {
  darkMode: "class",
  content: [
    "./submission_strategy/jfr/web/templates/**/*.html",
    "./submission_strategy/jfr/web/static/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "ui-sans-serif", "SF Pro Text", "Helvetica Neue", "Inter", "system-ui", "sans-serif"],
        serif: ["ui-serif", "New York", "Source Serif 4", "Georgia", "serif"],
        mono: ["ui-monospace", "SF Mono", "Menlo", "IBM Plex Mono", "monospace"],
        rounded: ["ui-rounded", "SF Pro Rounded", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
      },
      colors: {
        ink: {
          50: "#f7f8fa", 100: "#eef0f4", 200: "#dde1e8", 300: "#bfc6d2",
          400: "#8b94a6", 500: "#5a6478", 600: "#3e4759", 700: "#2a3142",
          800: "#1c2230", 900: "#12161f", 950: "#0a0d14",
        },
        gray: {
          50: "#f7f8fa", 100: "#eef0f4", 200: "#dde1e8", 300: "#bfc6d2",
          400: "#8b94a6", 500: "#5a6478", 600: "#3e4759", 700: "#2a3142",
          800: "#1c2230", 900: "#12161f", 950: "#0a0d14",
        },
        brand: {
          50: "rgb(var(--brand-50) / <alpha-value>)",
          100: "rgb(var(--brand-100) / <alpha-value>)",
          200: "rgb(var(--brand-200) / <alpha-value>)",
          300: "rgb(var(--brand-300) / <alpha-value>)",
          400: "rgb(var(--brand-400) / <alpha-value>)",
          500: "rgb(var(--brand-500) / <alpha-value>)",
          600: "rgb(var(--brand-600) / <alpha-value>)",
          700: "rgb(var(--brand-700) / <alpha-value>)",
          800: "rgb(var(--brand-800) / <alpha-value>)",
          900: "rgb(var(--brand-900) / <alpha-value>)",
          950: "rgb(var(--brand-950) / <alpha-value>)",
        },
        indigo: {
          50: "rgb(var(--brand-50) / <alpha-value>)",
          100: "rgb(var(--brand-100) / <alpha-value>)",
          200: "rgb(var(--brand-200) / <alpha-value>)",
          300: "rgb(var(--brand-300) / <alpha-value>)",
          400: "rgb(var(--brand-400) / <alpha-value>)",
          500: "rgb(var(--brand-500) / <alpha-value>)",
          600: "rgb(var(--brand-600) / <alpha-value>)",
          700: "rgb(var(--brand-700) / <alpha-value>)",
          800: "rgb(var(--brand-800) / <alpha-value>)",
          900: "rgb(var(--brand-900) / <alpha-value>)",
          950: "rgb(var(--brand-950) / <alpha-value>)",
        },
      },
      boxShadow: {
        soft: "0 1px 2px rgb(0 0 0 / 0.04), 0 1px 8px rgb(0 0 0 / 0.04)",
        "soft-dark": "0 1px 2px rgb(0 0 0 / 0.3), 0 1px 12px rgb(0 0 0 / 0.4)",
      },
    },
  },
};
