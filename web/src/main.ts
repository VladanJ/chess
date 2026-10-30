import "./style.css";
import { AIController } from "./ai";
import { Brain, NNPolicy, loadBrain } from "./brain";
import {
  BASE_PIECE_SPEED, BOARD, Color, DEFAULT_SPEED, HEIGHT, HP_MAP, PIECE_NAMES, PieceName, SPEED_PRESETS,
  STOP_BTN_RADIUS, SpeedKey, TILE, Tile, WIDTH, inBounds,
} from "./constants";
import { PieceSpec, fromFen, toFen } from "./fen";
import { Piece, setPieceSpeed } from "./piece";
import {
  DEATH_MS, Images, PieceSet, drawAttackDots, drawBoard, drawDeaths, drawGuards, drawHighlights, drawPiece,
  drawPromotionChoices, drawStatus, loadPieceImages, promotionChoiceAt,
} from "./render";
import { createPieces, getLegalTargets, pawnsToPromote, processCombat } from "./rules";
import { setAdPlaying, setPortalMuted, setSoundEnabled, sfx, unlockAudio } from "./sound";
import { portal } from "@portal";

interface Settings {
  speed: SpeedKey;
  aiEnabled: boolean;
  difficulty: number;
  hp: Record<PieceName, number>;
  pieceSet: PieceSet;
  promotion: "auto" | "choose";
  guard: boolean; // formation defense
  sound: boolean;
}

const HP_MIN = 10;
const HP_MAX = 10000;

interface Game {
  pieces: Piece[];
  ai: AIController | null;
  myColor: Color | null; // null = hotseat, both colors playable
  selected: Piece | null;
  legalTargets: Tile[];
  gameOver: boolean;
  winner: string | null;
  cooldownMs: number;
  lastActionMs: Record<Color, number>;
  whiteStarted: boolean;
  sandbox: boolean; // board-editor game: both sides, no cooldown
}

type Brush = { color: Color; name: PieceName } | "erase";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const canvas = $<HTMLCanvasElement>("board");
const ctx = canvas.getContext("2d")!;
const menu = $("menu");
const gameOverPanel = $("gameover");
const editorPanel = $("editor");
// Hidden board editor, enabled with ?sandbox in the URL; ?setup=<FEN> preloads a layout.
const params = new URLSearchParams(location.search);
const SANDBOX = params.has("sandbox");
const SHARED_SETUP = fromFen(params.get("setup") ?? "");

const settings: Settings = {
  speed: DEFAULT_SPEED, aiEnabled: true, difficulty: 5, hp: { ...HP_MAP }, pieceSet: "war",
  promotion: "auto", guard: false, sound: true,
};
const hpInputs = new Map<PieceName, HTMLInputElement>();
let images: Record<PieceSet, Images> | null = null;
let brain: Brain | null = null;
let game: Game | null = null;
let editorPieces: Piece[] | null = null; // non-null while the editor is open
let brush: Brush = { color: "white", name: "Pawn" };
let sandboxLayout: PieceSpec[] = [];
let playing = false;      // last gameplay state reported to the portal
let gamesStarted = 0;
let adRunning = false;    // ignore new-game requests while an ad break runs

/** Reports gameplay start/stop to the portal, once per change. */
function setPlaying(on: boolean): void {
  if (on === playing) return;
  playing = on;
  if (on) portal.gameplayStart();
  else portal.gameplayStop();
}

/** Starts a match, after a portal ad break if this isn't the session's first match. */
async function requestGame(layout: PieceSpec[] | null = null): Promise<void> {
  if (adRunning || !images) return;
  unlockAudio();
  if (gamesStarted > 0) {
    adRunning = true;
    await portal.commercialBreak();
    adRunning = false;
  }
  gamesStarted++;
  startGame(layout);
}

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
  for (const [name, input] of hpInputs) input.value = String(settings.hp[name]);
  document.querySelectorAll<HTMLButtonElement>("#set-buttons button").forEach((b) => {
    b.classList.toggle("active", b.dataset.set === settings.pieceSet);
  });
  document.querySelectorAll<HTMLButtonElement>("#promo-mode button").forEach((b) => {
    b.classList.toggle("active", b.dataset.promo === settings.promotion);
  });
  document.querySelectorAll<HTMLButtonElement>("#guard-mode button").forEach((b) => {
    b.classList.toggle("active", (b.dataset.guard === "on") === settings.guard);
  });
  document.querySelectorAll<HTMLButtonElement>("#sound-mode button").forEach((b) => {
    b.classList.toggle("active", (b.dataset.sound === "on") === settings.sound);
  });
  saveSettings();
}

