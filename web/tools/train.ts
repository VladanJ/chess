/**
 * Evolutionary self-play trainer for the web AI (port of legacy/train.py).
 *
 * Plays headless games with the real web rules (src/), so the brain learns the
 * game players actually play. Writes the champion to public/brain.json.
 *
 *   npm run train -- --games 3000            # continue from the current brain
 *   npm run train -- --games 3000 --fresh    # start from random brains
 */
import { copyFileSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { cpus } from "node:os";
import { fileURLToPath } from "node:url";
import { Worker, isMainThread, parentPort } from "node:worker_threads";
import { AIController } from "../src/ai";
import { Brain, BrainWeights, NNPolicy, gaussian } from "../src/brain";
import { BASE_PIECE_SPEED, Color, HP_MAP, PIECE_VALUE, SPEED_PRESETS } from "../src/constants";
import { Piece, setPieceSpeed } from "../src/piece";
import { createPieces, pawnsToPromote, processCombat } from "../src/rules";

const WEB = fileURLToPath(new URL("..", import.meta.url));
const OUT = `${WEB}public/brain.json`;
const BACKUP = `${WEB}tools/brain.backup.json`;

// Train at the default game speed with the AI on the player's cadence.
const MOVE_INTERVAL = SPEED_PRESETS.medium;
const DT = 0.25;
const MAX_TIME = 900; // simulated seconds before remaining material decides

// --- Headless game -----------------------------------------------------------

function material(pieces: Piece[], color: Color): number {
  return pieces.reduce((s, p) => s + (p.alive && p.color === color ? PIECE_VALUE[p.name] : 0), 0);
}

const kingAlive = (pieces: Piece[], color: Color) =>
  pieces.some((p) => p.alive && p.color === color && p.name === "King");

/** +1 white wins, -1 black wins, 0 draw. */
function playGame(white: AIController, black: AIController): number {
  setPieceSpeed((BASE_PIECE_SPEED * SPEED_PRESETS.fast) / MOVE_INTERVAL);
  Piece.attackCounter = 0;
  const pieces = createPieces(HP_MAP);
  white.actionsPerSecond = black.actionsPerSecond = 1 / MOVE_INTERVAL;
  for (let t = 0; t < MAX_TIME; t += DT) {
    white.update(DT, pieces);
    black.update(DT, pieces);
    processCombat(pieces, DT);
    for (const p of pieces) p.update(DT, pieces);
    for (const p of pawnsToPromote(pieces)) p.promote("Queen", HP_MAP.Queen);
    const wk = kingAlive(pieces, "white");
    const bk = kingAlive(pieces, "black");
    if (!wk || !bk) return wk === bk ? 0 : wk ? 1 : -1;
  }
  return Math.sign(material(pieces, "white") - material(pieces, "black"));
}

interface Task {
  a: BrainWeights;
  b: BrainWeights | null; // null = built-in heuristic AI at max difficulty
  aWhite: boolean;
  sigma: number;
}

/** Result from brain a's point of view: +1 win, -1 loss, 0 draw. */
function runTask(t: Task): number {
  const aColor: Color = t.aWhite ? "white" : "black";
  const bColor: Color = t.aWhite ? "black" : "white";
  const a = new AIController(aColor, 10, new NNPolicy(new Brain(t.a), t.sigma));
  const b = new AIController(bColor, 10, t.b ? new NNPolicy(new Brain(t.b), t.sigma) : null);
  const r = t.aWhite ? playGame(a, b) : playGame(b, a);
  return t.aWhite ? r : -r;
}

if (!isMainThread) {
  parentPort!.on("message", (t: Task) => parentPort!.postMessage(runTask(t)));
}

// --- Worker pool -------------------------------------------------------------

class Pool {
  private readonly workers: Worker[];

  constructor(size: number) {
    this.workers = Array.from({ length: size }, () => new Worker(fileURLToPath(import.meta.url)));
  }

  run(tasks: Task[]): Promise<number[]> {
    const results = new Array<number>(tasks.length);
    let next = 0;
    return new Promise((resolve, reject) => {
      let done = 0;
      const onError = (e: Error) => { cleanup(); reject(e); };
      const cleanup = () => this.workers.forEach((w) => w.off("error", onError));
      const finish = () => { cleanup(); resolve(results); };
      this.workers.forEach((w) => w.on("error", onError));
      if (tasks.length === 0) finish();
      const feed = (w: Worker) => {
        if (next >= tasks.length) return;
        const i = next++;
        w.once("message", (r: number) => {
          results[i] = r;
          if (++done === tasks.length) finish();
          else feed(w);
        });
        w.postMessage(tasks[i]);
      };
      this.workers.forEach(feed);
    });
  }

  close(): Promise<number[]> {
    return Promise.all(this.workers.map((w) => w.terminate()));
  }
}

// --- Brains ------------------------------------------------------------------

function randomLayer(nIn: number, nOut: number): BrainWeights["layers"][number] {
  const bound = 1 / Math.sqrt(nIn); // PyTorch nn.Linear default init
  const u = () => (Math.random() * 2 - 1) * bound;
  return { w: Array.from({ length: nOut }, () => Array.from({ length: nIn }, u)), b: Array.from({ length: nOut }, u) };
}

const randomBrain = (): BrainWeights => ({ layers: [randomLayer(10, 24), randomLayer(24, 24), randomLayer(24, 1)] });

const mutate = (w: BrainWeights, sigma: number): BrainWeights => ({
  layers: w.layers.map((l) => ({
    w: l.w.map((row) => row.map((v) => v + gaussian() * sigma)),
    b: l.b.map((v) => v + gaussian() * sigma),
  })),
});

const score = (results: number[]) =>
  results.reduce((s, r) => s + (r > 0 ? 1 : r === 0 ? 0.5 : 0), 0) / results.length;

// --- Training loop -------------------------------------------------------------

interface Options {
  games: number;
  pop: number;
  sigma: number;
  explore: number;
  evalGames: number;
  confirmGames: number;
  h2hGames: number;
  reportGames: number;
  fresh: boolean;
  workers: number;
}

function parseArgs(): Options {
  const o: Options = {
    games: 2000, pop: 8, sigma: 0.15, explore: 0.05, evalGames: 16, confirmGames: 64, h2hGames: 8, reportGames: 100,
    fresh: false, workers: cpus().length,
  };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i].replace(/^--/, "").replace(/-(\w)/g, (_, c: string) => c.toUpperCase()) as keyof Options;
    if (key === "fresh") o.fresh = true;
    else if (key in o) (o[key] as number) = Number(argv[++i]);
    else throw new Error(`Unknown option ${argv[i]}`);
  }
  return o;
}

