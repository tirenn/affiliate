/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        threads: {
          dark: "#101010",
          card: "#181818",
          border: "#262626",
          accent: "#0095F6",
          text: "#F3F5F7",
          muted: "#777777",
        }
      }
    },
  },
  plugins: [],
}
