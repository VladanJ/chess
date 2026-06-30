"""
Simple real-time AI opponent for the RTS chess game.

The AI controls every piece of one color. Because the game is real-time (no
turns), the controller spends an "action budget" that refills at a fixed rate
(actions per second). Each action issues one move:

  1. Captures first — pick the most valuable / most finishable enemy in reach.
  2. Otherwise advance toward the enemy king to apply pressure.

Difficulty (0-10) directly sets how many actions the AI performs per second,
so a higher difficulty means a faster, more reactive opponent. Difficulty 0
disables the AI (zero actions per second).
"""

import random


# Relative worth of each piece, used to prioritise captures.
PIECE_VALUE = {
    "Pawn": 1,
    "Knight": 3,
    "Bishop": 3,
    "Rook": 5,
    "Queen": 9,
    "King": 100,
}

MIN_DIFFICULTY = 0
MAX_DIFFICULTY = 10


class AIController:
    def __init__(self, color, legal_targets_fn, difficulty=5):
        """
        color             — the color this AI plays ("black" or "white").
        legal_targets_fn  — function(piece, pieces) -> list[(col, row)].
        difficulty        — 0..10; equals the number of actions per second.
        """
        self.color = color
        self.legal_targets_fn = legal_targets_fn
        self.budget = 0.0
        self.set_difficulty(difficulty)

    # ------------------------------------------------------------------
    def set_difficulty(self, difficulty):
        """Clamp difficulty to 0..10. Difficulty == actions per second."""
        self.difficulty = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, int(difficulty)))
        self.actions_per_second = float(self.difficulty)
        # Higher difficulty plays more optimally; lower wanders more.
        self.randomness = 1.0 - self.difficulty / MAX_DIFFICULTY

    # ------------------------------------------------------------------
    def update(self, dt, pieces):
        """Refill the action budget and spend whole actions this frame."""
        if self.actions_per_second <= 0:
            return
        self.budget += self.actions_per_second * dt
        # Never bank more than ~1s worth of actions (avoid bursts after a pause).
        self.budget = min(self.budget, self.actions_per_second)
        while self.budget >= 1.0:
            if not self._act(pieces):
                # Nothing to do — don't spin; keep at most one action ready.
                self.budget = min(self.budget, 1.0)
                break
            self.budget -= 1.0

    # ------------------------------------------------------------------
    def _act(self, pieces):
        """Issue a single best move. Returns True if a move was made."""
        enemies = [p for p in pieces if p.alive and p.color != self.color]
        if not enemies:
            return False

        enemy_king = next((p for p in enemies if p.name == "King"), None)

        # Tiles occupied by enemies (current position + mid-slide next tile).
        enemy_tiles = {}
        for e in enemies:
            enemy_tiles[(e.col, e.row)] = e
            if e.moving and e.next_tile:
                enemy_tiles.setdefault(e.next_tile, e)

        idle = [p for p in pieces
                if p.alive and p.color == self.color and not p.moving]
        random.shuffle(idle)

        best_capture = None       # (score, piece, (col, row))
        advance_plans = []        # (dist, piece, (col, row))

        for p in idle:
            targets = self.legal_targets_fn(p, pieces)
            if not targets:
                continue

            # Best capture available to this piece.
            piece_capture = None
            piece_score = -1.0
            for (tc, tr) in targets:
                e = enemy_tiles.get((tc, tr))
                if e is None:
                    continue
                # Favour high-value targets, and those low on HP (finishable).
                score = PIECE_VALUE.get(e.name, 1) * 10.0 - e.hp / 50.0
                if score > piece_score:
                    piece_score = score
                    piece_capture = (tc, tr)

            if piece_capture is not None:
                if best_capture is None or piece_score > best_capture[0]:
                    best_capture = (piece_score, p, piece_capture)
                continue

            # No capture — advance toward the enemy king (or nearest enemy).
            goal = enemy_king or min(
                enemies,
                key=lambda e: abs(e.col - p.col) + abs(e.row - p.row))
            best_move = None
            best_dist = None
            for (tc, tr) in targets:
                d = abs(tc - goal.col) + abs(tr - goal.row)
                if best_dist is None or d < best_dist:
                    best_dist = d
                    best_move = (tc, tr)
            cur_dist = abs(p.col - goal.col) + abs(p.row - goal.row)
            if best_move is not None and best_dist < cur_dist:
                advance_plans.append((best_dist, p, best_move))

        # Always take the best capture when one exists.
        if best_capture is not None:
            _score, p, tgt = best_capture
            p.start_move(*tgt)
            return True

        if not advance_plans:
            return False

        # Pick an advance: optimal when skilled, more random when not.
        if random.random() < self.randomness:
            _dist, p, tgt = random.choice(advance_plans)
        else:
            advance_plans.sort(key=lambda x: x[0])
            _dist, p, tgt = advance_plans[0]
        p.start_move(*tgt)
        return True
