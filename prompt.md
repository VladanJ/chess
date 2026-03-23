# Prompt: Generate a Real-Time Chess Game in Python

Write a complete real-time strategy (RTS) chess game in Python using Pygame. Put all code in a single file called `ChessGame.py`. The game is played on an 8×8 board with 100×100 pixel tiles, for two players (white and black). There are no turns — both players can move any of their pieces at any time, simultaneously.

---

## Board & Setup

- Draw an 8×8 chessboard with alternating light `(240, 217, 181)` and dark `(181, 136, 99)` tiles, each 100×100 pixels.
- Below the board, add a 40-pixel-tall status bar with a dark background `(30, 30, 30)` showing the currently selected piece or a game-over message.
- Place pieces in the standard chess starting position: back rank (Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook) and a row of pawns for each side. Black on rows 0–1, white on rows 6–7.
- Load piece images from a `pieces/` folder structured as `pieces/{PieceName}/{color}.png` (e.g., `pieces/Bishop/black.png`, `pieces/King/white.png`). Scale each image to 100×100 pixels.

---

## Health System

Each piece has a health bar displayed at the bottom of its tile (90px wide, 6px tall, with a 1px black border). The bar changes color based on remaining HP: green (>50%), yellow (>25%), red (≤25%).

HP values:
- Pawn: 100 HP
- Knight: 300 HP
- Bishop: 300 HP
- Rook: 500 HP
- Queen: 1000 HP
- King: 5000 HP

When a piece reaches 0 HP, it is removed from the board. The game ends when either king reaches 0 HP — display "{Color} wins!" in the status bar.

---

## Movement

All pieces move according to chess rules. Every piece moves at the same speed: **0.2 tiles per second**. Movement is slow and deliberate.

### Sliding Pieces (Pawn, Bishop, Rook, Queen, King)

Movement is **translatory** (smooth pixel interpolation). When a piece is ordered to move, compute the full path as a list of tile-by-tile waypoints from origin to destination. The piece slides through each waypoint one at a time. **As soon as a piece finishes crossing a tile, that tile is freed** — other pieces can immediately use it.

**Before moving any pixels toward the next waypoint**, check if that tile is occupied:
- If occupied by a **friendly** piece → cancel the entire move, snap back to the current tile.
- If occupied by an **enemy** piece → the piece does NOT move toward that tile. Instead, it stays centered on its own tile and enters a **waiting/attacking** state (see Combat below).
- **Pawns blocked forward by any piece** (same column) → always cancel, never attack forward. Pawns can only attack diagonally.

### Knight

The knight uses a **simultaneous crossfade** animation instead of sliding. When moving:
1. A fading-out copy is drawn at the origin tile (alpha 255→0) while simultaneously a fading-in copy appears at the destination tile (alpha 0→255). Both copies are visible at the same time during the transition.
2. The total crossfade duration matches what other pieces would take to travel 3 tiles at 0.2 tiles/sec.
3. At the end of the crossfade:
   - If the target is empty → the knight arrives normally.
   - If the target has an enemy → enter waiting/attacking state (knight becomes invisible, damage is dealt, a red arrow is drawn).
   - If the target has a friendly piece → snap back to origin, cancel.
4. While waiting for an enemy to die/move, once the target clears, the knight teleports to the destination and finishes the move.

### Pawn Special Rules

- Can move forward 1 tile (or 2 tiles from the starting row if it hasn't moved yet). Forward moves are only allowed if the target tile is completely empty (no piece of either color).
- Can move diagonally forward by 1 tile **only if** an enemy piece occupies that diagonal tile.
- If a pawn attacks diagonally and the defender **survives** (moves away with HP > 0), the pawn does **not** proceed diagonally — it stays on its current tile (the attack was unsuccessful, no capture).
- If the defender **dies** (HP reaches 0), the pawn proceeds to occupy the diagonal tile (successful capture).
- A pawn blocked forward by an enemy does NOT attack — it simply stops. Pawns only attack diagonally.

---

## Combat

**One-directional damage only** — the attacking piece is never harmed.

When a moving piece's next waypoint tile is occupied by an enemy, the attacker stays on its own tile and the **defender** takes 10 HP of damage per second. This continues every frame (`10 × dt` per frame) until:
- The defender dies (HP ≤ 0) → removed from the board, attacker proceeds to occupy the tile.
- The defender moves away → tile is free (but for pawns attacking diagonally, if the defender survived, the pawn cancels instead of proceeding).

No two pieces can ever overlap or occupy the same tile.

---

## Visual Indicators

### Selection Highlights
- When a piece is selected, draw a semi-transparent green overlay `(186, 202, 68, 150)` on its tile.
- Show **grey dots** `(100, 100, 100, 160)` (radius 15) on empty tiles the piece can move to.
- Show **red dots** `(220, 30, 30, 200)` (radius 18) **rendered on top of enemy pieces** that can be attacked. These must be drawn after pieces so they appear over the piece images.

### Movement Arrow
- While a piece is moving (not in attack/waiting state), draw a **blue arrow** `(40, 100, 220)` from the center of the origin tile to the center of the target tile, with an arrowhead.

### Attack Arrow
- While a piece is in the waiting/attacking state, draw a **red arrow** `(220, 30, 30)` from the center of the attacker's tile to the center of the defender's tile, with an arrowhead.

### Stop Button
- Every moving piece displays a small **red circle** (radius 10) with a **white X** in its top-right corner.
- Clicking the stop button immediately halts the piece — it snaps to its current logical tile, cancels all movement and attack state.

---

## Input Handling

All input is mouse-driven (left-click only):

1. **Stop button** — checked first on every click. If a moving piece's stop button is hit, stop that piece.
2. **Clicking a friendly piece** — always (re)selects it and **reevaluates legal moves** from the current board state. This applies even if the same piece is clicked again.
3. **Clicking a legal target tile** — initiates movement toward that tile.
4. **Clicking an empty non-target tile** — deselects the current piece.
5. **ESC key** — quits the game.

---

## Rendering Order

Each frame, draw in this exact order:
1. Board tiles (8×8 grid)
2. Selection highlights and grey move dots (under pieces)
3. All alive pieces (images, health bars, blue/red arrows, stop buttons)
4. Red attack dots over capturable enemy pieces (on top of piece images)
5. Status bar text

---

## Technical Details

- Use `pygame` as the only external dependency.
- Frame rate capped at 60 FPS. Use `clock.tick(FPS) / 1000.0` for delta time.
- Window size: 800×840 pixels (800 for the board + 40 for the status bar).
- Use `pygame.font.SysFont("consolas", 22)` for status bar text.
- All images loaded with `convert_alpha()` and scaled with `smoothscale()`.
- The game loop runs continuously: handle events → update movement → process combat → check game over → draw.

---

## Folder Structure

```
chess/
  ChessGame.py
  pieces/
    Bishop/   black.png  white.png
    King/     black.png  white.png
    Knight/   black.png  white.png
    Pawn/     black.png  white.png
    Queen/    black.png  white.png
    Rook/     black.png  white.png
```
