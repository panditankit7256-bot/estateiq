/** Colours are CSS variables so light/dark themes switch without rebuilding. */
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: { canvas: v("canvas"), surface: v("surface"), raised: v("raised"), line: v("line"), ink: v("ink"), muted: v("muted"),
                brand: v("brand"), brandfg: v("brandfg"), rail: v("rail"), railfg: v("railfg"),
                ok: v("ok"), warn: v("warn"), bad: v("bad"), info: v("info") },
      fontFamily: { sans: ['"IBM Plex Sans"', '"IBM Plex Sans Devanagari"', "system-ui", "sans-serif"] },
      borderRadius: { card: "10px" },
    },
  },
  plugins: [],
};
