import { Color, PIECE_VALUE, Tile } from "./constants";
import { Piece } from "./piece";
import { getLegalTargets } from "./rules";

export type Move = [Piece, Tile];

export interface Policy {
  choose(idle: Piece[], pieces: Piece[], color: Color): Move | null;
}

const MAX_DIFFICULTY = 10;

function shuffle<T>(arr: T[]): void {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
}

function captureScore(e: Piece): number {
  return PIECE_VALUE[e.name] * 10.0 - e.hp / 50.0;
}

function tileKey(c: number, r: number): number {
  return r * 8 + c;
}

/** Real-time AI: spends an action budget that refills at actionsPerSecond.
 *  Each action issues one move (defend king > capture > advance). */
export class AIController {
  readonly color: Color;
  readonly policy: Policy | null;
  actionsPerSecond = 0;
  private budget = 0;
  private randomness = 0;

  constructor(color: Color, difficulty = 5, policy: Policy | null = null) {
    this.color = color;
    this.policy = policy;
    this.setDifficulty(difficulty);
  }

  setDifficulty(difficulty: number): void {
    const d = Math.max(0, Math.min(MAX_DIFFICULTY, Math.trunc(difficulty)));
    this.actionsPerSecond = d;
    this.randomness = 1.0 - d / MAX_DIFFICULTY;
  }

  update(dt: number, pieces: Piece[]): void {
    if (this.actionsPerSecond <= 0) return;
    this.budget += this.actionsPerSecond * dt;
    // Never bank more than one pending action; >= 1 so slow cadences still act.
    this.budget = Math.min(this.budget, Math.max(this.actionsPerSecond, 1.0));
    while (this.budget >= 1.0) {
      if (!this.act(pieces)) {
        this.budget = Math.min(this.budget, 1.0);
        break;
      }
      this.budget -= 1.0;
    }
  }

  private defendKing(idle: Piece[], pieces: Piece[], enemies: Piece[]): Move | null {
    const king = pieces.find((p) => p.alive && p.color === this.color && p.name === "King");
    if (!king || king.moving) return null;

    const reaches = (p: Piece, c: number, r: number) =>
      getLegalTargets(p, pieces).some(([tc, tr]) => tc === c && tr === r);

    const attackers = enemies.filter((e) => reaches(e, king.col, king.row));
    if (attackers.length === 0) return null;

    const attackerAt = new Map<number, Piece>();
    for (const e of attackers) attackerAt.set(tileKey(e.col, e.row), e);

    // 1) Capture an attacker with a non-king piece.
    let best: { score: number; move: Move } | null = null;
    let kingCapture: Move | null = null;
    for (const p of idle) {
      if (p.moving) continue;
      for (const t of getLegalTargets(p, pieces)) {
        const e = attackerAt.get(tileKey(t[0], t[1]));
        if (!e) continue;
        if (p === king) {
          kingCapture = [king, t];
          continue;
        }
        const score = captureScore(e);
        if (best === null || score > best.score) best = { score, move: [p, t] };
      }
    }
    if (best !== null) return best.move;

    // 2) Flee to a tile no enemy can reach, farthest from the nearest attacker.
    const enemyReach = new Set<number>();
    for (const e of enemies) {
      for (const [tc, tr] of getLegalTargets(e, pieces)) enemyReach.add(tileKey(tc, tr));
    }
    const safe = getLegalTargets(king, pieces).filter(([tc, tr]) => !enemyReach.has(tileKey(tc, tr)));
    if (safe.length > 0) {
      const nearest = (t: Tile) =>
        Math.min(...attackers.map((e) => Math.abs(t[0] - e.col) + Math.abs(t[1] - e.row)));
      safe.sort((a, b) => nearest(b) - nearest(a));
      return [king, safe[0]];
    }

    // 3) Last resort: the king captures an adjacent attacker.
    return kingCapture;
  }

  private act(pieces: Piece[]): boolean {
    const enemies = pieces.filter((p) => p.alive && p.color !== this.color);
    if (enemies.length === 0) return false;
    const idle = pieces.filter((p) => p.alive && p.color === this.color && !p.moving);
    if (idle.length === 0) return false;

    // Below max difficulty, some moves fall back to the weaker heuristic so the brain isn't always at full strength.
    if (this.policy !== null && Math.random() >= this.randomness) {
      const choice = this.policy.choose(idle, pieces, this.color);
      if (choice === null) return false;
      choice[0].startMove(choice[1][0], choice[1][1]);
      return true;
    }

    const enemyKing = enemies.find((p) => p.name === "King") ?? null;

    // King safety first, at every difficulty.
    const defense = this.defendKing(idle, pieces, enemies);
    if (defense !== null) {
      defense[0].startMove(defense[1][0], defense[1][1]);
      return true;
    }

    // Enemy-occupied tiles (current + mid-slide next tile).
    const enemyTiles = new Map<number, Piece>();
    for (const e of enemies) enemyTiles.set(tileKey(e.col, e.row), e);
    for (const e of enemies) {
      const nt = e.nextTile;
      if (nt && !enemyTiles.has(tileKey(nt[0], nt[1]))) enemyTiles.set(tileKey(nt[0], nt[1]), e);
    }

    shuffle(idle);

    let bestCapture: { score: number; move: Move } | null = null;
    const advancePlans: { dist: number; move: Move }[] = [];

    for (const p of idle) {
      const targets = getLegalTargets(p, pieces);
      if (targets.length === 0) continue;

      let pieceCapture: Tile | null = null;
      let pieceScore = -1.0;
      for (const t of targets) {
        const e = enemyTiles.get(tileKey(t[0], t[1]));
        if (!e) continue;
        const score = captureScore(e);
        if (score > pieceScore) {
          pieceScore = score;
          pieceCapture = t;
        }
      }
      if (pieceCapture !== null) {
        if (bestCapture === null || pieceScore > bestCapture.score) {
          bestCapture = { score: pieceScore, move: [p, pieceCapture] };
        }
        continue;
      }

      // No capture — advance toward the enemy king (or nearest enemy).
      const dist = (c: number, r: number, q: Piece) => Math.abs(c - q.col) + Math.abs(r - q.row);
      const goal = enemyKing ?? enemies.reduce((a, b) => (dist(p.col, p.row, b) < dist(p.col, p.row, a) ? b : a));
      let bestMove: Tile | null = null;
      let bestDist = Infinity;
      for (const t of targets) {
        const d = dist(t[0], t[1], goal);
        if (d < bestDist) {
          bestDist = d;
          bestMove = t;
        }
      }
      if (bestMove !== null && bestDist < dist(p.col, p.row, goal)) {
        advancePlans.push({ dist: bestDist, move: [p, bestMove] });
      }
    }

    if (bestCapture !== null) {
      const [p, t] = bestCapture.move;
      p.startMove(t[0], t[1]);
      return true;
    }
    if (advancePlans.length === 0) return false;

    let plan;
    if (Math.random() < this.randomness) {
      plan = advancePlans[Math.floor(Math.random() * advancePlans.length)];
    } else {
      plan = advancePlans.reduce((a, b) => (b.dist < a.dist ? b : a));
    }
    const [p, t] = plan.move;
    p.startMove(t[0], t[1]);
    return true;
  }
}
