import { defineConfig } from "vite";

// Relative base so the build runs from any sub-path (game portals, GitHub Pages).
export default defineConfig({
  base: "./",
  // inotify doesn't fire for /mnt/c under WSL, so poll for changes.
  server: { watch: { usePolling: true, interval: 300 } },
});
