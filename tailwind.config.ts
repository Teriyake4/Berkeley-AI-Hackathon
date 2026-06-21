import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        // ── Night-dispatch console surfaces ──────────────────────────
        ink: {
          950: "#06090f",
          900: "#0a0e16",
          850: "#0d1320",
          800: "#111a2b",
          700: "#172236",
          600: "#1f2c43",
          500: "#2b3a56",
        },
        // ── Emergency signal (brand accent) ──────────────────────────
        signal: {
          50: "#fff1ef",
          100: "#ffe0db",
          200: "#ffc0b6",
          300: "#ff9485",
          400: "#ff6452",
          500: "#ff4536",
          600: "#ed2c1e",
          700: "#c61f14",
          800: "#a01d15",
          900: "#841e18",
        },
        // ── Live AI / data (electric cyan) ───────────────────────────
        clinical: {
          50: "#ecfdff",
          100: "#cff8fe",
          200: "#a5f0fc",
          300: "#67e3f9",
          400: "#22d4ec",
          500: "#08b6d4",
          600: "#0992b3",
          700: "#107491",
          800: "#175e76",
          900: "#164e63",
          950: "#083344",
        },
        // ── Vitals (mint = connected / ok) ───────────────────────────
        vitals: {
          400: "#3ddc97",
          500: "#22c98a",
        },
        // ambulance kept as an alias of signal for any lingering refs
        ambulance: {
          50: "#fff1ef",
          100: "#ffe0db",
          200: "#ffc0b6",
          300: "#ff9485",
          400: "#ff6452",
          500: "#ff4536",
          600: "#ed2c1e",
          700: "#c61f14",
          800: "#a01d15",
          900: "#841e18",
          950: "#450a0a",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,69,54,0.4), 0 0 24px -4px rgba(255,69,54,0.55)",
        "glow-cyan": "0 0 0 1px rgba(34,212,236,0.35), 0 0 24px -6px rgba(34,212,236,0.5)",
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 40px -24px rgba(0,0,0,0.7)",
      },
    },
  },
  plugins: [],
};

export default config;
