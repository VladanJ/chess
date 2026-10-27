import "./style.css";
import { AIController } from "./ai";
import { Brain, NNPolicy, loadBrain } from "./brain";
import {
  BASE_PIECE_SPEED, Color, DEFAULT_SPEED, HEIGHT, SPEED_PRESETS, SpeedKey, TILE, Tile, WIDTH, inBounds,
} from "./constants";
import { Piece, setPieceSpeed } from "./piece";
import {
  Images, drawAttackDots, drawBoard, drawHighlights, drawPiece, drawStatus, loadPieceImages,
} from "./render";
import { createPieces, getLegalTargets, processCombat } from "./rules";

interface Settings {
  speed: SpeedKey;
  aiEnabled: boolean;
  difficulty: number;
}

interface Game {
  pieces: Piece[];
  ai: AIController | null;
  myColor: Color | null; // null = hotseat, both colors playable
  selected: Piece | null;
  legalTargets: Tile[];
  gameOver: boolean;
  winner: string | null;
  cooldownMs: number;
  lastActionMs: number;
  whiteStarted: boolean;
}

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const canvas = $<HTMLCanvasElement>("board");
const ctx = canvas.getContext("2d")!;
const menu = $("menu");
const gameOverPanel = $("gameover");

const settings: Settings = { speed: DEFAULT_SPEED, aiEnabled: true, difficulty: 5 };
let images: Images | null = null;
let brain: Brain | null = null;
let game: Game | null = null;

// --- Canvas sizing (sharp on HiDPI screens) ---------------------------------

