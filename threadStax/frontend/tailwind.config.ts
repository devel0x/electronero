import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        midnight: "#05070f",
        accent: "#6ee7ff",
        card: "#0b1220",
      },
      boxShadow: {
        glow: "0 0 30px rgba(110,231,255,0.2)",
      },
    },
  },
  plugins: [],
};

export default config;
