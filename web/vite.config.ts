import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig, Plugin } from "vite";

// Portal builds (`--mode crazygames` / `--mode poki`) swap in that portal's adapter for
// "@portal", load its SDK before the game, and write to dist-<portal>/.
const SDK_SCRIPTS: Record<string, string> = {
  crazygames: "https://sdk.crazygames.com/crazygames-sdk-v3.js",
  poki: "https://game-cdn.poki.com/scripts/v2/poki-sdk.js",
};

/** `--mode record` only: saves frames POSTed by tools/video/record.ts to tools/video/frames/. */
function frameSaver(): Plugin {
  const root = fileURLToPath(new URL("./tools/video/frames/", import.meta.url));
  return {
    name: "frame-saver",
    configureServer(server) {
      server.middlewares.use("/__frame", (req, res) => {
        const q = new URL(req.url ?? "", "http://x").searchParams;
        const video = q.get("video") ?? "";
        const i = q.get("i") ?? "";
        if (req.method !== "POST" || !["landscape", "portrait"].includes(video) || !/^\d{1,5}$/.test(i)) {
          res.statusCode = 400;
          res.end();
          return;
        }
        const chunks: Buffer[] = [];
        req.on("data", (c: Buffer) => chunks.push(c));
        req.on("end", () => {
          const dir = `${root}${video}/`;
          if (i === "0") rmSync(dir, { recursive: true, force: true });
          mkdirSync(dir, { recursive: true });
          writeFileSync(`${dir}frame-${i.padStart(5, "0")}.jpg`, Buffer.concat(chunks));
          res.end("ok");
        });
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const portal = mode in SDK_SCRIPTS ? mode : null;
  const adapter = portal ? `./portals/${portal}/portal.ts` : "./src/portal.ts";
  const plugins: Plugin[] = [];
  if (portal) {
    plugins.push({
      name: "portal-sdk",
      transformIndexHtml: () => [{ tag: "script", attrs: { src: SDK_SCRIPTS[portal] }, injectTo: "head-prepend" as const }],
    });
  }
  if (mode === "record") plugins.push(frameSaver());
  return {
    // Relative base so the build runs from any sub-path (game portals, GitHub Pages).
    base: "./",
    resolve: { alias: { "@portal": fileURLToPath(new URL(adapter, import.meta.url)) } },
    build: { outDir: portal ? `dist-${portal}` : "dist" },
    plugins,
    // inotify doesn't fire for /mnt/c under WSL, so poll for changes.
    server: { watch: { usePolling: true, interval: 300 } },
  };
});
