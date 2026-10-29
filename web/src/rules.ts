import { BOARD, DAMAGE_PER_SECOND, HP_MAP, PieceName, Tile, inBounds, sameTile } from "./constants";
import { Piece } from "./piece";

/** True if a friendly piece occupies or is moving into (col, row), or the tile
 *  is off-board. Waiting (attacking) friendlies don't block. */
export function tileBlockedByOwn(pieces: Piece[], piece: Piece, col: number, row: number): boolean {
  for (const p of pieces) {
    if (p === piece || !p.alive || p.color !== piece.color) continue;
    if (p.col === col && p.row === row) return true;
    if (p.moving && !p.waiting && sameTile(p.nextTile, col, row)) return true;
  }
  return !inBounds(col, row);
}

function anyPieceAt(
  pieces: Piece[], col: number, row: number, exclude: Piece | null, includeNext = false,
): Piece | null {
  for (const p of pieces) {
    if (p === exclude || !p.alive) continue;
    if (p.col === col && p.row === row) return p;
    if (includeNext && p.moving && sameTile(p.nextTile, col, row)) return p;
  }
  return null;
}

function pawnPathClear(pieces: Piece[], piece: Piece, tc: number, tr: number): boolean {
  return anyPieceAt(pieces, tc, tr, piece, true) === null;
}

function slide(
  pieces: Piece[], piece: Piece, sc: number, sr: number, dc: number, dr: number, targets: Tile[],
): void {
  let nc = sc + dc;
  let nr = sr + dr;
  while (inBounds(nc, nr)) {
    const occ = anyPieceAt(pieces, nc, nr, piece);
    if (occ) {
      if (occ.color !== piece.color && !tileBlockedByOwn(pieces, piece, nc, nr)) {
        targets.push([nc, nr]);
      }
      break;
    }
    if (!tileBlockedByOwn(pieces, piece, nc, nr)) targets.push([nc, nr]);
    nc += dc;
    nr += dr;
  }
}

const KNIGHT_JUMPS: Tile[] = [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]];
const DIAGONALS: Tile[] = [[-1, -1], [-1, 1], [1, -1], [1, 1]];
const ORTHOGONALS: Tile[] = [[-1, 0], [1, 0], [0, -1], [0, 1]];

/** Tiles *piece* can move to right now (chess-like rules, ignoring check). */
export function getLegalTargets(piece: Piece, pieces: Piece[]): Tile[] {
  if (piece.moving) return [];
  const targets: Tile[] = [];
  const c = piece.col;
  const r = piece.row;

  const add = (tc: number, tr: number) => {
    if (inBounds(tc, tr) && !tileBlockedByOwn(pieces, piece, tc, tr)) targets.push([tc, tr]);
  };
  const slideAll = (dirs: Tile[]) => {
    for (const [dc, dr] of dirs) slide(pieces, piece, c, r, dc, dr, targets);
  };

  switch (piece.name) {
    case "Pawn": {
      const dir = piece.color === "white" ? -1 : 1;
      const fr = r + dir;
      if (inBounds(c, fr) && pawnPathClear(pieces, piece, c, fr)) {
        add(c, fr);
        const fr2 = r + 2 * dir;
        if (!piece.hasMoved && inBounds(c, fr2) && pawnPathClear(pieces, piece, c, fr2)) {
          add(c, fr2);
        }
      }
      // Diagonal captures — allowed if an enemy occupies or is sliding into the tile.
      for (const dc of [-1, 1]) {
        const tc = c + dc;
        if (inBounds(tc, fr)) {
          const occ = anyPieceAt(pieces, tc, fr, piece, true);
          if (occ && occ.color !== piece.color) add(tc, fr);
        }
      }
      break;
    }
    case "Knight":
      for (const [dc, dr] of KNIGHT_JUMPS) add(c + dc, r + dr);
      break;
    case "Bishop":
      slideAll(DIAGONALS);
      break;
    case "Rook":
      slideAll(ORTHOGONALS);
      break;
    case "Queen":
      slideAll([...DIAGONALS, ...ORTHOGONALS]);
      break;
    case "King":
      for (let dc = -1; dc <= 1; dc++) {
        for (let dr = -1; dr <= 1; dr++) {
          if (dc !== 0 || dr !== 0) add(c + dc, r + dr);
        }
      }
      break;
  }
  return targets;
}

/** Only the defender takes damage. An attacker is a moving piece, settled on
 *  its tile, whose next tile overlaps a tile the defender occupies. */
export function processCombat(pieces: Piece[], dt: number): void {
  const damage = DAMAGE_PER_SECOND * dt;

  for (const p of pieces) p.beingAttacked = false;

  // Collect hits first so simultaneous lethal blows land regardless of array order.
  const hits: Piece[] = [];
  for (const attacker of pieces) {
    if (!attacker.alive || !attacker.moving) continue;
    if (!attacker.hasReachedTile()) continue;
    const target = attacker.nextTile;
    if (target === null) continue;
    // Pawns only deal damage diagonally, never forward.
    if (attacker.name === "Pawn" && target[0] === attacker.col) continue;

    for (const defender of pieces) {
      if (defender === attacker || !defender.alive || defender.color === attacker.color) continue;
      // A defender is vulnerable at its next tile only while genuinely in transit.
      const hit = (defender.col === target[0] && defender.row === target[1])
        || (defender.moving && !defender.hasReachedTile()
            && sameTile(defender.nextTile, target[0], target[1]));
      if (hit) hits.push(defender);
    }
  }

  for (const defender of hits) {
    defender.hp -= damage;
    defender.beingAttacked = true;
    if (defender.hp <= 0) {
      defender.hp = 0;
      defender.alive = false;
    }
  }
}

const BACK_RANK: PieceName[] = ["Rook", "Knight", "Bishop", "Queen", "King", "Bishop", "Knight", "Rook"];

/** Pawns that have come to rest on the far rank become Queens. Returns the promoted pieces. */
export function promotePawns(pieces: Piece[], queenHp: number): Piece[] {
  const promoted: Piece[] = [];
  for (const p of pieces) {
    const lastRow = p.color === "white" ? 0 : BOARD - 1;
    if (p.alive && p.name === "Pawn" && !p.moving && p.row === lastRow) {
      p.promote("Queen", queenHp);
      promoted.push(p);
    }
  }
  return promoted;
}

export function createPieces(hp: Record<PieceName, number> = HP_MAP): Piece[] {
  const pieces: Piece[] = [];
  BACK_RANK.forEach((name, i) => pieces.push(new Piece("black", name, i, 0, hp[name])));
  for (let i = 0; i < BOARD; i++) pieces.push(new Piece("black", "Pawn", i, 1, hp.Pawn));
  for (let i = 0; i < BOARD; i++) pieces.push(new Piece("white", "Pawn", i, 6, hp.Pawn));
  BACK_RANK.forEach((name, i) => pieces.push(new Piece("white", name, i, 7, hp[name])));
  return pieces;
}
