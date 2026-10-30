/**
 * Renders the portal preview videos frame by frame from real AI-vs-AI gameplay:
 * cover -> opening -> cut to the midgame -> cut to the endgame where the Black King falls.
 *
 *   npx vite --mode record --port 5180          # dev server that saves POSTed frames
 *   open http://127.0.0.1:5180/tools/video/record.html?video=landscape   (then ?video=portrait)
 *   encode: see web/tools/video/encode.sh
 *
 * Time is simulated (fixed 30 fps step) and randomness is seeded, so every run produces
 * identical frames regardless of browser throttling. Scenes are cuts, never sped up.
 */
import { AIController } from "../../src/ai";
import { NNPolicy, loadBrain } from "../../src/brain";
import { BASE_PIECE_SPEED, BOARD, HP_MAP, SPEED_PRESETS, TILE } from "../../src/constants";
import { Piece, setPieceSpeed } from "../../src/piece";
import { drawBoard, drawDeaths, drawPiece, loadPieceImages } from "../../src/render";
import { createPieces, pawnsToPromote, processCombat } from "../../src/rules";

const FPS = 30;
const INTRO_S = 1.0;      // cover held still (CrazyGames: open on the static cover)
const FADE_S = 0.8;       // cover cross-fades into the opening
const OPENING_S = 4.5;
const MIDGAME_S = 5;
const ENDGAME_S = 5.5;    // up to the Black King's death...
const AFTER_S = 1.5;      // ...plus its death animation
const FLASH_S = 0.25;     // white flash marking each cut
const ZOOM = 0.04;        // slow push-in within each scene
const CANDIDATES = 60;    // games simulated to find a good one
const MAX_GAME_S = 900;

const SIZES = { landscape: [1920, 1080], portrait: [1080, 1620] } as const;
type VideoName = keyof typeof SIZES;

// --- Deterministic clock and randomness ---------------------------------------------

let clockMs = 0;
performance.now = () => clockMs;

function seedRandom(seed: number): void {
  let a = seed >>> 0;
  Math.random = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// --- Headless game ---------------------------------------------------------------------

interface Match {
  pieces: Piece[];
  ais: AIController[];
  over: boolean;
  blackLost: boolean;
}

function newMatch(seed: number, brain: NNPolicy | null): Match {
  seedRandom(seed);
  clockMs = 0;
  const interval = SPEED_PRESETS.fast;
  setPieceSpeed((BASE_PIECE_SPEED * SPEED_PRESETS.fast) / interval);
  Piece.attackCounter = 0;
  // White at full strength, Black weaker, so White usually wins; difficulty below 10 also
  // mixes in randomness, so different seeds play out differently.
  const ais = ([["white", 10], ["black", 6]] as const).map(([c, d]) => {
    const ai = new AIController(c, d, brain);
    ai.actionsPerSecond = 1 / interval;
    return ai;
  });
  return { pieces: createPieces(HP_MAP), ais, over: false, blackLost: false };
}

function step(m: Match, dt: number): void {
  clockMs += dt * 1000;
  if (m.over) return;
  for (const ai of m.ais) ai.update(dt, m.pieces);
  processCombat(m.pieces, dt);
  for (const p of m.pieces) p.update(dt, m.pieces);
  for (const p of pawnsToPromote(m.pieces)) p.promote("Queen", HP_MAP.Queen);
  const deadKing = m.pieces.find((p) => p.name === "King" && !p.alive);
  if (deadKing) {
    m.over = true;
    m.blackLost = deadKing.color === "black";
  }
}

/** Plays the match forward to *seconds* without drawing; pieces that died meanwhile won't replay their death. */
function fastForward(m: Match, seconds: number): void {
  for (let f = 0; f < Math.round(seconds * FPS); f++) step(m, 1 / FPS);
  for (const p of m.pieces) if (!p.alive) p.diedAt = clockMs - 60_000;
}

interface Plan {
  seed: number;
  midStart: number; // seconds into the game
  kingDeath: number;
}

/** Finds a game the Black King loses after a real fight, and its most action-packed midgame stretch. */
function plan(brain: NNPolicy | null): Plan {
  let best: (Plan & { score: number }) | null = null;
  for (let seed = 1; seed <= CANDIDATES; seed++) {
    const m = newMatch(seed, brain);
    const action: number[] = []; // pieces under attack, summed per second
    let f = 0;
    for (; f < MAX_GAME_S * FPS && !m.over; f++) {
      step(m, 1 / FPS);
      const sec = Math.floor(f / FPS);
      action[sec] = (action[sec] ?? 0) + m.pieces.filter((p) => p.beingAttacked).length;
    }
    const end = f / FPS;
    if (!m.blackLost || end < 60) continue;
    let midStart = 0;
    let midScore = -1;
    for (let s = Math.floor(end * 0.3); s + MIDGAME_S < end * 0.7; s++) {
      let sum = 0;
      for (let k = s; k < s + MIDGAME_S; k++) sum += action[k] ?? 0;
      if (sum > midScore) [midStart, midScore] = [s, sum];
    }
    const kills = m.pieces.filter((p) => !p.alive).length;
    const score = kills * 10 + midScore / FPS;
    if (!best || score > best.score) best = { seed, midStart, kingDeath: end, score };
  }
  if (!best) throw new Error("no candidate game ended with the Black King falling");
  return best;
}

// --- Rendering -------------------------------------------------------------------------

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(src));
    img.src = src;
  });
}