// --- Saved settings ----------------------------------------------------------

const STORAGE_KEY = "rtchess.settings";

/** Restores saved settings, keeping defaults for anything missing or invalid. */
function loadSettings(): void {
  let s: Record<string, unknown>;
  try {
    s = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    return;
  }
  if (typeof s !== "object" || s === null) return;
  if (typeof s.speed === "string" && s.speed in SPEED_PRESETS) settings.speed = s.speed as SpeedKey;
  if (typeof s.aiEnabled === "boolean") settings.aiEnabled = s.aiEnabled;
  if (Number.isInteger(s.difficulty) && (s.difficulty as number) >= 0 && (s.difficulty as number) <= 10) {
    settings.difficulty = s.difficulty as number;
  }
  if (s.pieceSet === "war" || s.pieceSet === "classic") settings.pieceSet = s.pieceSet;
  if (s.promotion === "auto" || s.promotion === "choose") settings.promotion = s.promotion;
  if (typeof s.guard === "boolean") settings.guard = s.guard;
  if (typeof s.sound === "boolean") settings.sound = s.sound;
  const hp = (s.hp ?? {}) as Record<string, unknown>;
  for (const name of PIECE_NAMES) {
    const v = hp[name];
    if (typeof v === "number" && v >= HP_MIN && v <= HP_MAX) settings.hp[name] = Math.round(v);
  }
}

function saveSettings(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Storage can be unavailable (private mode, quota); settings then last for the session.
  }
  setSoundEnabled(settings.sound);
}

const optionsPanel = $("options");

function openOptions(): void {
  menu.classList.add("hidden");
  optionsPanel.classList.remove("hidden");
  renderMenu();
}

function closeOptions(): void {
  // Blur fires the input's change event so a just-typed HP value is applied.
  if (document.activeElement instanceof HTMLInputElement) document.activeElement.blur();
  optionsPanel.classList.add("hidden");
  menu.classList.remove("hidden");
}

const howtoPanel = $("howto");

function openHowto(): void {
  menu.classList.add("hidden");
  howtoPanel.classList.remove("hidden");
}

function closeHowto(): void {
  howtoPanel.classList.add("hidden");
  menu.classList.remove("hidden");
}

function initHpMenu(): void {
  const grid = $("hp-grid");
  for (const name of PIECE_NAMES) {
    const label = document.createElement("label");
    label.textContent = name;
    label.htmlFor = `hp-${name}`;
    const input = document.createElement("input");
    Object.assign(input, { type: "number", id: label.htmlFor, min: HP_MIN, max: HP_MAX, step: 10 });
    input.inputMode = "numeric";
    input.addEventListener("change", () => {
      const v = Math.round(Number(input.value));
      if (Number.isFinite(v)) settings.hp[name] = Math.min(HP_MAX, Math.max(HP_MIN, v));
      input.value = String(settings.hp[name]);
      saveSettings();
    });
    grid.append(label, input);
    hpInputs.set(name, input);
  }
  $("hp-reset").addEventListener("click", () => {
    settings.hp = { ...HP_MAP };
    renderMenu();
  });
}

function showMenu(): void {
  game = null;
  setPlaying(false);
  closeEditor();
  gameOverPanel.classList.add("hidden");
  menu.classList.remove("hidden");
  renderMenu();
}

// --- Board editor ------------------------------------------------------------

function makePiece(s: PieceSpec): Piece {
  const p = new Piece(s.color, s.name, s.col, s.row, settings.hp[s.name]);
  // Pawns placed off their home rank have no double step.
  if (s.name === "Pawn") p.hasMoved = s.row !== (s.color === "white" ? BOARD - 2 : 1);
  return p;
}

function renderPalette(): void {
  const palette = $("palette");
  palette.replaceChildren();
  const add = (b: Brush, el: Node, title: string) => {
    const btn = document.createElement("button");
    btn.title = title;
    btn.append(el);
    btn.classList.toggle("active", JSON.stringify(b) === JSON.stringify(brush));
    btn.addEventListener("click", () => { brush = b; renderPalette(); });
    palette.append(btn);
  };
  for (const color of ["white", "black"] as const) {
    for (const name of PIECE_NAMES) {
      const img = document.createElement("img");
      img.src = `pieces/${settings.pieceSet}/${name}/${color}.svg`;
      img.alt = "";
      add({ color, name }, img, `${color} ${name}`);
    }
    if (color === "white") add("erase", document.createTextNode("\u2715"), "Erase");
  }
}

