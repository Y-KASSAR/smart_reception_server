/** @type {import('tailwindcss').Config} */
export default {
  // Reduced surface — the design system lives in src/styles/global.css.
  // Tailwind here only provides utility classes (flex, grid, gap, w/h, …)
  // for one-off layouts that don't warrant a named class.
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  corePlugins: {
    preflight: true,
  },
  theme: {
    extend: {},
  },
  plugins: [],
};
