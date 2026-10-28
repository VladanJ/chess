import {
  BASE_PIECE_SPEED, Color, HP_MAP, PieceName, STOP_BTN_RADIUS, TILE, Tile, sameTile,
} from "./constants";

// Active movement speed (tiles/sec); set from the chosen game speed.
let pieceSpeed = BASE_PIECE_SPEED;

export function setPieceSpeed(speed: number): void {
  pieceSpeed = speed;
}

type KnightPhase = "crossfade" | "waiting" | null;

export class Piece {
  // Monotonic counter to order concurrent attackers.
  static attackCounter = 0;

  readonly color: Color;
  readonly name: PieceName;
  col: number;
  row: number;
  hp: number;
  readonly maxHp: number;
  alive = true;

  moving = false;
  targetCol: number;
  targetRow: number;
  pixelX: number;
  pixelY: number;
  originCol: number;
  originRow: number;

  // Knight crossfade animation; alphas are 0..255 like the Python version.
  knightPhase: KnightPhase = null;
  knightAlpha = 255;
  knightDestAlpha = 0;
  knightTimer = 0;
  knightDuration = 0;

  path: Tile[] = [];
  pathIndex = 0;
  waiting = false;
  attackTarget: Piece | null = null;
  attackOrder: number | null = null;

  beingAttacked = false;
  hasMoved = false;
  // performance.now() when first drawn dead; drives the death animation.
  diedAt: number | null = null;

  constructor(color: Color, name: PieceName, col: number, row: number, hp = HP_MAP[name]) {
    this.color = color;
    this.name = name;
    this.col = col;
    this.row = row;
    this.hp = hp;
    this.maxHp = hp;
    this.targetCol = col;
    this.targetRow = row;
    this.pixelX = col * TILE;
    this.pixelY = row * TILE;
    this.originCol = col;
    this.originRow = row;
  }

  get nextTile(): Tile | null {
    if (this.moving && this.path.length > 0 && this.pathIndex < this.path.length) {
      return this.path[this.pathIndex];
    }
    return null;
  }

  get currentTile(): Tile {
    return [this.col, this.row];
  }

  /** True if settled on a reached tile: may deal damage and is not vulnerable
   *  at the tile it only heads toward. A knight is "not reached" only while
   *  genuinely fading across to an empty target. */
  hasReachedTile(): boolean {
    if (this.name === "Knight") {
      if (this.knightPhase === "crossfade") return this.knightDestAlpha === 0;
      return true;
    }
    return this.pixelX === this.col * TILE && this.pixelY === this.row * TILE;
  }

  startMove(tcol: number, trow: number): void {
    this.originCol = this.col;
    this.originRow = this.row;
    this.targetCol = tcol;
    this.targetRow = trow;
    this.path = this.computePath();
    this.pathIndex = 0;
    this.waiting = false;
    this.moving = true;

    if (this.name === "Knight") {
      this.knightDuration = 1.0 / pieceSpeed;
      this.knightPhase = "crossfade";
      this.knightTimer = 0;
      this.knightAlpha = 255;
      this.knightDestAlpha = 0;
    }
  }

  private computePath(): Tile[] {
    if (this.name === "Knight") return [[this.targetCol, this.targetRow]];
    const path: Tile[] = [];
    const tc = this.targetCol;
    const tr = this.targetRow;
    const dc = Math.sign(tc - this.col);
    const dr = Math.sign(tr - this.row);
    let cc = this.col + dc;
    let rr = this.row + dr;
    for (;;) {
      path.push([cc, rr]);
      if (cc === tc && rr === tr) break;
      cc += dc;
      rr += dr;
    }
    return path;
  }

  update(dt: number, pieces: Piece[]): void {
    if (!this.alive || !this.moving) return;
    if (this.name === "Knight") this.updateKnight(dt, pieces);
    else this.updateSlide(dt, pieces);
  }

  private snapToTile(): void {
    this.pixelX = this.col * TILE;
    this.pixelY = this.row * TILE;
  }

