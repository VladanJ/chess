# Generation Prompt — Real-Time Chess

Use this prompt to regenerate the complete software from scratch.

---

## Project Overview

Write a **real-time strategy (RTS) board game** in Python using Pygame. It looks like chess and is played on a standard 8×8 board with alternating light `(240, 217, 181)` and dark `(181, 136, 99)` tiles, each 100×100 pixels. The window is 800×840 (800 for the board, 40 for a status bar at the bottom). Two players control white and black pieces respectively. There are **no turns** — all pieces can move simultaneously in real time.

The game supports three modes via command-line arguments:
- **Local** (no args): Both colors on one machine, hotseat play.
- **Host** (`--host`): You play white. The game listens on TCP port 5555, waits for one client to connect, then starts.
- **Join** (`--join <IP>`): You play black. Connect to the host's IP on port 5555.

---

## File Structure

Create two Python files:

```
ChessGame.py     — All game logic, rendering, and the main loop
network.py       — TCP networking: Server class, Client class, serialisation
```

Piece images are pre-existing in a `pieces/` folder:
```
pieces/Bishop/black.png, white.png
pieces/King/black.png, white.png
pieces/Knight/black.png, white.png
pieces/Pawn/black.png, white.png
pieces/Queen/black.png, white.png
pieces/Rook/black.png, white.png
```

Load all images at startup and scale to 100×100.

---

## Pieces

Standard chess setup. Back rank order: Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook. Black on rows 0–1, white on rows 6–7.

Each piece has HP:

| Piece | HP |
|---|---|
| Pawn | 100 |
| Knight | 300 |
| Bishop | 300 |
| Rook | 500 |
| Queen | 1000 |
| King | 5000 |

A piece dies when HP reaches 0. The game ends when a King dies — the opposite color wins.

---

## Movement

All pieces move at **0.3 tiles per second** (uniform speed, configurable via `PIECE_SPEED`).

### Tile-by-tile Waypoints (all pieces except Knight)

When a piece is told to move, compute a list of waypoints (one per tile) from the current position to the target. The piece slides smoothly tile by tile. Each frame, move `pixel_x/y` toward the next waypoint. When the pixel position reaches the waypoint, update the logical `col/row` and advance `path_index` to the next waypoint.

Movement follows chess rules for legal targets:
- **Pawn**: Forward 1 (or 2 from start row if not yet moved). Diagonal captures only if an enemy occupies that tile (on its `col/row` or as its `next_tile` while mid-slide). Pawns moving forward deal **0 damage** — they can only deal damage diagonally.
- **Knight**: L-shape (8 possible squares).
- **Bishop**: Diagonal slides.
- **Rook**: Orthogonal slides.
- **Queen**: Diagonal + orthogonal slides.
- **King**: One step in any direction.

### Knight Animation

Knights use a **simultaneous crossfade**: the sprite at the origin fades out (alpha 255→0) while a copy at the destination fades in (alpha 0→255), both over `3.0 / PIECE_SPEED` seconds. After the crossfade completes, check for friendly blocker (snap back), enemy (enter waiting), or clear (arrive).

During the "waiting" phase the knight is invisible — only the red attack arrow shows.

### Friendly Blocking

Before any pixel movement each frame, check `_get_blocker()`: if a same-color piece occupies the next waypoint tile (on its `col/row` or as its `next_tile`), **cancel the move entirely** and snap back to the current logical tile.

A tile is also considered blocked for move generation if a friendly piece has it as `col/row`, `target_col/row`, or `next_tile`.

### Enemy Detection

- `_get_enemy_on_tile(col, row)`: Returns an alive enemy whose `col/row` matches OR whose `next_tile` matches.
- `_get_stationary_enemy(col, row)`: Returns only non-moving enemies whose `col/row` matches.

When a non-pawn encounters an enemy on its next waypoint, it **stops on its current tile** (snaps pixel position to tile center), sets `waiting = True`, and stores `attack_target`. It stays there dealing damage until the enemy dies or leaves.

