/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/templates/**/*.html", "./frontend/**/*.js"],
  theme: {
    extend: {
      colors: {
        ink: "#10130f",
        paper: "#f1f0e9",
        moss: "#445c42",
        acid: "#d9ff57",
        ember: "#ea6c4b"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Georgia", "ui-serif", "serif"]
      },
      boxShadow: {
        lift: "0 18px 60px rgba(16, 19, 15, 0.10)"
      }
    }
  },
  plugins: [require("@tailwindcss/forms")]
};

