import {
  ATTACK_DOT_COLOR, BOARD, Color, DARK_COLOR, HIGHLIGHT_COLOR, LIGHT_COLOR, MOVE_DOT_COLOR,
  PIECE_NAMES, PieceName, STATUS_H, STOP_BTN_RADIUS, TILE, Tile, WIDTH, sameTile,
} from "./constants";
import { Piece } from "./piece";

export type Images = Record<Color, Record<PieceName, HTMLImageElement>>;

// Pawn and Rook are drawn 30% narrower, centred in the tile.
const NARROW: ReadonlySet<PieceName> = new Set<PieceName>(["Pawn", "Rook"]);

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load ${src}`));
    img.src = src;
  });
}

export async function loadPieceImages(): Promise<Images> {
  const images = { white: {}, black: {} } as Images;
  await Promise.all(
    PIECE_NAMES.flatMap((name) =>
      (["white", "black"] as const).map(async (color) => {
        images[color][name] = await loadImage(`pieces/${name}/${color}.png`);
      }),
    ),
  );
  return images;
}

export function drawBoard(ctx: CanvasRenderingContext2D): void {
  for (let r = 0; r < BOARD; r++) {
    for (let c = 0; c < BOARD; c++) {
      ctx.fillStyle = (r + c) % 2 === 0 ? LIGHT_COLOR : DARK_COLOR;
      ctx.fillRect(c * TILE, r * TILE, TILE, TILE);
    }
  }
}

function dot(ctx: CanvasRenderingContext2D, c: number, r: number, radius: number, color: string): void {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(c * TILE + TILE / 2, r * TILE + TILE / 2, radius, 0, Math.PI * 2);
  ctx.fill();
}

/** Tiles occupied by enemies of *selected* (current + mid-slide next tile). */
function enemyTiles(selected: Piece, pieces: Piece[]): Tile[] {
  const tiles: Tile[] = [];
  for (const p of pieces) {
    if (p === selected || !p.alive || p.color === selected.color) continue;
    tiles.push([p.col, p.row]);
    const nt = p.nextTile;
    if (p.moving && nt) tiles.push(nt);
  }
  return tiles;
}

export function drawHighlights(
  ctx: CanvasRenderingContext2D, selected: Piece | null, targets: Tile[], pieces: Piece[],
): void {
  if (!selected) return;
  ctx.fillStyle = HIGHLIGHT_COLOR;
  ctx.fillRect(selected.col * TILE, selected.row * TILE, TILE, TILE);
  const enemies = enemyTiles(selected, pieces);
  for (const [tc, tr] of targets) {
    if (!enemies.some((t) => sameTile(t, tc, tr))) dot(ctx, tc, tr, 15, MOVE_DOT_COLOR);
  }
}

export function drawAttackDots(
  ctx: CanvasRenderingContext2D, selected: Piece | null, targets: Tile[], pieces: Piece[],
): void {
  if (!selected) return;
  const enemies = enemyTiles(selected, pieces);
  for (const [tc, tr] of targets) {
    if (enemies.some((t) => sameTile(t, tc, tr))) dot(ctx, tc, tr, 18, ATTACK_DOT_COLOR);
  }
}

function drawImg(ctx: CanvasRenderingContext2D, img: HTMLImageElement, name: PieceName, x: number, y: number, alpha = 1): void {
  if (alpha <= 0) return;
  ctx.globalAlpha = alpha;
  if (NARROW.has(name)) {
    const w = Math.trunc(TILE * 0.7);
    ctx.drawImage(img, x + Math.trunc((TILE - w) / 2), y, w, TILE);
  } else {
    ctx.drawImage(img, x, y, TILE, TILE);
  }
  ctx.globalAlpha = 1;
}

function line(ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number): void {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function arrow(
  ctx: CanvasRenderingContext2D, sx: number, sy: number, ex: number, ey: number, color: string, spread: number,
): void {
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  line(ctx, sx, sy, ex, ey);
  const angle = Math.atan2(ey - sy, ex - sx);
  const headLen = 14;
  for (const sign of [1, -1]) {
    line(ctx, ex, ey,
      ex - headLen * Math.cos(angle + sign * spread),
      ey - headLen * Math.sin(angle + sign * spread));
  }
}

function drawHp(ctx: CanvasRenderingContext2D, p: Piece, now: number): void {
  const barW = TILE - 10;
  const barH = 6;
  const bx = p.pixelX + 5;
  const by = p.pixelY + TILE - 10;
  const ratio = Math.max(p.hp / p.maxHp, 0);
  ctx.fillStyle = "rgb(60,60,60)";
  ctx.fillRect(bx, by, barW, barH);
  // Blink while being attacked.
  const blinkOn = !p.beingAttacked || Math.floor(now / 150) % 2 === 0;
  if (blinkOn) {
    ctx.fillStyle = ratio > 0.5 ? "rgb(0,200,0)" : ratio > 0.2 ? "rgb(220,140,0)" : "rgb(210,30,30)";
    ctx.fillRect(bx, by, Math.trunc(barW * ratio), barH);
  }
  ctx.strokeStyle = "black";
  ctx.lineWidth = 1;
  ctx.strokeRect(bx + 0.5, by + 0.5, barW - 1, barH - 1);
}

function drawStopBtn(ctx: CanvasRenderingContext2D, p: Piece): void {
  const [cx, cy] = p.stopBtnCenter();
  ctx.fillStyle = "rgb(200,40,40)";
  ctx.beginPath();
  ctx.arc(cx, cy, STOP_BTN_RADIUS, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "white";
  ctx.lineWidth = 2;
  const m = 4;
  line(ctx, cx - m, cy - m, cx + m, cy + m);
  line(ctx, cx + m, cy - m, cx - m, cy + m);
}

export function drawPiece(ctx: CanvasRenderingContext2D, p: Piece, images: Images, now: number): void {
  if (!p.alive) return;
  const img = images[p.color][p.name];

  if (p.name === "Knight" && p.knightPhase === "crossfade") {
    drawImg(ctx, img, p.name, p.originCol * TILE, p.originRow * TILE, p.knightAlpha / 255);
    drawImg(ctx, img, p.name, p.targetCol * TILE, p.targetRow * TILE, p.knightDestAlpha / 255);
  } else if (p.name === "Knight" && p.knightPhase === "waiting") {
    drawImg(ctx, img, p.name, p.originCol * TILE, p.originRow * TILE);
  } else {
    drawImg(ctx, img, p.name, p.pixelX, p.pixelY);
  }

  drawHp(ctx, p, now);

  const half = TILE / 2;
  if (p.moving && !p.waiting) {
    const sx = p.originCol * TILE + half;
    const sy = p.originRow * TILE + half;
    const ex = p.targetCol * TILE + half;
    const ey = p.targetRow * TILE + half;
    if (sx !== ex || sy !== ey) arrow(ctx, sx, sy, ex, ey, "rgb(40,100,220)", 0.45);
  }
  const nt = p.nextTile;
  if (p.waiting && nt) {
    arrow(ctx, p.col * TILE + half, p.row * TILE + half, nt[0] * TILE + half, nt[1] * TILE + half,
      "rgb(220,30,30)", 0.8);
  }
  if (p.moving) drawStopBtn(ctx, p);
}

export interface StatusInfo {
  text: string;
  textColor: string;
  cooldownFrac: number | null; // null hides the meter
  cooldownLeft: number;
}

export function drawStatus(ctx: CanvasRenderingContext2D, s: StatusInfo): void {
  const y0 = TILE * BOARD;
  ctx.fillStyle = "rgb(30,30,30)";
  ctx.fillRect(0, y0, WIDTH, STATUS_H);
  ctx.font = "22px Consolas, 'Courier New', monospace";
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  ctx.fillStyle = s.textColor;
  ctx.fillText(s.text, 10, y0 + STATUS_H / 2);

  if (s.cooldownFrac === null) return;
  const ready = s.cooldownFrac >= 1;
  const barW = 150;
  const barH = 18;
  const barX = WIDTH - barW - 12;
  const barY = y0 + 11;
  ctx.fillStyle = "rgb(60,60,60)";
  ctx.fillRect(barX, barY, barW, barH);
  ctx.fillStyle = ready ? "rgb(90,200,90)" : "rgb(210,165,60)";
  ctx.fillRect(barX, barY, Math.trunc(barW * s.cooldownFrac), barH);
  ctx.fillStyle = "rgb(245,245,245)";
  ctx.textAlign = "center";
  ctx.fillText(ready ? "READY" : `${s.cooldownLeft.toFixed(1)}s`, barX + barW / 2, barY + barH / 2);
}