function openEditor(): void {
  game = null;
  setPlaying(false);
  menu.classList.add("hidden");
  gameOverPanel.classList.add("hidden");
  editorPanel.classList.remove("hidden");
  editorPieces = sandboxLayout.length > 0 ? sandboxLayout.map(makePiece) : createPieces(settings.hp);
  renderPalette();
}

function closeEditor(): void {
  editorPieces = null;
  editorPanel.classList.add("hidden");
}

function editorClick(col: number, row: number, erase: boolean): void {
  if (!editorPieces) return;
  editorPieces = editorPieces.filter((p) => p.col !== col || p.row !== row);
  if (!erase && brush !== "erase") editorPieces.push(makePiece({ ...brush, col, row }));
}

function initEditor(): void {
  if (!SANDBOX) return;
  const btn = $("sandbox-btn");
  btn.classList.remove("hidden");
  btn.addEventListener("click", openEditor);
  $("ed-clear").addEventListener("click", () => { editorPieces = []; });
  $("ed-standard").addEventListener("click", () => { editorPieces = createPieces(settings.hp); });
  $("ed-menu").addEventListener("click", showMenu);
  $("ed-link").addEventListener("click", () => {
    if (!editorPieces) return;
    const url = new URL(location.pathname, location.origin);
    url.searchParams.set("sandbox", "");
    url.searchParams.set("setup", toFen(editorPieces));
    history.replaceState(null, "", url);
    const btn = $("ed-link");
    const flash = (msg: string) => {
      btn.textContent = msg;
      setTimeout(() => { btn.textContent = "Copy link"; }, 1500);
    };
    if (!navigator.clipboard) flash("In address bar");
    else navigator.clipboard.writeText(url.href).then(() => flash("Copied!"), () => flash("In address bar"));
  });
  $("ed-play").addEventListener("click", () => {
    if (!editorPieces) return;
    sandboxLayout = editorPieces.map((p) => ({ color: p.color, name: p.name, col: p.col, row: p.row }));
    closeEditor();
    void requestGame(sandboxLayout);
  });
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
  document.querySelectorAll<HTMLButtonElement>("#set-buttons button").forEach((b) => {
    b.addEventListener("click", () => {
      settings.pieceSet = b.dataset.set as PieceSet;
      renderMenu();
    });
  });
  document.querySelectorAll<HTMLButtonElement>("#promo-mode button").forEach((b) => {
    b.addEventListener("click", () => {
      settings.promotion = b.dataset.promo as Settings["promotion"];
      renderMenu();
    });
  });
  document.querySelectorAll<HTMLButtonElement>("#guard-mode button").forEach((b) => {
    b.addEventListener("click", () => {
      settings.guard = b.dataset.guard === "on";
      renderMenu();
    });
  });
  document.querySelectorAll<HTMLButtonElement>("#sound-mode button").forEach((b) => {
    b.addEventListener("click", () => {
      settings.sound = b.dataset.sound === "on";
      renderMenu();
      unlockAudio();
      sfx.move();
    });
  });
  $("options-btn").addEventListener("click", openOptions);
  $("options-back").addEventListener("click", closeOptions);
  $("howto-btn").addEventListener("click", openHowto);
  $("howto-back").addEventListener("click", closeHowto);
  $("start").addEventListener("click", () => void requestGame());
  $("again").addEventListener("click", () => (game?.sandbox ? openEditor() : showMenu()));
  loadSettings();
  initHpMenu();
  initEditor();
  renderMenu();
}

// --- Game lifecycle ----------------------------------------------------------

