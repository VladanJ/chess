# Real-Time Chess

A real-time strategy board game that plays like chess — but with no turns. Both players move simultaneously, pieces have hit points, and combat happens on contact. The game ends when a King is destroyed.

## Requirements

- Python 3.8+
- Pygame (`pip install pygame`)

## Quick Start

```bash
# Local hotseat (both players on one machine)
python ChessGame.py

# Play against the built-in AI (you are white, AI is black)
python ChessGame.py --ai --difficulty 8

# Online — Player 1 hosts (white)
python ChessGame.py --host

# Online — Player 2 joins (black)
python ChessGame.py --join 192.168.1.X
```

## How to Play

1. **Select** a piece by clicking it.
2. **Grey dots** show where you can move. **Red dots** show attackable enemies.
3. **Click a target** to send the piece there. It slides tile by tile in real time.
4. **Stop** a moving piece by clicking the red X button on its top-right corner.
5. **No turns** — move any of your pieces at any time, as many as you want.
6. **Move cooldown** — you can only *commit* a move every few seconds (the
   game-speed cadence). An on-screen meter shows `READY` or a countdown;
   selecting and inspecting pieces is always free.

### Combat

- When a piece reaches an enemy, it stops and **deals damage** automatically.
- Only the **defender** (the piece being moved into) takes damage — unless both pieces attack each other simultaneously.
- Damage rate: **10 HP/sec** for all pieces.
- A piece is destroyed when its HP reaches 0.

### Piece HP

| Piece | HP |
|---|---|
| Pawn | 100 |
| Knight | 300 |
| Bishop | 300 |
| Rook | 500 |
| Queen | 1000 |
| King | 100 |

### Pawn Rules

- Pawns move forward but can only **attack diagonally**.
- Moving forward into an enemy deals **no damage** — the pawn just stops.
- Diagonal captures appear as red dots only when an enemy is on that tile.

### Win Condition

Destroy the opponent's **King** (reduce to 0 HP). The game displays the winner and you can press ESC to quit.

## Single-Player vs AI

Play against a computer opponent that controls the black army.

```bash
python ChessGame.py --ai --difficulty 8 --brain ai_brain.pt --speed medium
```

| Flag | Default | Description |
|---|---|---|
| `--ai` | off | Enable the AI opponent (local play only) |
| `--difficulty 0-10` | 5 | AI **skill** (higher = fewer random moves). 0 disables the AI |
| `--brain PATH` | `ai_brain.pt` | Trained neural-net brain; falls back to the heuristic if missing |
| `--speed fast\|medium\|slow` | medium | Move cadence: 1 s / 3 s / 5 s between moves (also scales piece speed) |

- If a trained brain (`ai_brain.pt`) is present it is loaded automatically;
  otherwise the AI uses a hand-written heuristic.
- In local play these flags only **seed the in-game settings menu** — your
  final picks there take effect.
- The AI moves at the same cadence as you; difficulty changes *how well* it
  plays, not how fast.

The AI is trained by evolutionary self-play (`train.py`) and benchmarked with
`eval.py`. The trained champion beats the heuristic at maximum difficulty about
**91%** of the time. See the [documentation](docs/README.md) for a full,
engineer-level write-up of the neural network and the training pipeline.

## Online Play

The host runs the game simulation. The client sends commands and receives state updates.

| Flag | Role | Color |
|---|---|---|
| `--host` | Server (authoritative) | White |
| `--join <IP>` | Client (display-only) | Black |

- Default port: **5555**
- Each player can only control their own color.
- Status bar shows "Disconnected!" if the connection drops.

## Controls

| Input | Action |
|---|---|
| Left click piece | Select it |
| Left click target | Move selected piece there |
| Left click red X | Stop a moving piece |
| ESC | Quit |

## Project Structure

```
chess/
├── ChessGame.py       # Game logic, rendering, main loop
├── ai.py              # Heuristic AI controller (torch-free)
├── brain.py           # Neural-net move policy (PyTorch)
├── train.py           # Evolutionary self-play trainer (PyTorch)
├── eval.py            # Benchmark: trained brain vs heuristic (PyTorch)
├── network.py         # TCP server/client for online play
├── ai_brain.pt        # Trained champion brain (auto-loaded by --ai)
├── ai_brain_91.pt     # Backup of the 91%-vs-heuristic champion
├── ARCHITECTURE.md    # Technical architecture documentation
├── README.md          # This file
├── docs/              # Long-form documentation (game + neural network + ML)
└── pieces/            # Piece images (black.png, white.png per piece)
    ├── Bishop/
    ├── King/
    ├── Knight/
    ├── Pawn/
    ├── Queen/
    └── Rook/
```

## Documentation

- [docs/](docs/README.md) — a short technical book: project overview, a deep
  dive on the **neural network** (architecture, weights, visualisations), and
  the **machine-learning** training pipeline.
- [ARCHITECTURE.md](ARCHITECTURE.md) — game internals (pieces, movement, combat).

## Configuration

Edit constants at the top of `ChessGame.py`:

| Constant | Default | Description |
|---|---|---|
| `BASE_PIECE_SPEED` | 0.3 | Piece speed (tiles/sec) at the fastest cadence; scaled by game speed |
| `SPEED_PRESETS` | fast 1s / medium 3s / slow 5s | Seconds between moves per game-speed preset |
| `DAMAGE_PER_SECOND` | 10 | HP removed per second during combat |
| `FPS` | 60 | Frame rate cap |
