import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: { bg: "#0b0e14", panel: "#141925", border: "#222b3d" },
        accent: { DEFAULT: "#3b82f6", up: "#16a34a", down: "#dc2626", warn: "#d97706" },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
