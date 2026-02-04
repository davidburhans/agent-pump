/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Map Textual semantic variables conceptually
        primary: "#3b82f6", // blue-500
        secondary: "#64748b", // gray-500
        success: "#22c55e", // green-500
        error: "#ef4444", // red-500
        warning: "#eab308", // yellow-500
        surface: "#1f2937", // gray-800
        background: "#030712", // gray-950
      }
    },
  },
  plugins: [],
}
