import type { Config } from "tailwindcss"

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: "#050807",
        teal: {
          300: "#7de3df",
          500: "#2bb5b0",
          700: "#135b59",
        },
        ember: "#b14233",
        stoneglass: "#c1ad8f",
      },
      boxShadow: {
        cathedral: "0 30px 80px rgba(0, 0, 0, 0.48)",
      },
    },
  },
  plugins: [],
} satisfies Config
