# Real-Time Chess

A real-time strategy board game that plays like chess — but with no turns. Both players move simultaneously, pieces have hit points, and combat happens on contact. The game ends when a King is destroyed.

## Requirements

- Python 3.8+
- Pygame (`pip install pygame`)

## Quick Start

```bash
# Local hotseat (both players on one machine)
python ChessGame.py

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
| King | 5000 |

### Pawn Rules

- Pawns move forward but can only **attack diagonally**.
- Moving forward into an enemy deals **no damage** — the pawn just stops.
- Diagonal captures appear as red dots only when an enemy is on that tile.

### Win Condition

Destroy the opponent's **King** (reduce to 0 HP). The game displays the winner and you can press ESC to quit.

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
├── network.py         # TCP server/client for online play
├── ARCHITECTURE.md    # Technical architecture documentation
├── prompt.md          # Full generation prompt
├── README.md          # This file
└── pieces/            # Piece images (black.png, white.png per piece)
    ├── Bishop/
    ├── King/
    ├── Knight/
    ├── Pawn/
    ├── Queen/
    └── Rook/
```

## Configuration

Edit constants at the top of `ChessGame.py`:

| Constant | Default | Description |
|---|---|---|
| `PIECE_SPEED` | 0.3 | Tiles per second (all pieces) |
| `DAMAGE_PER_SECOND` | 10 | HP removed per second during combat |
| `FPS` | 60 | Frame rate cap |
