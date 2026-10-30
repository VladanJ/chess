import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

// Portal builds (`--mode crazygames` / `--mode poki`) swap in that portal's adapter for
// "@portal", load its SDK before the game, and write to dist-<portal>/.
const SDK_SCRIPTS: Record<string, string> = {
  crazygames: "https://sdk.crazygames.com/crazygames-sdk-v3.js",
  poki: "https://game-cdn.poki.com/scripts/v2/poki-sdk.js",
};

export default defineConfig(({ mode }) => {
  const portal = mode in SDK_SCRIPTS ? mode : null;
  const adapter = portal ? `./portals/${portal}/portal.ts` : "./src/portal.ts";
  return {
    // Relative base so the build runs from any sub-path (game portals, GitHub Pages).
    base: "./",
    resolve: { alias: { "@portal": fileURLToPath(new URL(adapter, import.meta.url)) } },
    build: { outDir: portal ? `dist-${portal}` : "dist" },
    plugins: portal
      ? [{
        name: "portal-sdk",
        transformIndexHtml: () => [{ tag: "script", attrs: { src: SDK_SCRIPTS[portal] }, injectTo: "head-prepend" as const }],
      }]
      : [],
    // inotify doesn't fire for /mnt/c under WSL, so poll for changes.
    server: { watch: { usePolling: true, interval: 300 } },
  };
});
