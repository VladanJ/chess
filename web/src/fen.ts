import { BOARD, Color, PieceName } from "./constants";

export interface PieceSpec {
  color: Color;
  name: PieceName;
  col: number;
  row: number;
}

const LETTER: Record<PieceName, string> = { Pawn: "p", Knight: "n", Bishop: "b", Rook: "r", Queen: "q", King: "k" };
const NAME = Object.fromEntries(Object.entries(LETTER).map(([n, l]) => [l, n])) as Record<string, PieceName>;

/** Piece placement in FEN notation (rank 8 = row 0 first; uppercase = white). */
export function toFen(pieces: PieceSpec[]): string {
  const rows: string[] = [];
  for (let r = 0; r < BOARD; r++) {
    let row = "";
    let empty = 0;
    for (let c = 0; c < BOARD; c++) {
      const p = pieces.find((q) => q.col === c && q.row === r);
      if (!p) {
        empty++;
        continue;
      }
      if (empty) row += empty;
      empty = 0;
      row += p.color === "white" ? LETTER[p.name].toUpperCase() : LETTER[p.name];
    }
    rows.push(empty ? row + empty : row);
  }
  return rows.join("/");
}

/** Parses the placement field of a FEN string; null if it isn't a valid 8x8 board. */
export function fromFen(fen: string): PieceSpec[] | null {
  const rows = fen.trim().split(" ")[0].split("/");
  if (rows.length !== BOARD) return null;
  const pieces: PieceSpec[] = [];
  for (let r = 0; r < BOARD; r++) {
    let c = 0;
    for (const ch of rows[r]) {
      if (/[1-8]/.test(ch)) {
        c += Number(ch);
      } else {
        const name = NAME[ch.toLowerCase()];
        if (!name || c >= BOARD) return null;
        pieces.push({ color: ch === ch.toUpperCase() ? "white" : "black", name, col: c, row: r });
        c++;
      }
    }
    if (c !== BOARD) return null;
  }
  return pieces;
}
