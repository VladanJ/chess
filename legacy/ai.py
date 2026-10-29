"""
Simple real-time AI opponent for the RTS chess game.

The AI controls every piece of one color. Because the game is real-time (no
turns), the controller spends an "action budget" that refills at a fixed rate
(actions per second). Each action issues one move:

  1. Defend the king — if an enemy can reach our king, remove the threat
     (capture the attacker) or move the king to safety. Applied at every
     difficulty so even a weak AI protects its king.
  2. Captures next — pick the most valuable / most finishable enemy in reach.
  3. Otherwise advance toward the enemy king to apply pressure.

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
    def __init__(self, color, legal_targets_fn, difficulty=5, policy=None):
        """
        color             — the color this AI plays ("black" or "white").
        legal_targets_fn  — function(piece, pieces) -> list[(col, row)].
        difficulty        — 0..10; equals the number of actions per second.
        policy            — optional object with
                            choose(idle, pieces, color, legal_targets_fn)
                            -> (piece, (col, row)) or None. When given, it
                            replaces the built-in heuristic move selection.
        """
        self.color = color
        self.legal_targets_fn = legal_targets_fn
        self.policy = policy
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
        # Never bank more than one pending action (avoid bursts after a pause).
        # Cap at >= 1.0 so slow cadences (< 1 action/sec) can still reach a move.
        self.budget = min(self.budget, max(self.actions_per_second, 1.0))
        while self.budget >= 1.0:
            if not self._act(pieces):
                # Nothing to do — don't spin; keep at most one action ready.
                self.budget = min(self.budget, 1.0)
                break
            self.budget -= 1.0

    # ------------------------------------------------------------------
    def _defend_king(self, idle, pieces, enemies):
        """Return a (piece, target) move that protects our own king, or None.

        Runs before ordinary play at *every* difficulty so the AI always
        reacts to direct threats on its king:
          1. capture an enemy that can reach the king (with a non-king piece),
          2. otherwise flee the king to a tile no enemy can reach,
          3. otherwise let the king capture the attacker as a last resort.
        """
        king = next((p for p in pieces if p.alive
                     and p.color == self.color and p.name == "King"), None)
        if king is None or king.moving:
            return None
        king_tile = (king.col, king.row)

        # Enemies that can move onto the king's tile right now = direct threats.
        attackers = [e for e in enemies
                     if king_tile in self.legal_targets_fn(e, pieces)]
        if not attackers:
            return None

        attacker_tiles = {(e.col, e.row): e for e in attackers}

        # 1) Remove the threat: capture an attacker with a non-king piece,
        #    preferring the most valuable / most finishable one.
        best = None            # (score, piece, (col, row))
        king_capture = None    # fallback: king takes an adjacent attacker
        for p in idle:
            if p.moving:
                continue
            for (tc, tr) in self.legal_targets_fn(p, pieces):
                e = attacker_tiles.get((tc, tr))
                if e is None:
                    continue
                if p is king:
                    king_capture = (king, (tc, tr))
                    continue
                score = PIECE_VALUE.get(e.name, 1) * 10.0 - e.hp / 50.0
                if best is None or score > best[0]:
                    best = (score, p, (tc, tr))
        if best is not None:
            return (best[1], best[2])

        # 2) Flee: move the king to a tile no enemy can currently reach,
        #    picking the one farthest from the nearest attacker.
        enemy_reach = set()
        for e in enemies:
            enemy_reach.update(self.legal_targets_fn(e, pieces))
        safe = [t for t in self.legal_targets_fn(king, pieces)
                if t not in enemy_reach]
        if safe:
            safe.sort(
                key=lambda t: min(abs(t[0] - e.col) + abs(t[1] - e.row)
                                  for e in attackers),
                reverse=True)
            return (king, safe[0])

        # 3) Last resort: trade the king into an adjacent attacker.
        if king_capture is not None:
            return king_capture

        return None

    # ------------------------------------------------------------------
    def _act(self, pieces):
        """Issue a single best move. Returns True if a move was made."""
        enemies = [p for p in pieces if p.alive and p.color != self.color]
        if not enemies:
            return False

        idle = [p for p in pieces
                if p.alive and p.color == self.color and not p.moving]
        if not idle:
            return False

        # Delegate move selection to a learned policy when one is provided.
        if self.policy is not None:
            choice = self.policy.choose(idle, pieces, self.color,
                                        self.legal_targets_fn)
            if choice is None:
                return False
            piece, tgt = choice
            piece.start_move(*tgt)
            return True

        enemy_king = next((p for p in enemies if p.name == "King"), None)

        # King safety comes first, at EVERY difficulty (not subject to the
        # low-difficulty randomness used for ordinary moves).
        defense = self._defend_king(idle, pieces, enemies)
        if defense is not None:
            piece, tgt = defense
            piece.start_move(*tgt)
            return True

        # Tiles occupied by enemies (current position + mid-slide next tile).
        enemy_tiles = {}
        for e in enemies:
            enemy_tiles[(e.col, e.row)] = e
            if e.moving and e.next_tile:
                enemy_tiles.setdefault(e.next_tile, e)

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