function startGame(layout: PieceSpec[] | null = null): void {
  if (!images) return;
  unlockAudio();
  const sandbox = layout !== null;
  const moveInterval = SPEED_PRESETS[settings.speed];
  setPieceSpeed((BASE_PIECE_SPEED * SPEED_PRESETS.fast) / moveInterval);
  Piece.attackCounter = 0;

  // Difficulty 0 means the AI is disabled.
  const aiEnabled = !sandbox && settings.aiEnabled && settings.difficulty > 0;
  let ai: AIController | null = null;
  if (aiEnabled) {
    ai = new AIController("black", settings.difficulty, brain ? new NNPolicy(brain) : null);
    // Same cadence as the human; difficulty controls skill, not speed.
    ai.actionsPerSecond = 1.0 / moveInterval;
  }

  const cooldownMs = sandbox ? 0 : Math.trunc(moveInterval * 1000);
  const readyAt = performance.now() - cooldownMs;
  game = {
    pieces: layout ? layout.map(makePiece) : createPieces(settings.hp),
    ai,
    myColor: aiEnabled ? "white" : null,
    selected: null,
    legalTargets: [],
    gameOver: false,
    winner: null,
    cooldownMs,
    lastActionMs: { white: readyAt, black: readyAt },
    whiteStarted: sandbox,
    sandbox,
  };
  menu.classList.add("hidden");
  gameOverPanel.classList.add("hidden");
  setPlaying(true);
}

function endGame(g: Game, winner: string): void {
  if (g.gameOver) return;
  g.gameOver = true;
  g.winner = winner;
  setPlaying(false);
  const humanLost = g.myColor !== null && winner.toLowerCase() !== g.myColor;
  (humanLost ? sfx.lose : sfx.win)();
  if (g.ai && !humanLost) portal.happyTime();
  $("winner-text").textContent = `${winner} wins!`;
  // Let the King's death animation play before covering the board.
  setTimeout(() => {
    if (game === g) gameOverPanel.classList.remove("hidden");
  }, DEATH_MS);
}

// --- Input -------------------------------------------------------------------

function deselect(g: Game): void {
  g.selected = null;
  g.legalTargets = [];
}

/** Pawns on the far rank waiting for the player to pick a piece (AI pawns never wait). */
function pendingPromotions(g: Game): Piece[] {
  if (settings.promotion !== "choose") return [];
  return pawnsToPromote(g.pieces).filter((p) => !g.ai || p.color !== g.ai.color);
}

function handleClick(g: Game, mx: number, my: number, stopRadius: number): void {
  const choice = promotionChoiceAt(pendingPromotions(g), mx, my);
  if (choice) {
    const [pawn, name] = choice;
    if (g.myColor === null || pawn.color === g.myColor) {
      pawn.promote(name, settings.hp[name]);
      sfx.promote();
    }
    return;
  }

  // Stop buttons first.
  for (const p of g.pieces) {
    if (p.stopBtnHit(mx, my, stopRadius)) {
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
    if (g.cooldownMs && now - g.lastActionMs[sel.color] < g.cooldownMs) return;
    g.lastActionMs[sel.color] = now;
    sel.startMove(col, row);
    sfx.move();
    deselect(g);
  } else if (clicked) {
    g.selected = clicked;
    g.legalTargets = getLegalTargets(clicked, g.pieces);
  } else {
    deselect(g);
  }
}

canvas.addEventListener("pointerdown", (e) => {
  const rect = canvas.getBoundingClientRect();
  const mx = ((e.clientX - rect.left) * WIDTH) / rect.width;
  const my = ((e.clientY - rect.top) * HEIGHT) / rect.height;
  if (editorPieces) {
    const col = Math.floor(mx / TILE);
    const row = Math.floor(my / TILE);
    if (inBounds(col, row)) editorClick(col, row, e.button === 2);
    return;
  }
  if (!game || game.gameOver || e.button !== 0) return;
  unlockAudio();
  // Keep the stop button at least ~22 CSS px to tap when the board is scaled down (phones).
  const stopRadius = Math.min(30, Math.max(STOP_BTN_RADIUS, (22 * WIDTH) / rect.width));
  handleClick(game, mx, my, stopRadius);
});

canvas.addEventListener("contextmenu", (e) => {
  if (editorPieces) e.preventDefault();
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !optionsPanel.classList.contains("hidden")) closeOptions();
  else if (e.key === "Escape" && !howtoPanel.classList.contains("hidden")) closeHowto();
  else if (e.key === "Escape" && game?.sandbox) openEditor();
  else if (e.key === "Escape" && (game || editorPieces)) showMenu();
  else if (e.key === "Enter" && !game && !editorPieces && !menu.classList.contains("hidden")) {
    // Blur fires the input's change event so a just-typed HP value is applied.
    if (document.activeElement instanceof HTMLInputElement) document.activeElement.blur();
    void requestGame();
  }
});

window.addEventListener("resize", resizeCanvas);

// --- Main loop ---------------------------------------------------------------