  private cancelMove(): void {
    this.moving = false;
    this.waiting = false;
    this.path = [];
    this.attackTarget = null;
  }

  private updateSlide(dt: number, pieces: Piece[]): void {
    if (this.pathIndex >= this.path.length) {
      this.finishMove();
      return;
    }

    const [wc, wr] = this.path[this.pathIndex];
    const pawnForward = this.name === "Pawn" && wc === this.col;

    // Stop only if an enemy is physically on the target tile. Pawns moving
    // forward only stop for stationary enemies.
    const enemy = pawnForward
      ? this.getStationaryEnemy(pieces, wc, wr)
      : this.getEnemyBlocking(pieces, wc, wr);
    if (enemy !== null) {
      this.snapToTile();
      // Pawns can only attack diagonally, never forward.
      if (pawnForward) this.cancelMove();
      else this.beginAttack(enemy);
      return;
    }

    // No enemy on the tile — a friendly piece occupying or heading there blocks us.
    if (this.getBlocker(pieces, wc, wr) !== null) {
      this.snapToTile();
      this.cancelMove();
      return;
    }

    // Defender still on this tile — maintain attack until it fully leaves.
    if (this.waiting && this.attackTarget !== null && this.attackTarget.alive) {
      if (this.attackTarget.col === wc && this.attackTarget.row === wr) return;
    }

    // Pawn diagonal attack failed (defender survived and left).
    if (this.waiting && this.name === "Pawn" && wc !== this.col) {
      if (this.attackTarget !== null && this.attackTarget.alive) {
        this.snapToTile();
        this.cancelMove();
        return;
      }
    }

    // Head-on collision: a genuine mutual swap — stay and fight.
    if (!pawnForward) {
      for (const q of pieces) {
        if (q !== this && q.alive && q.color !== this.color && q.moving
            && sameTile(q.nextTile, this.col, this.row)
            && wc === q.col && wr === q.row) {
          this.snapToTile();
          this.beginAttack(q);
          return;
        }
      }
    }

    // Contested freed tile: only the earliest attacker may claim it.
    if (this.waiting && this.earlierAttackerExists(pieces, wc, wr)) {
      this.snapToTile();
      return;
    }

    // Tile is free — slide towards it.
    this.waiting = false;
    this.attackTarget = null;
    const tx = wc * TILE;
    const ty = wr * TILE;
    const dx = tx - this.pixelX;
    const dy = ty - this.pixelY;
    const dist = Math.hypot(dx, dy);
    const step = pieceSpeed * TILE * dt;

    if (dist <= step) {
      this.pixelX = tx;
      this.pixelY = ty;
      this.col = wc;
      this.row = wr;
      this.pathIndex += 1;
      if (this.pathIndex >= this.path.length) this.finishMove();
    } else {
      this.pixelX += (dx / dist) * step;
      this.pixelY += (dy / dist) * step;
    }
  }

  private resetKnightVisual(): void {
    this.knightPhase = null;
    this.knightAlpha = 255;
    this.knightDestAlpha = 0;
  }

  private knightSnapBack(): void {
    this.pixelX = this.originCol * TILE;
    this.pixelY = this.originRow * TILE;
    this.col = this.originCol;
    this.row = this.originRow;
    this.resetKnightVisual();
    this.moving = false;
    this.waiting = false;
    this.path = [];
  }

  private knightLand(): void {
    this.pixelX = this.targetCol * TILE;
    this.pixelY = this.targetRow * TILE;
    this.col = this.targetCol;
    this.row = this.targetRow;
    this.resetKnightVisual();
  }