### Pawn-Specific Movement Rules

1. **Forward movement**: Pawns moving forward (same column) only stop for **stationary** enemies. If an enemy is moving through the forward tile, the pawn keeps sliding and takes damage (but deals none forward).
2. **Forward blocking also checks `next_tile`**: `_pawn_path_clear()` uses `include_next=True` when checking if the forward tile is occupied, so a pawn can't move forward if any piece's `next_tile` is that square.
3. **Diagonal attack**: When a pawn waits diagonally on an enemy and the enemy survives and leaves, the pawn **cancels** — it stays on its current tile and stops, rather than moving diagonally to the now-empty tile.
4. **0 forward damage**: `process_combat()` skips any pawn whose `next_tile` is in the same column as itself.

### Head-On Collision (Mutual Combat)

If two enemy pieces are heading toward each other (piece A's `next_tile` is piece B's `current_tile` and vice versa), both remain in place dealing damage simultaneously until one dies. The survivor then proceeds.

Pawns moving forward (same column) are **exempt** from the head-on lock — they keep sliding instead.

### Damage Continuation

If a defender starts fleeing (becomes `moving`), the attacker continues dealing damage as long as the defender's `col/row` hasn't actually changed (i.e., the defender is still physically on that tile mid-slide). Only when the defender reaches its next tile and `col/row` update does damage stop.

### Stop Button

Every moving piece shows a small red circle (radius 10) with a white X in its top-right corner. Clicking it calls `stop()`, which snaps the piece to its current logical tile and cancels all movement/attack state.

---

## Combat System

`process_combat()` runs **before** movement updates each frame (so damage applies on the frame a defender finishes its slide).

```
for each alive, moving attacker:
    target_tile = attacker.next_tile
    skip if None
    skip if attacker is Pawn and target_tile column == attacker column
    for each alive enemy defender:
        defender_tiles = {current_tile}
        if defender is moving and has next_tile: add next_tile
        if target_tile in defender_tiles:
            defender.hp -= DAMAGE_PER_SECOND * dt
            if hp <= 0: kill defender
```

Damage is **one-directional per attacker**: only the defender takes damage. In mutual combat, both act as attacker AND defender simultaneously (each deals damage to the other).

---

## Visual Indicators

### Selection
- Click a stationary piece to select it. Green overlay on the selected tile.
- **Grey dots** on legal empty-tile targets (circle radius 15, color `(100, 100, 100, 160)`).
- **Red dots** on legal targets where an enemy is present (circle radius 18, color `(220, 30, 30, 200)`). Rendered **on top of pieces**. Enemy presence checked on both `col/row` and `next_tile`.
- Clicking the same piece again re-evaluates legal targets.

### Movement Arrows
- **Blue arrow** from origin tile center to target tile center while a piece is sliding (not waiting).
- **Red arrow** from piece's current tile center to enemy's tile center while a piece is waiting/attacking.
- Both arrows have arrowheads (14 px lines).

### HP Bar
- Drawn at the bottom of each piece's tile (width = TILE-10, height = 6).
- Green (>50%), yellow (>25%), red (≤25%).
- Dark grey background, black border.

### Status Bar
- 40 px tall, dark background, below the board.
- Shows "Selected: {color} {name}" when a piece is selected.
- Shows "{Winner} wins! Press ESC to quit." on game over.
- Shows "Disconnected!" in red when a network connection drops.
- Shows default hint text when nothing is selected.

---

## Input Handling

1. Check if a stop button was clicked (iterate pieces; in network mode only own-color pieces).
2. Check if click is in board bounds.
3. Check if a stationary piece is under the click. In network mode, ignore opponent's pieces.
4. If the clicked piece is own-color → select it (re-evaluate legal targets).
5. If a piece is selected and the click is on a legal target → start move (or send move command over network if client).
6. Otherwise deselect.

---

## Networking (`network.py`)

### Protocol

