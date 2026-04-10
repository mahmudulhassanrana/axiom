import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        surface: {
          DEFAULT: "#0f1419",
          raised: "#151b23",
          overlay: "#1c2430",
        },
        border: {
          subtle: "#2d3748",
          DEFAULT: "#3d4f5f",
        },
        accent: {
          DEFAULT: "#6366f1",
          hover: "#818cf8",
          muted: "#312e81",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgb(99 102 241 / 0.2), 0 8px 40px -12px rgb(0 0 0 / 0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
