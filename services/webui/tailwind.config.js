export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "dark-grey": "#1a1a2e",
        "navy-blue": "#16213e",
        gold: "#d4af37",
        gray: {
          50: "#f9fafb",
          100: "#f3f4f6",
          200: "#e5e7eb",
          300: "#d1d5db",
          400: "#9ca3af",
          500: "#6b7280",
          600: "#4b5563",
          700: "#374151",
          800: "#1f2937",
          900: "#111827",
        },
      },
      backgroundColor: {
        primary: "#1a1a2e",
        secondary: "#16213e",
        accent: "#d4af37",
      },
      textColor: {
        primary: "#ffffff",
        secondary: "#d4af37",
      },
      borderColor: {
        primary: "#16213e",
        accent: "#d4af37",
      },
    },
  },
  plugins: [],
};