Length-prefixed JSON over TCP:
```
[4 bytes big-endian uint32: payload length][UTF-8 JSON payload]
```
Max message size: 10 MB sanity cap.

### Server Class

- Binds on `0.0.0.0:5555`, listens for one client.
- `wait_for_client()` blocks until connected, then starts a daemon receiver thread.
- Receiver thread reads messages into a thread-safe list (protected by `threading.Lock`).
- `get_messages()` returns and clears the queue.
- `send_state(pieces, game_over, winner)` serialises all pieces to dicts and sends a `{"type": "state", ...}` message.
- Server validates client commands: only accepts `move` and `stop` for black pieces.

### Client Class

- Connects to `host:5555`, starts a daemon receiver thread.
- `send_move(piece_index, target_col, target_row)` sends `{"type": "move", ...}`.
- `send_stop(piece_index)` sends `{"type": "stop", ...}`.
- `get_messages()` returns and clears incoming state messages.

### Serialisation

`piece_to_dict(p)` serialises all piece fields: color, name, col, row, hp, max_hp, alive, moving, target_col/row, pixel_x/y, origin_col/row, knight_phase, knight_alpha, knight_dest_alpha, knight_timer, knight_duration, path, path_index, waiting, has_moved.

`apply_state(pieces, state_list)` overwrites all fields of each `Piece` from the server snapshot. `attack_target` is set to `None` (not serialisable; server handles combat).

### Authority Model

The **server is authoritative**: it runs the full simulation (movement, combat, game-over). The **client is display-only**: it sends input commands and receives full state snapshots at 20 Hz. The client does no local simulation — it renders the last received state at 60 FPS.

### State Sync

The server sends full state every 50 ms (20 Hz), tracked by a `sync_timer` that accumulates `dt`.

### Disconnection

Both `Server` and `Client` detect disconnection via failed `recv()` or `send()` calls (setting `connected = False`). Status bar shows "Disconnected!" when detected.

---

## Game Loop Order

### Server / Local

1. Receive network messages (server: process client move/stop commands)
2. Process Pygame events (mouse clicks → select, move, stop)
3. `process_combat(pieces, dt)` — apply damage
4. `piece.update(dt, pieces)` for all pieces — advance movement
5. Check game over (any King with HP ≤ 0)
6. Deselect piece if it died or started moving
7. Send state snapshot (server only, 20 Hz)
8. Draw: board → highlights → pieces → attack dots → status bar
9. `pygame.display.flip()`

### Client

1. Receive state snapshots → `apply_state()` overwrites all piece fields, game_over, winner
2. Process Pygame events (mouse clicks → send move/stop commands to server)
3. No local simulation
4. Draw from last received state
5. `pygame.display.flip()`

---

## Board Colours

```python
LIGHT_COLOR = (240, 217, 181)
DARK_COLOR  = (181, 136, 99)
HIGHLIGHT_COLOR = (186, 202, 68, 150)   # green selection overlay
MOVE_DOT_COLOR  = (100, 100, 100, 160)  # grey legal-move dot
ATTACK_DOT_COLOR = (220, 30, 30, 200)   # red attack dot
```

---

## Key Implementation Details

- Frame rate is 60 FPS. `dt` = `clock.tick(60) / 1000.0`.
- `PIECE_SPEED = 0.3` tiles/sec. Pixel step per frame = `PIECE_SPEED * TILE * dt`.
- `DAMAGE_PER_SECOND = 10`. Damage per frame = `DAMAGE_PER_SECOND * dt`.
- Tile size `TILE = 100` pixels.
- Use `argparse` for CLI: `--host` (store_true), `--join IP` (str).
- Network imports are conditional (`from network import Server/Client/apply_state` only when needed).
- `pieces` list order: 8 black back-rank, 8 black pawns, 8 white pawns, 8 white back-rank (32 total). This order is stable and used as indices for network commands.
- ESC key quits the game.
- Font: `consolas`, size 22.
