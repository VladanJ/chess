import { BOARD, Color, PIECE_VALUE } from "./constants";
import { Move, Policy } from "./ai";
import { Piece } from "./piece";
import { getLegalTargets } from "./rules";

// Mirrors brain.py: MLP 10 -> 24 -> 24 -> 1 with tanh, scoring candidate moves.
const MAX_DIST = 2 * (BOARD - 1);
const MAX_MATERIAL = 39.0;
const CENTER = (BOARD - 1) / 2;

interface Layer {
  w: number[][]; // [out][in]
  b: number[];
}

export interface BrainWeights {
  layers: Layer[];
}

function dense(layer: Layer, x: number[], activate: boolean): number[] {
  const out = new Array<number>(layer.b.length);
  for (let o = 0; o < layer.b.length; o++) {
    const row = layer.w[o];
    let s = layer.b[o];
    for (let i = 0; i < x.length; i++) s += row[i] * x[i];
    out[o] = activate ? Math.tanh(s) : s;
  }
  return out;
}

export class Brain {
  constructor(private readonly weights: BrainWeights) {}

  score(x: number[]): number {
    const { layers } = this.weights;
    let h = x;
    for (let i = 0; i < layers.length; i++) h = dense(layers[i], h, i < layers.length - 1);
    return h[0];
  }
}

export async function loadBrain(url: string): Promise<Brain | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = (await res.json()) as BrainWeights;
    if (!Array.isArray(data.layers) || data.layers.length === 0) return null;
    return new Brain(data);
  } catch {
    return null;
  }
}

export function gaussian(): number {
  return Math.sqrt(-2 * Math.log(1 - Math.random())) * Math.cos(2 * Math.PI * Math.random());
}

function material(pieces: Piece[], color: Color): number {
  let sum = 0;
  for (const p of pieces) if (p.alive && p.color === color) sum += PIECE_VALUE[p.name];
  return sum;
}

export class NNPolicy implements Policy {
  /** *sigma* > 0 adds gaussian noise to move scores (training exploration). */
  constructor(private readonly brain: Brain, private readonly sigma = 0) {}

  choose(idle: Piece[], pieces: Piece[], color: Color): Move | null {
    const enemies = pieces.filter((p) => p.alive && p.color !== color);
    if (enemies.length === 0) return null;
    const enemyKing = enemies.find((p) => p.name === "King") ?? null;

    const enemyTiles = new Map<number, Piece>();
    for (const e of enemies) enemyTiles.set(e.row * BOARD + e.col, e);
    for (const e of enemies) {
      const nt = e.nextTile;
      if (nt && !enemyTiles.has(nt[1] * BOARD + nt[0])) enemyTiles.set(nt[1] * BOARD + nt[0], e);
    }

    const enemyMat = enemies.reduce((s, p) => s + PIECE_VALUE[p.name], 0);
    const matBalance = (material(pieces, color) - enemyMat) / MAX_MATERIAL;
    const forward = color === "black" ? 1 : -1;

    let best: Move | null = null;
    let bestScore = -Infinity;
    for (const p of idle) {
      for (const t of getLegalTargets(p, pieces)) {
        const [tc, tr] = t;
        const enemy = enemyTiles.get(tr * BOARD + tc) ?? null;
        let newKd = 0;
        let deltaKd = 0;
        if (enemyKing) {
          const cur = Math.abs(p.col - enemyKing.col) + Math.abs(p.row - enemyKing.row);
          const nxt = Math.abs(tc - enemyKing.col) + Math.abs(tr - enemyKing.row);
          newKd = nxt / MAX_DIST;
          deltaKd = (cur - nxt) / MAX_DIST;
        }
        const features = [
          PIECE_VALUE[p.name] / 9.0,
          p.hp / p.maxHp,
          enemy ? 1.0 : 0.0,
          enemy ? PIECE_VALUE[enemy.name] / 9.0 : 0.0,
          enemy ? enemy.hp / enemy.maxHp : 0.0,
          newKd,
          deltaKd,
          (forward * (tr - p.row)) / (BOARD - 1),
          matBalance,
          1.0 - (Math.abs(tc - CENTER) + Math.abs(tr - CENTER)) / MAX_DIST,
        ];
        const s = this.brain.score(features) + (this.sigma > 0 ? this.sigma * gaussian() : 0);
        if (s > bestScore) {
          bestScore = s;
          best = [p, t];
        }
      }
    }
    return best;
  }
}
