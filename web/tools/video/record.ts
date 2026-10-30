/**
 * Renders the portal preview videos frame by frame from real AI-vs-AI gameplay.
 *
 *   npx vite --mode record --port 5180          # dev server that saves POSTed frames
 *   open http://127.0.0.1:5180/tools/video/record.html?video=landscape   (then ?video=portrait)
 *   encode: see web/tools/video/encode.sh
 *
 * Time is simulated (fixed 30 fps step) and randomness is seeded, so every run produces
 * identical frames regardless of browser throttling.
 */
import { AIController } from "../../src/ai";
import { NNPolicy, loadBrain } from "../../src/brain";
import { BASE_PIECE_SPEED, BOARD, PieceName, SPEED_PRESETS, TILE } from "../../src/constants";
import { fromFen } from "../../src/fen";
import { Piece, setPieceSpeed } from "../../src/piece";
import { drawBoard, drawDeaths, drawPiece, loadPieceImages } from "../../src/render";
import { pawnsToPromote, processCombat } from "../../src/rules";

const FPS = 30;
const INTRO_S = 1.0;      // cover held still (CrazyGames: open on the static cover)
const FADE_S = 0.8;       // cover cross-fades into the battle
const TOTAL_S = 19;       // CrazyGames trims anything past 20 s
const ZOOM = 0.06;        // slow push-in over the clip
const CANDIDATES = 40;    // games simulated to find the most eventful one

// Pawn lines already locked together so the fighting starts at once; lower HP (a normal
// player option) so pieces fall within the clip.
const START = "rnbqkbnr/8/8/pppppppp/PPPPPPPP/8/8/RNBQKBNR";
const HP: Record<PieceName, number> = { Pawn: 40, Knight: 80, Bishop: 80, Rook: 120, Queen: 200, King: 160 };

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
}

function newMatch(seed: number, brain: NNPolicy | null): Match {
  seedRandom(seed);
  clockMs = 0;
  const interval = SPEED_PRESETS.fast;
  setPieceSpeed((BASE_PIECE_SPEED * SPEED_PRESETS.fast) / interval);
  Piece.attackCounter = 0;
  const pieces = fromFen(START)!.map((s) => {
    const p = new Piece(s.color, s.name, s.col, s.row, HP[s.name]);
    if (s.name === "Pawn") p.hasMoved = s.row !== (s.color === "white" ? BOARD - 2 : 1);
    return p;
  });
  // Difficulty below 10 mixes in the heuristic, so different seeds play out differently.
  const ais = (["white", "black"] as const).map((c) => {
    const ai = new AIController(c, 7, brain);
    ai.actionsPerSecond = 1 / interval;
    return ai;
  });
  return { pieces, ais, over: false };
}

function step(m: Match, dt: number): void {
  clockMs += dt * 1000;
  if (m.over) return;
  for (const ai of m.ais) ai.update(dt, m.pieces);
  processCombat(m.pieces, dt);
  for (const p of m.pieces) p.update(dt, m.pieces);
  for (const p of pawnsToPromote(m.pieces)) p.promote("Queen", HP.Queen);
  if (m.pieces.some((p) => p.name === "King" && !p.alive)) m.over = true;
}

/** Seed whose clip has the most kills, preferring one that ends with a King falling late. */
function pickSeed(brain: NNPolicy | null): number {
  const playS = TOTAL_S - INTRO_S;
  let best = { seed: 1, score: -1 };
  for (let seed = 1; seed <= CANDIDATES; seed++) {
    const m = newMatch(seed, brain);
    let kingAt = -1;
    for (let f = 0; f < playS * FPS && !m.over; f++) {
      step(m, 1 / FPS);
      if (m.over) kingAt = f / FPS;
    }
    const kills = m.pieces.filter((p) => !p.alive).length;
    const finale = kingAt > playS - 5 ? 6 : kingAt > 0 ? -4 : 0; // a too-early ending cuts the action
    if (kills + finale > best.score) best = { seed, score: kills + finale };
  }
  return best.seed;
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
  status.textContent = "choosing the most eventful game…";
  const seed = pickSeed(policy);
  const match = newMatch(seed, policy);
  const bg = backdrop(W, H);
  const baseBoard = Math.round(name === "landscape" ? H * 0.92 : W * 0.94);

  const frames = TOTAL_S * FPS;
  for (let f = 0; f < frames; f++) {
    const t = f / FPS;
    if (t >= INTRO_S) step(match, 1 / FPS);

    if (t < INTRO_S) {
      ctx.drawImage(intro, 0, 0, W, H);
    } else {
      ctx.drawImage(bg, 0, 0);
      // Draw the board at its on-screen size so the SVG pieces stay sharp.
      const size = Math.round(baseBoard * (1 + ZOOM * (t - INTRO_S) / (TOTAL_S - INTRO_S)));
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
      if (t < INTRO_S + FADE_S) {
        ctx.globalAlpha = 1 - (t - INTRO_S) / FADE_S;
        ctx.drawImage(intro, 0, 0, W, H);
        ctx.globalAlpha = 1;
      }
    }

    const blob = await new Promise<Blob>((r) => out.toBlob((b) => r(b!), "image/jpeg", 0.95));
    const res = await fetch(`/__frame?video=${name}&i=${f}`, { method: "POST", body: blob });
    if (!res.ok) throw new Error(`frame ${f}: ${res.status}`);
    status.textContent = `${name}: frame ${f + 1}/${frames} (seed ${seed})`;
  }
  const kills = match.pieces.filter((p) => !p.alive).length;
  status.textContent = `done: ${name}, seed ${seed}, ${kills} pieces fell, king down: ${match.over}`;
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