function simulate(g: Game, dt: number): void {
  if (!g.whiteStarted && g.pieces.some((p) => p.color === "white" && p.moving)) {
    g.whiteStarted = true;
  }
  if (g.ai && g.whiteStarted) g.ai.update(dt, g.pieces);

  // Combat before movement so damage applies until full arrival.
  const aliveBefore = g.pieces.filter((p) => p.alive).length;
  processCombat(g.pieces, dt, settings.guard);
  if (g.pieces.filter((p) => p.alive).length < aliveBefore) sfx.death();
  else if (g.pieces.some((p) => p.beingAttacked)) sfx.hit();
  for (const p of g.pieces) p.update(dt, g.pieces);
  const waiting = pendingPromotions(g);
  for (const p of pawnsToPromote(g.pieces)) {
    if (waiting.includes(p)) continue;
    p.promote("Queen", settings.hp.Queen);
    sfx.promote();
  }

  for (const p of g.pieces) {
    if (p.name === "King" && !p.alive) endGame(g, p.color === "white" ? "Black" : "White");
  }
  if (g.selected && (!g.selected.alive || g.selected.moving)) deselect(g);
  // The board keeps changing, so the shown (and clickable) targets must too.
  if (g.selected) g.legalTargets = getLegalTargets(g.selected, g.pieces);
}

function render(now: number): void {
  drawBoard(ctx);
  if (!images) return;
  const imgs = images[settings.pieceSet];

  if (editorPieces) {
    for (const p of editorPieces) drawPiece(ctx, p, imgs, now);
    if (settings.guard) drawGuards(ctx, editorPieces);
    const count = (c: Color) => editorPieces!.filter((p) => p.color === c).length;
    drawStatus(ctx, {
      text: `Board editor: ${count("white")} white, ${count("black")} black`,
      textColor: "rgb(220,220,220)",
      meters: [],
    });
    return;
  }

  if (!game) return;
  const g = game;
  drawHighlights(ctx, g.selected, g.legalTargets, g.pieces);
  for (const p of g.pieces) drawPiece(ctx, p, imgs, now);
  if (settings.guard) drawGuards(ctx, g.pieces);
  drawDeaths(ctx, g.pieces, imgs, now);
  drawAttackDots(ctx, g.selected, g.legalTargets, g.pieces);
  const waiting = g.gameOver ? [] : pendingPromotions(g);
  drawPromotionChoices(ctx, waiting, imgs, now);

  let text = g.sandbox ? "Sandbox: move either side. Esc = editor." : "Select a piece, then a target.";
  let textColor = "rgb(180,180,180)";
  if (g.gameOver) {
    text = `${g.winner} wins!`;
    textColor = "rgb(255,255,100)";
  } else if (g.selected) {
    text = `Selected: ${g.selected.color} ${g.selected.name}`;
    textColor = "rgb(220,220,220)";
  } else if (waiting.length > 0) {
    text = "Promote: pick a piece on the pawn's square.";
    textColor = "rgb(246,201,69)";
  } else if (!g.whiteStarted) {
    text = "White moves first.";
  }

  const colors: Color[] = g.myColor ? [g.myColor] : ["white", "black"];
  drawStatus(ctx, {
    text,
    textColor,
    meters: g.cooldownMs && !g.gameOver
      ? colors.map((c) => {
        const elapsed = now - g.lastActionMs[c];
        return {
          label: g.myColor ? null : (c === "white" ? "White" : "Black"),
          frac: Math.max(0, Math.min(1, elapsed / g.cooldownMs)),
          left: (g.cooldownMs - elapsed) / 1000,
        };
      })
      : [],
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
  if (portal.name !== "web") $("opp-online").classList.add("hidden");
  // A blocked or failing portal SDK must never stop the game from loading.
  await portal.init({
    pauseAudio: () => setAdPlaying(true),
    resumeAudio: () => setAdPlaying(false),
    setForcedMute: setPortalMuted,
  }).catch((e) => console.warn("Portal SDK unavailable", e));
  const [war, classic, b] = await Promise.all([
    loadPieceImages("war"), loadPieceImages("classic"), loadBrain("brain.json"),
  ]);
  images = { war, classic };
  brain = b;
  startBtn.disabled = false;
  portal.loadingDone();
  if (SANDBOX && SHARED_SETUP) {
    sandboxLayout = SHARED_SETUP;
    openEditor();
  }
  requestAnimationFrame(frame);
}

boot().catch((err) => {
  console.error(err);
  $("start").textContent = "Failed to load assets";
});
