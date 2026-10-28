import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Single-page React app (React 19 + Vite 6 + react-router-dom v7).
// One entry (index.html) with client-side routing:
//   /           landing / hero
//   /demo       split view (customer phone + operator)
//   /dashboard  operator "Mission Control"
//   /phone      customer phone
// base:"./" so built assets work behind the Cloud9/VFS proxy and under any path.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: [".vfs.cloud9.us-east-1.amazonaws.com", ".amazonaws.com"],
  },
  preview: { host: "0.0.0.0", port: 4173 },
});