function resizeCanvas(): void {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(WIDTH * dpr);
  canvas.height = Math.round(HEIGHT * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

// --- Settings menu -----------------------------------------------------------

function renderMenu(): void {
  document.querySelectorAll<HTMLButtonElement>("#speed-buttons button").forEach((b) => {
    b.classList.toggle("active", b.dataset.speed === settings.speed);
  });
  $("opp-ai").classList.toggle("active", settings.aiEnabled);
  $("opp-hotseat").classList.toggle("active", !settings.aiEnabled);
  $<HTMLButtonElement>("diff-minus").disabled = !settings.aiEnabled;
  $<HTMLButtonElement>("diff-plus").disabled = !settings.aiEnabled;
  $("diff-label").classList.toggle("disabled", !settings.aiEnabled);
  $("diff-value").textContent = settings.aiEnabled
    ? (settings.difficulty === 0 ? "OFF" : String(settings.difficulty))
    : "-";
}

function showMenu(): void {
  game = null;
  gameOverPanel.classList.add("hidden");
  menu.classList.remove("hidden");
  renderMenu();
}

function initMenu(): void {
  document.querySelectorAll<HTMLButtonElement>("#speed-buttons button").forEach((b) => {
    b.addEventListener("click", () => {
      settings.speed = b.dataset.speed as SpeedKey;
      renderMenu();
    });
  });
  $("opp-ai").addEventListener("click", () => { settings.aiEnabled = true; renderMenu(); });
  $("opp-hotseat").addEventListener("click", () => { settings.aiEnabled = false; renderMenu(); });
  $("diff-minus").addEventListener("click", () => {
    settings.difficulty = Math.max(0, settings.difficulty - 1);
    renderMenu();
  });
  $("diff-plus").addEventListener("click", () => {
    settings.difficulty = Math.min(10, settings.difficulty + 1);
    renderMenu();
  });
  $("start").addEventListener("click", startGame);
  $("again").addEventListener("click", showMenu);
  renderMenu();
}

// --- Game lifecycle ----------------------------------------------------------

function startGame(): void {
  if (!images) return;
  const moveInterval = SPEED_PRESETS[settings.speed];
  setPieceSpeed((BASE_PIECE_SPEED * SPEED_PRESETS.fast) / moveInterval);
  Piece.attackCounter = 0;

  // Difficulty 0 means the AI is disabled.
  const aiEnabled = settings.aiEnabled && settings.difficulty > 0;
  let ai: AIController | null = null;
  if (aiEnabled) {
    ai = new AIController("black", settings.difficulty, brain ? new NNPolicy(brain) : null);
    // Same cadence as the human; difficulty controls skill, not speed.
    ai.actionsPerSecond = 1.0 / moveInterval;
  }

  const cooldownMs = Math.trunc(moveInterval * 1000);
  game = {
    pieces: createPieces(),
    ai,
    myColor: aiEnabled ? "white" : null,
    selected: null,
    legalTargets: [],
    gameOver: false,
    winner: null,
    cooldownMs,
    lastActionMs: performance.now() - cooldownMs,
    whiteStarted: false,
  };
  menu.classList.add("hidden");
  gameOverPanel.classList.add("hidden");
}

function endGame(g: Game, winner: string): void {
  g.gameOver = true;
  g.winner = winner;
  $("winner-text").textContent = `${winner} wins!`;
  gameOverPanel.classList.remove("hidden");
}

// --- Input -------------------------------------------------------------------

function deselect(g: Game): void {
  g.selected = null;
  g.legalTargets = [];
}

function handleClick(g: Game, mx: number, my: number): void {
  // Stop buttons first.
  for (const p of g.pieces) {
    if (p.stopBtnHit(mx, my)) {
      if (g.myColor !== null && p.color !== g.myColor) continue;
      p.stop();
      deselect(g);
      return;
    }
  }

  const col = Math.floor(mx / TILE);
  const row = Math.floor(my / TILE);
  if (!inBounds(col, row)) {
    deselect(g);
    return;
  }

  let clicked = g.pieces.find((p) => p.alive && !p.moving && p.col === col && p.row === row) ?? null;
  if (g.myColor !== null && clicked && clicked.color !== g.myColor) clicked = null;

  const sel = g.selected;
  if (clicked && (clicked === sel || (sel && clicked.color === sel.color))) {
    g.selected = clicked;
    g.legalTargets = getLegalTargets(clicked, g.pieces);
  } else if (sel && g.legalTargets.some(([c, r]) => c === col && r === row)) {
    // Blocked moves keep the selection so the player can retry.
    const now = performance.now();
    if (sel.color === "black" && !g.whiteStarted) return;
    if (g.cooldownMs && now - g.lastActionMs < g.cooldownMs) return;
    g.lastActionMs = now;
    sel.startMove(col, row);
    deselect(g);
  } else if (clicked) {
    g.selected = clicked;
    g.legalTargets = getLegalTargets(clicked, g.pieces);
  } else {
    deselect(g);
  }
}

canvas.addEventListener("pointerdown", (e) => {
  if (!game || game.gameOver || e.button !== 0) return;
  const rect = canvas.getBoundingClientRect();
  const mx = ((e.clientX - rect.left) * WIDTH) / rect.width;
  const my = ((e.clientY - rect.top) * HEIGHT) / rect.height;
  handleClick(game, mx, my);
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && game) showMenu();
  else if (e.key === "Enter" && !game && !menu.classList.contains("hidden")) startGame();
});

window.addEventListener("resize", resizeCanvas);

// --- Main loop ---------------------------------------------------------------

function simulate(g: Game, dt: number): void {
  if (!g.whiteStarted && g.pieces.some((p) => p.color === "white" && p.moving)) {
    g.whiteStarted = true;
  }
  if (g.ai && g.whiteStarted) g.ai.update(dt, g.pieces);

  // Combat before movement so damage applies until full arrival.
  processCombat(g.pieces, dt);
  for (const p of g.pieces) p.update(dt, g.pieces);

  for (const p of g.pieces) {
    if (p.name === "King" && !p.alive) endGame(g, p.color === "white" ? "Black" : "White");
  }
  if (g.selected && (!g.selected.alive || g.selected.moving)) deselect(g);
}

function render(now: number): void {
  drawBoard(ctx);
  if (!game || !images) return;
  const g = game;
  drawHighlights(ctx, g.selected, g.legalTargets, g.pieces);
  for (const p of g.pieces) drawPiece(ctx, p, images, now);
  drawAttackDots(ctx, g.selected, g.legalTargets, g.pieces);

  let text = "Click a piece to select, then click a target.";
  let textColor = "rgb(180,180,180)";
  if (g.gameOver) {
    text = `${g.winner} wins!`;
    textColor = "rgb(255,255,100)";
  } else if (g.selected) {
    text = `Selected: ${g.selected.color} ${g.selected.name}`;
    textColor = "rgb(220,220,220)";
  } else if (!g.whiteStarted) {
    text = "White moves first.";
  }

  const elapsed = now - g.lastActionMs;
  drawStatus(ctx, {
    text,
    textColor,
    cooldownFrac: g.cooldownMs && !g.gameOver ? Math.max(0, Math.min(1, elapsed / g.cooldownMs)) : null,
    cooldownLeft: (g.cooldownMs - elapsed) / 1000,
  });
}

let lastFrame = performance.now();

function frame(now: number): void {
  // Clamp dt so a backgrounded tab doesn't teleport pieces on resume.
  const dt = Math.min((now - lastFrame) / 1000, 0.1);
  lastFrame = now;
  if (game && !game.gameOver) simulate(game, dt);
  render(now);
  requestAnimationFrame(frame);
}

// --- Boot --------------------------------------------------------------------

async function boot(): Promise<void> {
  resizeCanvas();
  initMenu();
  const startBtn = $<HTMLButtonElement>("start");
  startBtn.disabled = true;
  const [imgs, b] = await Promise.all([loadPieceImages(), loadBrain("brain.json")]);
  images = imgs;
  brain = b;
  startBtn.disabled = false;
  requestAnimationFrame(frame);
}

boot().catch((err) => {
  console.error(err);
  $("start").textContent = "Failed to load assets";
});