function backdrop(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d")!;
  const grad = g.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgb(18,19,26)");
  grad.addColorStop(1, "rgb(38,37,52)");
  g.fillStyle = grad;
  g.fillRect(0, 0, w, h);
  for (const [x, rgb] of [[0.18, "63,127,217"], [0.82, "217,67,63"]] as const) {
    const r = Math.max(w, h) * 0.55;
    const rad = g.createRadialGradient(w * x, h * 0.5, 0, w * x, h * 0.5, r);
    rad.addColorStop(0, `rgba(${rgb},0.35)`);
    rad.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = rad;
    g.fillRect(0, 0, w, h);
  }
  return c;
}

async function record(name: VideoName): Promise<void> {
  const status = document.getElementById("status")!;
  const [W, H] = SIZES[name];
  const out = document.getElementById("out") as HTMLCanvasElement;
  out.width = W;
  out.height = H;
  const ctx = out.getContext("2d")!;
  const board = document.createElement("canvas");
  const bctx = board.getContext("2d")!;

  const [images, intro, brain] = await Promise.all([
    loadPieceImages("war"), loadImage(`tools/video/intro-${W}x${H}.png`), loadBrain("brain.json"),
  ]);
  const policy = brain ? new NNPolicy(brain) : null;
  status.textContent = "choosing a game the Black King loses…";
  const { seed, midStart, kingDeath } = plan(policy);
  const bg = backdrop(W, H);
  const baseBoard = Math.round(name === "landscape" ? H * 0.92 : W * 0.94);

  const scenes = [
    { from: 0, len: OPENING_S },
    { from: midStart, len: MIDGAME_S },
    { from: kingDeath - ENDGAME_S, len: ENDGAME_S + AFTER_S },
  ];
  const frames = Math.round((INTRO_S + scenes.reduce((s, sc) => s + sc.len, 0)) * FPS);
  let f = 0;
  const emit = async () => {
    const blob = await new Promise<Blob>((r) => out.toBlob((b) => r(b!), "image/jpeg", 0.95));
    const res = await fetch(`/__frame?video=${name}&i=${f}`, { method: "POST", body: blob });
    if (!res.ok) throw new Error(`frame ${f}: ${res.status}`);
    f++;
    status.textContent = `${name}: frame ${f}/${frames} (seed ${seed}, mid ${midStart}s, black king falls ${kingDeath.toFixed(1)}s)`;
  };

  for (let i = 0; i < INTRO_S * FPS; i++) {
    ctx.drawImage(intro, 0, 0, W, H);
    await emit();
  }

  let match: Match | null = null;
  for (const [n, scene] of scenes.entries()) {
    match = newMatch(seed, policy);
    fastForward(match, scene.from);
    for (let i = 0; i < Math.round(scene.len * FPS); i++) {
      const t = i / FPS;
      step(match, 1 / FPS);
      ctx.drawImage(bg, 0, 0);
      // Draw the board at its on-screen size so the SVG pieces stay sharp.
      const size = Math.round(baseBoard * (1 + ZOOM * t / scene.len));
      board.width = board.height = size;
      bctx.setTransform(size / (TILE * BOARD), 0, 0, size / (TILE * BOARD), 0, 0);
      drawBoard(bctx);
      for (const p of match.pieces) drawPiece(bctx, p, images, clockMs);
      drawDeaths(bctx, match.pieces, images, clockMs);
      ctx.save();
      ctx.shadowColor = "rgba(0,0,0,0.6)";
      ctx.shadowBlur = 40;
      ctx.drawImage(board, Math.round((W - size) / 2), Math.round((H - size) / 2));
      ctx.restore();
      if (n === 0 && t < FADE_S) {
        ctx.globalAlpha = 1 - t / FADE_S;
        ctx.drawImage(intro, 0, 0, W, H);
      } else if (n > 0 && t < FLASH_S) {
        ctx.globalAlpha = 0.85 * (1 - t / FLASH_S);
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, W, H);
      }
      ctx.globalAlpha = 1;
      await emit();
    }
  }
  const kills = match!.pieces.filter((p) => !p.alive).length;
  status.textContent = `done: ${name}, seed ${seed}, scenes at 0/${midStart}/${(kingDeath - ENDGAME_S).toFixed(1)}s ` +
    `of a ${kingDeath.toFixed(1)}s game, ${kills} pieces fell, black king down: ${match!.blackLost}, ${f} frames`;
  (window as unknown as { recordDone: string }).recordDone = status.textContent;
}

const video = new URLSearchParams(location.search).get("video");
if (video === "landscape" || video === "portrait") {
  record(video).catch((e) => {
    document.getElementById("status")!.textContent = `error: ${e}`;
    (window as unknown as { recordDone: string }).recordDone = `error: ${e}`;
  });
} else {
  document.getElementById("status")!.textContent = "add ?video=landscape or ?video=portrait";
}
