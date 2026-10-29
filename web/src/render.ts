import {
  ATTACK_DOT_COLOR, BOARD, Color, DARK_COLOR, HIGHLIGHT_COLOR, LIGHT_COLOR, MOVE_DOT_COLOR,
  PIECE_NAMES, PieceName, STATUS_H, STOP_BTN_RADIUS, TILE, Tile, WIDTH, sameTile,
} from "./constants";
import { Piece } from "./piece";

export type Images = Record<Color, Record<PieceName, HTMLImageElement>>;
export type PieceSet = "war" | "classic";

const PROMO_MS = 800;

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`Failed to load ${src}`));
    img.src = src;
  });
}

export async function loadPieceImages(set: PieceSet): Promise<Images> {
  const images = { white: {}, black: {} } as Images;
  await Promise.all(
    PIECE_NAMES.flatMap((name) =>
      (["white", "black"] as const).map(async (color) => {
        images[color][name] = await loadImage(`pieces/${set}/${name}/${color}.svg`);
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

function drawImg(ctx: CanvasRenderingContext2D, img: HTMLImageElement, x: number, y: number, alpha = 1): void {
  if (alpha <= 0) return;
  ctx.globalAlpha = alpha;
  ctx.drawImage(img, x, y, TILE, TILE);
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
    drawImg(ctx, img, p.originCol * TILE, p.originRow * TILE, p.knightAlpha / 255);
    drawImg(ctx, img, p.targetCol * TILE, p.targetRow * TILE, p.knightDestAlpha / 255);
  } else if (p.name === "Knight" && p.knightPhase === "waiting") {
    drawImg(ctx, img, p.originCol * TILE, p.originRow * TILE);
  } else {
    drawImg(ctx, img, p.pixelX, p.pixelY);
  }

  drawHp(ctx, p, now);

  if (p.promotedAt !== null) {
    const u = (now - p.promotedAt) / PROMO_MS;
    if (u < 1) {
      ctx.globalAlpha = 1 - u;
      ctx.strokeStyle = "#f6c945";
      ctx.lineWidth = 7 * (1 - u) + 1;
      ctx.beginPath();
      ctx.arc(p.pixelX + TILE / 2, p.pixelY + TILE / 2, 20 + 45 * u, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

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

export const DEATH_MS = 1000;
const SPARKLE_COLORS = ["#ffd166", "#ff8fab", "#8ecae6", "#b8f2a0"];

const easeOut = (u: number) => 1 - (1 - u) * (1 - u);

function sparkle(ctx: CanvasRenderingContext2D, x: number, y: number, r: number): void {
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    const d = i % 2 === 0 ? r : r * 0.35;
    ctx.lineTo(x + Math.cos(a) * d, y + Math.sin(a) * d);
  }
  ctx.closePath();
  ctx.fill();
}

function ghost(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: Color, alpha: number): void {
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color === "white" ? "#ffffff" : "#d9d2ff";
  ctx.strokeStyle = "rgba(40,40,50,0.8)";
  ctx.lineWidth = 2;
  const bottom = y + r * 1.2;
  ctx.beginPath();
  ctx.arc(x, y, r, Math.PI, 0);
  ctx.lineTo(x + r, bottom);
  // Wavy hem: three bumps.
  const bump = (2 * r) / 3;
  for (let i = 0; i < 3; i++) {
    const x0 = x + r - i * bump;
    ctx.quadraticCurveTo(x0 - bump / 2, bottom - r * 0.35, x0 - bump, bottom);
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#2b2b36";
  for (const dx of [-0.38, 0.38]) {
    ctx.beginPath();
    ctx.ellipse(x + dx * r, y - r * 0.05, r * 0.14, r * 0.2, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = "rgba(255,120,150,0.6)";
  for (const dx of [-0.62, 0.62]) {
    ctx.beginPath();
    ctx.arc(x + dx * r, y + r * 0.3, r * 0.14, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

/** Squish, twirl away, burst of sparkles and a little ghost floating up. */
export function drawDeaths(ctx: CanvasRenderingContext2D, pieces: Piece[], images: Images, now: number): void {
  for (const p of pieces) {
    if (p.alive) continue;
    p.diedAt ??= now;
    const t = (now - p.diedAt) / DEATH_MS;
    if (t >= 1) continue;
    const cx = p.pixelX + TILE / 2;
    const cy = p.pixelY + TILE / 2;
    const seed = (p.col * 7 + p.row * 13) * 0.37;

    if (t < 0.35) {
      const u = t / 0.35;
      ctx.globalAlpha = 1 - u;
      ctx.strokeStyle = "white";
      ctx.lineWidth = 5 * (1 - u);
      ctx.beginPath();
      ctx.arc(cx, cy, 12 + 40 * easeOut(u), 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    const squish = t < 0.12 ? Math.sin((Math.PI * t) / 0.12) * 0.3 : 0;
    const v = Math.max(0, (t - 0.12) / 0.88);
    const scale = Math.pow(1 - v, 1.5);
    if (scale > 0.01) {
      const img = images[p.color][p.name];
      ctx.save();
      ctx.globalAlpha = 1 - v * v;
      ctx.translate(cx, cy - 36 * Math.sin(Math.PI * v));
      ctx.rotate(v * Math.PI * 2 * (p.color === "white" ? 1 : -1));
      ctx.scale((1 + squish) * scale, (1 - squish) * scale);
      ctx.drawImage(img, -TILE / 2, -TILE / 2, TILE, TILE);
      ctx.restore();
    }

    if (t > 0.05) {
      const u = (t - 0.05) / 0.95;
      ctx.globalAlpha = 1 - u;
      for (let i = 0; i < 8; i++) {
        const a = seed + (i * Math.PI * 2) / 8;
        const d = 10 + 50 * easeOut(u);
        ctx.fillStyle = SPARKLE_COLORS[i % SPARKLE_COLORS.length];
        sparkle(ctx, cx + Math.cos(a) * d, cy + Math.sin(a) * d, 8 * (1 - u) + 2);
      }
      ctx.globalAlpha = 1;
    }

    if (t > 0.25) {
      const g = (t - 0.25) / 0.75;
      ghost(ctx, cx + Math.sin(g * Math.PI * 3) * 6, cy - 10 - 55 * g, 16, p.color, Math.sin(Math.PI * g));
    }
  }
}

export interface CooldownMeter {
  label: string | null;
  frac: number;
  left: number; // seconds
}

export interface StatusInfo {
  text: string;
  textColor: string;
  meters: CooldownMeter[]; // empty hides the meters
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

  const barW = s.meters.length > 1 ? 110 : 150;
  const barH = 18;
  const barY = y0 + 11;
  let x = WIDTH - 12;
  for (const m of [...s.meters].reverse()) {
    x -= barW;
    const ready = m.frac >= 1;
    ctx.fillStyle = "rgb(60,60,60)";
    ctx.fillRect(x, barY, barW, barH);
    ctx.fillStyle = ready ? "rgb(90,200,90)" : "rgb(210,165,60)";
    ctx.fillRect(x, barY, Math.trunc(barW * m.frac), barH);
    ctx.fillStyle = "rgb(245,245,245)";
    ctx.textAlign = "center";
    ctx.fillText(ready ? "READY" : `${m.left.toFixed(1)}s`, x + barW / 2, barY + barH / 2);
    if (m.label) {
      ctx.fillStyle = "rgb(200,200,200)";
      ctx.textAlign = "right";
      ctx.fillText(m.label, x - 6, barY + barH / 2);
      x -= 6 + ctx.measureText(m.label).width;
    }
    x -= 16;
  }
}
