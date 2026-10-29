export const TILE = 100;
export const BOARD = 8;
export const WIDTH = TILE * BOARD;
export const STATUS_H = 40;
export const HEIGHT = WIDTH + STATUS_H;

export type Color = "white" | "black";
export type PieceName = "Pawn" | "Knight" | "Bishop" | "Rook" | "Queen" | "King";
export type Tile = readonly [number, number];

export const PIECE_NAMES: readonly PieceName[] = [
  "Pawn", "Knight", "Bishop", "Rook", "Queen", "King",
];

export const HP_MAP: Record<PieceName, number> = {
  Pawn: 100,
  Knight: 200,
  Bishop: 200,
  Rook: 300,
  Queen: 500,
  King: 500,
};

// Relative worth of each piece, used by the AI to prioritise captures.
export const PIECE_VALUE: Record<PieceName, number> = {
  Pawn: 1,
  Knight: 3,
  Bishop: 3,
  Rook: 5,
  Queen: 9,
  King: 100,
};

export const DAMAGE_PER_SECOND = 10;
export const STOP_BTN_RADIUS = 10;

// Movement speed (tiles/sec) at the fastest cadence; scaled by game speed.
export const BASE_PIECE_SPEED = 0.3;

// Seconds a player must wait between moves.
export const SPEED_PRESETS = { fast: 1.0, medium: 3.0, slow: 5.0 } as const;
export type SpeedKey = keyof typeof SPEED_PRESETS;
export const DEFAULT_SPEED: SpeedKey = "medium";

export const LIGHT_COLOR = "rgb(240,217,181)";
export const DARK_COLOR = "rgb(181,136,99)";
export const HIGHLIGHT_COLOR = "rgba(186,202,68,0.59)";
export const MOVE_DOT_COLOR = "rgba(100,100,100,0.63)";
export const ATTACK_DOT_COLOR = "rgba(220,30,30,0.78)";

export function inBounds(col: number, row: number): boolean {
  return col >= 0 && col < BOARD && row >= 0 && row < BOARD;
}

export function sameTile(a: Tile | null, col: number, row: number): boolean {
  return a !== null && a[0] === col && a[1] === row;
}