async function train(): Promise<void> {
  const o = parseArgs();
  const pool = new Pool(o.workers);
  const vsHeuristic = async (w: BrainWeights, n: number) =>
    score(await pool.run(Array.from({ length: n }, (_, i) => ({ a: w, b: null, aWhite: i % 2 === 0, sigma: 0 }))));
  const headToHead = async (a: BrainWeights, b: BrainWeights, n: number) =>
    score(await pool.run(Array.from({ length: n }, (_, i) => ({ a, b, aWhite: i % 2 === 0, sigma: 0 }))));

  const previous: BrainWeights | null = existsSync(OUT) ? JSON.parse(readFileSync(OUT, "utf8")) : null;
  if (previous) copyFileSync(OUT, BACKUP);
  const seed = !o.fresh && previous ? previous : null;
  let population = seed
    ? [seed, ...Array.from({ length: o.pop - 1 }, () => mutate(seed, o.sigma))]
    : Array.from({ length: o.pop }, randomBrain);
  let champion = population[0];

  const start = Date.now();
  const secs = () => ((Date.now() - start) / 1000).toFixed(0);
  console.log(`Training ${o.games} games, population ${o.pop}, ${o.workers} workers, ` +
    `${seed ? "continuing from public/brain.json" : "fresh random brains"}`);

  let championScore = await vsHeuristic(champion, o.confirmGames);
  let games = o.confirmGames;
  console.log(`Champion baseline vs heuristic: ${(championScore * 100).toFixed(0)}%`);

  for (let gen = 1; games < o.games; gen++) {
    // Each brain duels a random other brain.
    const pairs = population.map((_, i) => {
      let j = Math.floor(Math.random() * (o.pop - 1));
      if (j >= i) j++;
      return [i, j] as const;
    });
    const outcomes = await pool.run(pairs.map(([i, j]) => ({
      a: population[i], b: population[j], aWhite: Math.random() < 0.5, sigma: o.explore,
    })));
    games += pairs.length;
    const scores = new Array<number>(o.pop).fill(0);
    pairs.forEach(([i, j], k) => { scores[i] += outcomes[k]; scores[j] -= outcomes[k]; });

    // Champion gate: at least as good vs the heuristic AND beats the champion head-to-head.
    const ranked = scores.map((s, i) => i).sort((x, y) => scores[y] - scores[x]);
    const challenger = population[ranked[0]];
    let tag = "";
    if (challenger !== champion) {
      let chScore = await vsHeuristic(challenger, o.evalGames);
      games += o.evalGames;
      if (chScore >= championScore) {
        // A quick pass is often luck: confirm on a bigger sample before comparing.
        const extra = o.confirmGames - o.evalGames;
        chScore = (chScore * o.evalGames + (await vsHeuristic(challenger, extra)) * extra) / o.confirmGames;
        games += extra;
      }
      if (chScore >= championScore) {
        const h2h = await headToHead(challenger, champion, o.h2hGames);
        games += o.h2hGames;
        if (h2h > 0.5) {
          champion = challenger;
          championScore = chScore;
          writeFileSync(OUT, JSON.stringify(champion));
          tag = `  <- new champion (heuristic ${(chScore * 100).toFixed(0)}%, h2h ${(h2h * 100).toFixed(0)}%, saved)`;
        }
      }
    }

    // Keep the top half, refill with mutated children.
    const survivors = ranked.slice(0, Math.max(1, o.pop >> 1)).map((i) => population[i]);
    population = [...survivors];
    while (population.length < o.pop) {
      population.push(mutate(survivors[Math.floor(Math.random() * survivors.length)], o.sigma));
    }

    if (gen % 5 === 0 || tag) {
      console.log(`gen ${String(gen).padStart(4)} | games ${String(games).padStart(5)}/${o.games} ` +
        `| champ vs heuristic ${(championScore * 100).toFixed(0)}% | ${secs()}s${tag}`);
    }
  }

  console.log(`\nFinal report (${o.reportGames} games each):`);
  console.log(`  champion vs heuristic AI: ${(await vsHeuristic(champion, o.reportGames) * 100).toFixed(0)}%`);
  if (previous && champion !== previous) {
    console.log(`  champion vs previous brain: ${(await headToHead(champion, previous, o.reportGames) * 100).toFixed(0)}%`);
  }
  if (!existsSync(OUT) || champion === seed) console.log("  (no improvement found; public/brain.json unchanged)");
  console.log(`Done in ${secs()}s. Previous brain backed up to tools/brain.backup.json`);
  await pool.close();
}

if (isMainThread) {
  train().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
