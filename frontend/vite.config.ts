import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api and /ws straight to the FastAPI server on :5000
// so the React app can be developed standalone without CORS pain.
// In production, FastAPI itself serves frontend/dist (see api/app.py).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:5000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