  private updateKnight(dt: number, pieces: Piece[]): void {
    this.knightTimer += dt;
    const tc = this.targetCol;
    const tr = this.targetRow;

    if (this.knightPhase === "crossfade") {
      const t = Math.min(this.knightTimer / this.knightDuration, 1.0);
      if (this.getEnemyBlocking(pieces, tc, tr) !== null) {
        // Attacking an occupied tile — stay visible at origin, no fade.
        this.knightAlpha = 255;
        this.knightDestAlpha = 0;
      } else {
        this.knightAlpha = Math.trunc(255 * (1 - t));
        this.knightDestAlpha = Math.trunc(255 * t);
      }
      if (t >= 1.0) {
        const friendly = this.getBlocker(pieces, tc, tr);
        const enemy = this.getEnemyBlocking(pieces, tc, tr);
        if (friendly !== null) {
          this.knightSnapBack();
        } else if (enemy !== null) {
          this.knightPhase = "waiting";
          this.knightAlpha = 255;
          this.knightDestAlpha = 0;
          this.beginAttack(enemy);
        } else {
          this.knightLand();
          this.finishMove();
        }
      }
    } else if (this.knightPhase === "waiting") {
      const friendly = this.getBlocker(pieces, tc, tr);
      const enemy = this.getEnemyBlocking(pieces, tc, tr);
      if (friendly !== null) {
        this.knightSnapBack();
      } else if (enemy === null) {
        if (this.earlierAttackerExists(pieces, tc, tr)) return;
        this.knightLand();
        this.waiting = false;
        this.finishMove();
      }
    }
  }

  private finishMove(): void {
    const moved = this.col !== this.originCol || this.row !== this.originRow;
    this.moving = false;
    this.waiting = false;
    this.attackTarget = null;
    this.attackOrder = null;
    this.path = [];
    this.pathIndex = 0;
    if (moved) this.hasMoved = true;
  }

  private beginAttack(enemy: Piece): void {
    if (!this.waiting) {
      Piece.attackCounter += 1;
      this.attackOrder = Piece.attackCounter;
    }
    this.waiting = true;
    this.attackTarget = enemy;
  }

  private earlierAttackerExists(pieces: Piece[], col: number, row: number): boolean {
    if (this.attackOrder === null) return false;
    for (const q of pieces) {
      if (q !== this && q.alive && q.color === this.color && q.waiting
          && sameTile(q.nextTile, col, row)
          && q.attackOrder !== null && q.attackOrder < this.attackOrder) {
        return true;
      }
    }
    return false;
  }

  /** Alive friendly piece on, or sliding into, (col, row). Waiting (attacking)
   *  friendlies don't block, so several pieces can attack one tile. */
  private getBlocker(pieces: Piece[], col: number, row: number): Piece | null {
    for (const q of pieces) {
      if (q !== this && q.alive && q.color === this.color) {
        if (q.col === col && q.row === row) return q;
        if (q.moving && !q.waiting && sameTile(q.nextTile, col, row)) return q;
      }
    }
    return null;
  }

  private getStationaryEnemy(pieces: Piece[], col: number, row: number): Piece | null {
    for (const q of pieces) {
      if (q !== this && q.alive && q.color !== this.color
          && q.col === col && q.row === row && !q.moving) {
        return q;
      }
    }
    return null;
  }

  /** Alive enemy physically standing on (col, row); converging enemies don't count. */
  private getEnemyBlocking(pieces: Piece[], col: number, row: number): Piece | null {
    for (const q of pieces) {
      if (q !== this && q.alive && q.color !== this.color
          && q.col === col && q.row === row) {
        return q;
      }
    }
    return null;
  }

  stop(): void {
    this.snapToTile();
    this.targetCol = this.col;
    this.targetRow = this.row;
    this.moving = false;
    this.waiting = false;
    this.attackTarget = null;
    this.attackOrder = null;
    this.path = [];
    this.pathIndex = 0;
    if (this.name === "Knight") this.resetKnightVisual();
  }

  stopBtnCenter(): [number, number] {
    return [
      this.pixelX + TILE - STOP_BTN_RADIUS - 2,
      this.pixelY + STOP_BTN_RADIUS + 2,
    ];
  }

  stopBtnHit(mx: number, my: number): boolean {
    if (!this.moving || !this.alive) return false;
    const [cx, cy] = this.stopBtnCenter();
    return Math.hypot(mx - cx, my - cy) <= STOP_BTN_RADIUS;
  }
}
