"""
Neural-network move policy for the RTS chess AI.

A small MLP scores every candidate move (piece -> target tile) from a fixed
feature vector; the policy picks the highest-scoring move. The same network is
used both during evolutionary training (train.py) and when playing the game
(ChessGame.py --ai), so a trained "brain" file transfers directly into play.

PyTorch is only imported here, keeping ai.py dependency-free.
"""

import torch
import torch.nn as nn

from ai import PIECE_VALUE


N_FEATURES = 10
BOARD_SIZE = 8
MAX_DIST = 2 * (BOARD_SIZE - 1)          # max manhattan distance on the board
MAX_MATERIAL = 39.0                       # rough total value of one side's army
CENTER = (BOARD_SIZE - 1) / 2.0


class Brain(nn.Module):
    """Maps a move feature vector to a scalar desirability score."""

    def __init__(self, n_in=N_FEATURES, n_hidden=24):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, n_hidden), nn.Tanh(),
            nn.Linear(n_hidden, n_hidden), nn.Tanh(),
            nn.Linear(n_hidden, 1),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def clone_brain(brain):
    c = Brain()
    c.load_state_dict(brain.state_dict())
    return c


def mutate(brain, sigma):
    """Return a mutated copy of brain (gaussian noise added to all weights)."""
    child = clone_brain(brain)
    with torch.no_grad():
        for p in child.parameters():
            p.add_(torch.randn_like(p) * sigma)
    return child


def save_brain(brain, path):
    torch.save(brain.state_dict(), path)


def load_brain(path):
    brain = Brain()
    brain.load_state_dict(torch.load(path, map_location="cpu"))
    brain.eval()
    return brain


def _material(pieces, color):
    return sum(PIECE_VALUE.get(p.name, 1)
               for p in pieces if p.alive and p.color == color)


class NNPolicy:
    """Chooses moves by scoring candidates with a Brain.

    sigma > 0 adds exploration noise to scores (used during training).
    """

    def __init__(self, brain, sigma=0.0):
        self.brain = brain
        self.sigma = sigma

    # ------------------------------------------------------------------
    def choose(self, idle, pieces, color, legal_targets_fn):
        enemies = [p for p in pieces if p.alive and p.color != color]
        if not enemies:
            return None

        enemy_king = next((p for p in enemies if p.name == "King"), None)

        # Tiles occupied by enemies (current + mid-slide next tile).
        enemy_tiles = {}
        for e in enemies:
            enemy_tiles[(e.col, e.row)] = e
            if e.moving and e.next_tile:
                enemy_tiles.setdefault(e.next_tile, e)

        my_mat = _material(pieces, color)
        enemy_mat = sum(PIECE_VALUE.get(p.name, 1) for p in enemies)
        mat_balance = (my_mat - enemy_mat) / MAX_MATERIAL
        forward = 1 if color == "black" else -1  # black advances down, white up

        feats = []
        candidates = []
        for p in idle:
            for (tc, tr) in legal_targets_fn(p, pieces):
                candidates.append((p, (tc, tr)))
                feats.append(self._features(
                    p, tc, tr, enemy_tiles, enemy_king,
                    mat_balance, forward))

        if not candidates:
            return None

        with torch.no_grad():
            x = torch.tensor(feats, dtype=torch.float32)
            scores = self.brain(x)
            if self.sigma > 0:
                scores = scores + torch.randn_like(scores) * self.sigma
            best = int(torch.argmax(scores).item())

        return candidates[best]

    # ------------------------------------------------------------------
    def _features(self, p, tc, tr, enemy_tiles, enemy_king,
                  mat_balance, forward):
        enemy = enemy_tiles.get((tc, tr))
        is_capture = 1.0 if enemy is not None else 0.0
        cap_value = (PIECE_VALUE.get(enemy.name, 1) / 9.0) if enemy else 0.0
        cap_hp = (enemy.hp / enemy.max_hp) if enemy else 0.0

        if enemy_king is not None:
            cur_kd = abs(p.col - enemy_king.col) + abs(p.row - enemy_king.row)
            new_kd = abs(tc - enemy_king.col) + abs(tr - enemy_king.row)
            new_kd_n = new_kd / MAX_DIST
            delta_kd = (cur_kd - new_kd) / MAX_DIST
        else:
            new_kd_n = 0.0
            delta_kd = 0.0

        advance = forward * (tr - p.row) / (BOARD_SIZE - 1)
        center = 1.0 - (abs(tc - CENTER) + abs(tr - CENTER)) / MAX_DIST

        return [
            PIECE_VALUE.get(p.name, 1) / 9.0,
            p.hp / p.max_hp,
            is_capture,
            cap_value,
            cap_hp,
            new_kd_n,
            delta_kd,
            advance,
            mat_balance,
            center,
        ]
