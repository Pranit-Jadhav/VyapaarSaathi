/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./frontend/index.html", "./frontend/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eefbf8",
          100: "#d2f4ec",
          500: "#12a57f",
          600: "#0f8d6d",
          700: "#0d7359",
        },
        ink: {
          900: "#0f172a",
          700: "#334155",
          500: "#64748b",
        },
      },
      boxShadow: {
        panel: "0 10px 25px -12px rgba(15, 23, 42, 0.35)",
      },
    },
  },
  plugins: [],
};
