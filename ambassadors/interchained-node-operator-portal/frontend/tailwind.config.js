/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        neon: {
          pink: "#ff2d95",
          blue: "#35d3ff",
          purple: "#8a63ff",
        },
        glass: {
          dark: "rgba(10, 12, 29, 0.85)",
          light: "rgba(81, 92, 140, 0.35)",
        }
      },
      fontFamily: {
        heading: ["Orbitron", "sans-serif"],
        body: ["Inter", "sans-serif"],
      },
      boxShadow: {
        neon: "0 0 20px rgba(53, 211, 255, 0.45)",
      },
    },
  },
  plugins: [],
};
