import pygame
import sys
import os
import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TILE = 100
BOARD = 8
WIDTH = TILE * BOARD
HEIGHT = TILE * BOARD + 40  # extra strip for status text
FPS = 60

LIGHT_COLOR = (240, 217, 181)
DARK_COLOR = (181, 136, 99)
HIGHLIGHT_COLOR = (186, 202, 68, 150)
MOVE_DOT_COLOR = (100, 100, 100, 160)
ATTACK_DOT_COLOR = (220, 30, 30, 200)

PIECE_SPEED = 0.3  # tiles per second (same for every piece – slow RTS pace)

HP_MAP = {
    "Pawn": 100,
    "Knight": 300,
    "Bishop": 300,
    "Rook": 500,
    "Queen": 1000,
    "King": 100,
}

DAMAGE_PER_SECOND = 10
STOP_BTN_RADIUS = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_piece_images(base_path):
    """Return dict  images[color][piece_name] = Surface scaled to TILE."""
    images = {"white": {}, "black": {}}
    for piece_name in HP_MAP:
        for color in ("white", "black"):
            path = os.path.join(base_path, "pieces", piece_name, f"{color}.png")
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, (TILE, TILE))
            images[color][piece_name] = img
    return images


def in_bounds(col, row):
    return 0 <= col < BOARD and 0 <= row < BOARD


# ---------------------------------------------------------------------------
# Piece class
# ---------------------------------------------------------------------------

class Piece:
    _attack_counter = 0          # monotonic counter to order concurrent attackers

    def __init__(self, color, name, col, row):
        self.color = color          # "white" or "black"
        self.name = name            # "Pawn", "Knight", …
        self.col = col              # current logical column
        self.row = row              # current logical row
        self.hp = HP_MAP[name]
        self.max_hp = HP_MAP[name]
        self.alive = True

        # movement state
        self.moving = False
        self.target_col = col
        self.target_row = row
        self.pixel_x = float(col * TILE)
        self.pixel_y = float(row * TILE)
        self.origin_col = col
        self.origin_row = row
        # For knight: simultaneous fade-out / fade-in animation
        self.knight_phase = None     # None | "crossfade" | "waiting"
        self.knight_alpha = 255      # alpha at origin (fading out)
        self.knight_dest_alpha = 0   # alpha at destination (fading in)
        self.knight_timer = 0.0
        self.knight_duration = 0.0   # seconds for the whole crossfade

        self.path = []               # list of (col, row) waypoints
        self.path_index = 0
        self.waiting = False         # True if blocked by enemy, waiting to proceed
        self.attack_target = None     # ref to the piece being attacked (for pawn diagonal check)
        self.attack_order = None      # order in which this piece started attacking its tile

        self.being_attacked = False  # True this frame if taking damage (HP bar blinks)

        self.has_moved = False       # for pawn double-step

    # Where is this piece's "next tile" (the tile it is heading towards)?
    @property
    def next_tile(self):
        if self.moving and self.path and self.path_index < len(self.path):
            return self.path[self.path_index]
        return None

    @property
    def current_tile(self):
        return (self.col, self.row)

    # ------------------------------------------------------------------
    def start_move(self, tcol, trow):
        """Begin a move towards (tcol, trow)."""
        self.origin_col = self.col
        self.origin_row = self.row
        self.target_col = tcol
        self.target_row = trow
        self.path = self._compute_path()
        self.path_index = 0
        self.waiting = False
        self.moving = True

        if self.name == "Knight":
            dist = 1.0
            total_time = dist / PIECE_SPEED
            self.knight_duration = total_time
            self.knight_phase = "crossfade"
            self.knight_timer = 0.0
            self.knight_alpha = 255
            self.knight_dest_alpha = 0

    def _compute_path(self):
        """Compute waypoints from current position to target (excluding current tile)."""
        if self.name == "Knight":
            return [(self.target_col, self.target_row)]
        path = []
        c, r = self.col, self.row
        tc, tr = self.target_col, self.target_row
        dc = 0 if tc == c else (1 if tc > c else -1)
        dr = 0 if tr == r else (1 if tr > r else -1)
        cc, rr = c + dc, r + dr
        while True:
            path.append((cc, rr))
            if cc == tc and rr == tr:
                break
            cc += dc
            rr += dr
        return path

    # ------------------------------------------------------------------
    def update(self, dt, pieces):
        if not self.alive:
            return
        if not self.moving:
            return

        if self.name == "Knight":
            self._update_knight(dt, pieces)
        else:
            self._update_slide(dt, pieces)

    # ------------------------------------------------------------------
    def _update_slide(self, dt, pieces):
        if self.path_index >= len(self.path):
            self._finish_move()
            return

        wc, wr = self.path[self.path_index]

        # Check for enemy occupying the target tile FIRST. If an enemy is there,
        # this is an attack — friendly pieces also attacking the same tile must
        # NOT cancel us (multiple pieces may gang up on one enemy).
        # Pawns moving forward only stop for stationary enemies (they keep
        # sliding and take damage if the attacker is moving toward them).
        if self.name == "Pawn" and wc == self.col:
            enemy = self._get_stationary_enemy(pieces, wc, wr)
        else:
            enemy = self._get_enemy_on_tile(pieces, wc, wr)
        if enemy is not None:
            # Snap to current tile center — wait and attack
            self.pixel_x = float(self.col * TILE)
            self.pixel_y = float(self.row * TILE)
            # Pawns can only attack diagonally, never forward
            if self.name == "Pawn" and wc == self.col:
                self.moving = False
                self.waiting = False
                self.path = []
                self.attack_target = None
            else:
                self._begin_attack(enemy)
            return

        # No enemy on the tile — a friendly piece occupying or heading there
        # (to settle, not to attack) blocks us.
        blocker = self._get_blocker(pieces, wc, wr)
        if blocker is not None:
            # Friendly piece blocks — cancel movement
            self.pixel_x = float(self.col * TILE)
            self.pixel_y = float(self.row * TILE)
            self.moving = False
            self.waiting = False
            self.path = []
            self.attack_target = None
            return

        # Target still sliding away but hasn't reached the next tile yet —
        # keep dealing damage until it fully leaves.
        if self.waiting and self.attack_target is not None and self.attack_target.alive:
            if self.attack_target.col == wc and self.attack_target.row == wr:
                return  # defender still on this tile — maintain attack

        # Tile is completely free of enemies
        # Check if pawn diagonal attack failed (defender survived and left)
        if self.waiting and self.name == "Pawn" and wc != self.col:
            if self.attack_target is not None and self.attack_target.alive:
                self.pixel_x = float(self.col * TILE)
                self.pixel_y = float(self.row * TILE)
                self.moving = False
                self.waiting = False
                self.path = []
                self.attack_target = None
                return

        # Head-on collision: enemy heading toward our current tile
        # while we head toward theirs — mutual combat, stay and fight.
        # Pawns moving forward (same column) keep sliding instead.
        if not (self.name == "Pawn" and wc == self.col):
            for q in pieces:
                if (q is not self and q.alive and q.color != self.color
                        and q.moving and q.next_tile == (self.col, self.row)):
                    self.pixel_x = float(self.col * TILE)
                    self.pixel_y = float(self.row * TILE)
                    self._begin_attack(q)
                    return

        # Contested freed tile: only the earliest attacker may claim it.
        # If a friendly piece started attacking this tile before us and is
        # still alive, hold position and let it move in first.
        if self.waiting and self._earlier_attacker_exists(pieces, wc, wr):
            self.pixel_x = float(self.col * TILE)
            self.pixel_y = float(self.row * TILE)
            return

        # Tile is free — slide towards it
        self.waiting = False
        self.attack_target = None
        tx, ty = float(wc * TILE), float(wr * TILE)
        dx = tx - self.pixel_x
        dy = ty - self.pixel_y
        dist = math.hypot(dx, dy)
        step = PIECE_SPEED * TILE * dt

        if dist <= step:
            self.pixel_x = tx
            self.pixel_y = ty
            self.col = wc
            self.row = wr
            self.path_index += 1

            if self.path_index >= len(self.path):
                self._finish_move()
        else:
            self.pixel_x += dx / dist * step
            self.pixel_y += dy / dist * step

    # ------------------------------------------------------------------
    def _update_knight(self, dt, pieces):
        self.knight_timer += dt
        if self.knight_phase == "crossfade":
            t = min(self.knight_timer / self.knight_duration, 1.0)
            enemy = self._get_enemy_on_tile(pieces, self.target_col, self.target_row)
            if enemy is not None:
                # Attacking an occupied tile — stay visible at origin, no fade
                self.knight_alpha = 255
                self.knight_dest_alpha = 0
            else:
                self.knight_alpha = int(255 * (1 - t))      # origin fades out
                self.knight_dest_alpha = int(255 * t)        # target fades in
            if t >= 1.0:
                friendly = self._get_blocker(pieces, self.target_col, self.target_row)
                enemy = self._get_enemy_on_tile(pieces, self.target_col, self.target_row)
                if friendly is not None:
                    # Friendly blocker – snap back to origin
                    self.pixel_x = float(self.origin_col * TILE)
                    self.pixel_y = float(self.origin_row * TILE)
                    self.col = self.origin_col
                    self.row = self.origin_row
                    self.knight_phase = None
                    self.knight_alpha = 255
                    self.knight_dest_alpha = 0
                    self.moving = False
                    self.waiting = False
                    self.path = []
                elif enemy is not None:
                    # Wait for enemy to die / move — stay visible at origin
                    self.knight_phase = "waiting"
                    self.knight_alpha = 255
                    self.knight_dest_alpha = 0
                    self._begin_attack(enemy)
                else:
                    # Arrived
                    self.pixel_x = float(self.target_col * TILE)
                    self.pixel_y = float(self.target_row * TILE)
                    self.col = self.target_col
                    self.row = self.target_row
                    self.knight_phase = None
                    self.knight_alpha = 255
                    self.knight_dest_alpha = 0
                    self._finish_move()
        elif self.knight_phase == "waiting":
            friendly = self._get_blocker(pieces, self.target_col, self.target_row)
            enemy = self._get_enemy_on_tile(pieces, self.target_col, self.target_row)
            if friendly is not None:
                # Friendly moved in – cancel
                self.pixel_x = float(self.origin_col * TILE)
                self.pixel_y = float(self.origin_row * TILE)
                self.col = self.origin_col
                self.row = self.origin_row
                self.knight_phase = None
                self.knight_alpha = 255
                self.knight_dest_alpha = 0
                self.moving = False
                self.waiting = False
                self.path = []
            elif enemy is None:
                # Contested freed tile: let the earliest attacker move in first.
                if self._earlier_attacker_exists(pieces, self.target_col, self.target_row):
                    return
                self.pixel_x = float(self.target_col * TILE)
                self.pixel_y = float(self.target_row * TILE)
                self.col = self.target_col
                self.row = self.target_row
                self.knight_phase = None
                self.knight_alpha = 255
                self.knight_dest_alpha = 0
                self.waiting = False
                self._finish_move()

    # ------------------------------------------------------------------
    def _finish_move(self):
        moved = (self.col != self.origin_col or self.row != self.origin_row)
        self.moving = False
        self.waiting = False
        self.attack_target = None
        self.attack_order = None
        self.path = []
        self.path_index = 0
        if moved:
            self.has_moved = True

    def _begin_attack(self, enemy):
        """Enter the waiting/attacking state, recording attack order on first entry
        so concurrent attackers can be resolved first-come-first-served."""
        if not self.waiting:
            Piece._attack_counter += 1
            self.attack_order = Piece._attack_counter
        self.waiting = True
        self.attack_target = enemy

    def _earlier_attacker_exists(self, pieces, col, row):
        """True if a friendly piece started attacking tile (col, row) before us
        and is still alive (so it has priority to move onto the freed tile)."""
        if self.attack_order is None:
            return False
        for q in pieces:
            if (q is not self and q.alive and q.color == self.color
                    and q.waiting and q.next_tile == (col, row)
                    and q.attack_order is not None
                    and q.attack_order < self.attack_order):
                return True
        return False

    def _get_blocker(self, pieces, col, row):
        """Return an alive same-color piece sitting on or sliding through (col, row).
        Enemy pieces do NOT block — they are handled via the combat system.
        A friendly piece that is merely *waiting* (attacking that tile) does not
        block — multiple friendly pieces may attack the same enemy tile at once."""
        for q in pieces:
            if q is not self and q.alive and q.color == self.color:
                if q.col == col and q.row == row:
                    return q
                if q.moving and not q.waiting and q.next_tile == (col, row):
                    return q
        return None

    def _get_enemy_on_tile(self, pieces, col, row):
        """Return an alive enemy whose current or next tile is (col, row), or None."""
        for q in pieces:
            if q is not self and q.alive and q.color != self.color:
                if q.col == col and q.row == row:
                    return q
                if q.moving and q.next_tile == (col, row):
                    return q
        return None

    def _get_stationary_enemy(self, pieces, col, row):
        """Return an alive non-moving enemy sitting on (col, row), or None."""
        for q in pieces:
            if q is not self and q.alive and q.color != self.color:
                if q.col == col and q.row == row and not q.moving:
                    return q
        return None

    def stop(self):
        """Stop movement, snap to current logical tile."""
        self.pixel_x = float(self.col * TILE)
        self.pixel_y = float(self.row * TILE)
        self.target_col = self.col
        self.target_row = self.row
        self.moving = False
        self.waiting = False
        self.attack_target = None
        self.attack_order = None
        self.path = []
        self.path_index = 0
        if self.name == "Knight":
            self.knight_phase = None
            self.knight_alpha = 255
            self.knight_dest_alpha = 0

    # ------------------------------------------------------------------
    def draw(self, surface, images):
        if not self.alive:
            return
        img = images[self.color][self.name]

        if self.name == "Knight" and self.knight_phase == "crossfade":
            # Draw fading-out copy at origin
            origin_img = img.copy()
            origin_img.set_alpha(self.knight_alpha)
            surface.blit(origin_img, (self.origin_col * TILE, self.origin_row * TILE))
            # Draw fading-in copy at target
            dest_img = img.copy()
            dest_img.set_alpha(self.knight_dest_alpha)
            surface.blit(dest_img, (self.target_col * TILE, self.target_row * TILE))
        elif self.name == "Knight" and self.knight_phase == "waiting":
            # Knight stays visible at its origin while attacking
            surface.blit(img, (self.origin_col * TILE, self.origin_row * TILE))
        else:
            surface.blit(img, (self.pixel_x, self.pixel_y))

        # health bar
        self._draw_hp(surface)
        # blue movement arrow from origin to final target while moving
        if self.moving and not self.waiting:
            self._draw_move_arrow(surface)
        # red attack arrow when waiting
        if self.waiting and self.next_tile:
            self._draw_attack_arrow(surface)
        # stop button for moving pieces
        if self.moving:
            self._draw_stop_btn(surface)

    def _draw_move_arrow(self, surface):
        """Draw a blue arrow from the starting tile center to the final target tile center."""
        sx = self.origin_col * TILE + TILE // 2
        sy = self.origin_row * TILE + TILE // 2
        ex = self.target_col * TILE + TILE // 2
        ey = self.target_row * TILE + TILE // 2
        if sx == ex and sy == ey:
            return
        color = (40, 100, 220)
        pygame.draw.line(surface, color, (sx, sy), (ex, ey), 3)
        angle = math.atan2(ey - sy, ex - sx)
        head_len = 14
        for sign in (1, -1):
            hx = ex - head_len * math.cos(angle + sign * 0.45)
            hy = ey - head_len * math.sin(angle + sign * 0.45)
            pygame.draw.line(surface, color, (ex, ey), (int(hx), int(hy)), 3)

    def _draw_attack_arrow(self, surface):
        """Draw a red arrow from the piece's tile center to the enemy tile center."""
        sx = self.col * TILE + TILE // 2
        sy = self.row * TILE + TILE // 2
        nt = self.next_tile
        if nt is None:
            return
        ex = nt[0] * TILE + TILE // 2
        ey = nt[1] * TILE + TILE // 2
        color = (220, 30, 30)
        pygame.draw.line(surface, color, (sx, sy), (ex, ey), 3)
        # arrowhead
        angle = math.atan2(ey - sy, ex - sx)
        head_len = 14
        for offset in (2.5, -2.5):
            hx = ex - head_len * math.cos(angle + offset * 0.18 + 0.35 * (1 if offset > 0 else -1))
            hy = ey - head_len * math.sin(angle + offset * 0.18 + 0.35 * (1 if offset > 0 else -1))
            pygame.draw.line(surface, color, (ex, ey), (int(hx), int(hy)), 3)

    def _draw_stop_btn(self, surface):
        cx = int(self.pixel_x + TILE - STOP_BTN_RADIUS - 2)
        cy = int(self.pixel_y + STOP_BTN_RADIUS + 2)
        pygame.draw.circle(surface, (200, 40, 40), (cx, cy), STOP_BTN_RADIUS)
        m = 4
        pygame.draw.line(surface, (255, 255, 255),
                         (cx - m, cy - m), (cx + m, cy + m), 2)
        pygame.draw.line(surface, (255, 255, 255),
                         (cx + m, cy - m), (cx - m, cy + m), 2)

    def stop_btn_hit(self, mx, my):
        """Return True if (mx, my) hits this piece's stop button."""
        if not self.moving or not self.alive:
            return False
        cx = self.pixel_x + TILE - STOP_BTN_RADIUS - 2
        cy = self.pixel_y + STOP_BTN_RADIUS + 2
        return math.hypot(mx - cx, my - cy) <= STOP_BTN_RADIUS

    def _draw_hp(self, surface):
        bar_w = TILE - 10
        bar_h = 6
        bx = self.pixel_x + 5
        by = self.pixel_y + TILE - 10
        ratio = max(self.hp / self.max_hp, 0)
        # background
        pygame.draw.rect(surface, (60, 60, 60), (bx, by, bar_w, bar_h))
        # fill
        if ratio > 0.5:
            color = (0, 200, 0)
        elif ratio > 0.2:
            color = (220, 140, 0)
        else:
            color = (210, 30, 30)
        # Blink while being attacked: skip drawing the fill on alternate intervals
        blink_on = True
        if self.being_attacked:
            blink_on = (pygame.time.get_ticks() // 150) % 2 == 0
        if blink_on:
            pygame.draw.rect(surface, color, (bx, by, int(bar_w * ratio), bar_h))
        # border
        pygame.draw.rect(surface, (0, 0, 0), (bx, by, bar_w, bar_h), 1)


# ---------------------------------------------------------------------------
# Move-generation helpers (chess-like rules, ignoring check)
# ---------------------------------------------------------------------------

def occupied_by(pieces, col, row):
    """Return the Piece at (col, row) that is alive and sitting there, or None."""
    for p in pieces:
        if p.alive and p.col == col and p.row == row and not p.moving:
            return p
    return None


def tile_blocked_by_own(pieces, piece, col, row):
    """True if a friendly piece currently occupies or is moving through (col, row).
    A moving piece only blocks its current tile and its next tile — the rest of
    its path (including the final destination) stays free for other pieces.
    A friendly piece that is merely *waiting* (attacking that tile) does not
    block — multiple friendly pieces may attack the same enemy tile at once."""
    for p in pieces:
        if p is piece or not p.alive:
            continue
        if p.color != piece.color:
            continue
        if (p.col == col and p.row == row):
            return True
        if p.moving and not p.waiting and p.next_tile == (col, row):
            return True
    return True if not in_bounds(col, row) else False


def get_legal_targets(piece, pieces):
    """Return list of (col, row) that *piece* can move to right now."""
    if piece.moving:
        return []
    targets = []
    c, r = piece.col, piece.row

    def add(tc, tr):
        if in_bounds(tc, tr) and not tile_blocked_by_own(pieces, piece, tc, tr):
            targets.append((tc, tr))

    if piece.name == "Pawn":
        direction = -1 if piece.color == "white" else 1
        # forward 1
        fc, fr = c, r + direction
        if in_bounds(fc, fr) and _pawn_path_clear(pieces, piece, fc, fr):
            add(fc, fr)
            # forward 2 from start row
            if not piece.has_moved:
                fc2, fr2 = c, r + 2 * direction
                if in_bounds(fc2, fr2) and _pawn_path_clear(pieces, piece, fc2, fr2):
                    add(fc2, fr2)
        # diagonal captures – allowed if opponent occupies that tile or is sliding through it
        for dc in (-1, 1):
            tc, tr = c + dc, r + direction
            if in_bounds(tc, tr):
                occ = _any_piece_at(pieces, tc, tr, exclude=piece, include_next=True)
                if occ and occ.color != piece.color:
                    add(tc, tr)

    elif piece.name == "Knight":
        for dc, dr in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                        (1, -2), (1, 2), (2, -1), (2, 1)]:
            add(c + dc, r + dr)

    elif piece.name == "Bishop":
        for dc, dr in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            _slide(pieces, piece, c, r, dc, dr, targets)

    elif piece.name == "Rook":
        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            _slide(pieces, piece, c, r, dc, dr, targets)

    elif piece.name == "Queen":
        for dc, dr in [(-1, -1), (-1, 1), (1, -1), (1, 1),
                        (-1, 0), (1, 0), (0, -1), (0, 1)]:
            _slide(pieces, piece, c, r, dc, dr, targets)

    elif piece.name == "King":
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                add(c + dc, r + dr)

    return targets


def _any_piece_at(pieces, col, row, exclude=None, include_next=False):
    for p in pieces:
        if p is exclude or not p.alive:
            continue
        if p.col == col and p.row == row:
            return p
        if include_next and p.moving and p.next_tile == (col, row):
            return p
    return None


def _pawn_path_clear(pieces, piece, tc, tr):
    """For pawn forward moves, the target must not contain ANY piece
    (including pieces mid-slide whose next_tile is this square)."""
    occ = _any_piece_at(pieces, tc, tr, exclude=piece, include_next=True)
    return occ is None


def _slide(pieces, piece, sc, sr, dc, dr, targets):
    nc, nr = sc + dc, sr + dr
    while in_bounds(nc, nr):
        occ = _any_piece_at(pieces, nc, nr, exclude=piece)
        if occ:
            if occ.color != piece.color:
                if not tile_blocked_by_own(pieces, piece, nc, nr):
                    targets.append((nc, nr))
            break  # can't go past
        if not tile_blocked_by_own(pieces, piece, nc, nr):
            targets.append((nc, nr))
        nc += dc
        nr += dr


# ---------------------------------------------------------------------------
# Path-collision for sliding pieces
# ---------------------------------------------------------------------------

def _path_tiles(piece):
    """Return the list of intermediate tiles the piece currently traverses
    (not counting start/end) so we can check blocking during slide.
    For knight there are no intermediate tiles."""
    if piece.name == "Knight":
        return []
    c0, r0 = piece.col, piece.row
    c1, r1 = piece.target_col, piece.target_row
    dc = 0 if c1 == c0 else (1 if c1 > c0 else -1)
    dr = 0 if r1 == r0 else (1 if r1 > r0 else -1)
    tiles = []
    cc, rr = c0 + dc, r0 + dr
    while (cc, rr) != (c1, r1):
        tiles.append((cc, rr))
        cc += dc
        rr += dr
    return tiles


# ---------------------------------------------------------------------------
# Combat system
# ---------------------------------------------------------------------------

def process_combat(pieces, dt):
    """Only the defending piece takes damage.  An attacker is a moving piece
    whose next_tile equals any tile the defender occupies (current or mid-slide)."""
    damage_per_frame = DAMAGE_PER_SECOND * dt

    # Reset per-frame attack indicator
    for p in pieces:
        p.being_attacked = False

    for attacker in pieces:
        if not attacker.alive or not attacker.moving:
            continue
        target_tile = attacker.next_tile
        if target_tile is None:
            continue
        # Pawns only deal damage diagonally, never forward
        if attacker.name == "Pawn" and target_tile[0] == attacker.col:
            continue
        for defender in pieces:
            if defender is attacker or not defender.alive:
                continue
            if defender.color == attacker.color:
                continue
            # Defender occupies both its current tile and (if mid-slide) its next tile
            defender_tiles = {defender.current_tile}
            if defender.moving and defender.next_tile:
                defender_tiles.add(defender.next_tile)
            if target_tile in defender_tiles:
                defender.hp -= damage_per_frame
                defender.being_attacked = True
                if defender.hp <= 0:
                    defender.hp = 0
                    defender.alive = False


# ---------------------------------------------------------------------------
# Board setup
# ---------------------------------------------------------------------------

def create_pieces():
    pieces = []
    # Order: Rook Knight Bishop Queen King Bishop Knight Rook
    back_rank = ["Rook", "Knight", "Bishop", "Queen", "King", "Bishop", "Knight", "Rook"]
    for i, name in enumerate(back_rank):
        pieces.append(Piece("black", name, i, 0))
    for i in range(8):
        pieces.append(Piece("black", "Pawn", i, 1))
    for i in range(8):
        pieces.append(Piece("white", "Pawn", i, 6))
    for i, name in enumerate(back_rank):
        pieces.append(Piece("white", name, i, 7))
    return pieces


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def draw_board(surface):
    for r in range(BOARD):
        for c in range(BOARD):
            color = LIGHT_COLOR if (r + c) % 2 == 0 else DARK_COLOR
            pygame.draw.rect(surface, color, (c * TILE, r * TILE, TILE, TILE))


def draw_highlights(surface, selected, legal_targets, pieces):
    if selected is None:
        return
    # highlight selected tile
    hs = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    hs.fill(HIGHLIGHT_COLOR)
    surface.blit(hs, (selected.col * TILE, selected.row * TILE))
    # draw legal move dots (grey for empty tiles only)
    for (tc, tr) in legal_targets:
        # Skip if an enemy occupies this tile (current or next) — drawn as red dot later
        is_attack = False
        for p in pieces:
            if p is selected or not p.alive or p.color == selected.color:
                continue
            if (p.col == tc and p.row == tr):
                is_attack = True
                break
            if p.moving and p.next_tile == (tc, tr):
                is_attack = True
                break
        if is_attack:
            continue
        dot = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        pygame.draw.circle(dot, MOVE_DOT_COLOR, (TILE // 2, TILE // 2), 15)
        surface.blit(dot, (tc * TILE, tr * TILE))


def draw_attack_dots(surface, selected, legal_targets, pieces):
    """Draw red dots on every legal-target tile where an enemy is present
    (on its current tile OR its mid-slide next tile)."""
    if selected is None:
        return
    # Build set of all tiles occupied by enemies (current + next)
    enemy_tiles = set()
    for p in pieces:
        if p is selected or not p.alive or p.color == selected.color:
            continue
        enemy_tiles.add((p.col, p.row))
        if p.moving and p.next_tile:
            enemy_tiles.add(p.next_tile)
    # Draw red dot on any legal target that overlaps an enemy tile
    for (tc, tr) in legal_targets:
        if (tc, tr) in enemy_tiles:
            dot = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            pygame.draw.circle(dot, ATTACK_DOT_COLOR, (TILE // 2, TILE // 2), 18)
            surface.blit(dot, (tc * TILE, tr * TILE))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Real-Time Chess")
    parser.add_argument("--host", action="store_true",
                        help="Host a game (you play white)")
    parser.add_argument("--join", type=str, default=None, metavar="IP",
                        help="Join a game at IP (you play black)")
    parser.add_argument("--ai", action="store_true",
                        help="Play locally against the AI (you play white, AI plays black)")
    parser.add_argument("--difficulty", type=int, default=5,
                        metavar="0-10",
                        help="AI difficulty 0-10 (= AI actions per second; 0 disables it)")
    args = parser.parse_args()

    is_server = args.host
    is_client = args.join is not None
    is_network = is_server or is_client
    ai_enabled = args.ai and not is_network
    my_color = ("white" if is_server
                else "black" if is_client
                else "white" if ai_enabled
                else None)
    # True if the local human may only control pieces of my_color.
    restrict_input = is_network or ai_enabled

    # --- Networking setup ---
    net = None
    if is_server:
        from network import Server
        net = Server()
        net.wait_for_client()
    elif is_client:
        from network import Client
        net = Client(args.join)
        net.connect()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    caption = "Real-Time Chess"
    if is_server:
        caption += " [HOST - White]"
    elif is_client:
        caption += " [CLIENT - Black]"
    elif ai_enabled:
        caption += " [vs AI - White]"
    pygame.display.set_caption(caption)
    clock = pygame.time.Clock()

    base_path = os.path.dirname(os.path.abspath(__file__))
    images = load_piece_images(base_path)
    pieces = create_pieces()

    # AI opponent (local play only) — controls the black army.
    ai = None
    if ai_enabled:
        from ai import AIController
        ai = AIController("black", get_legal_targets, difficulty=args.difficulty)

    selected = None        # currently selected Piece (or None)
    legal_targets = []     # list of (col, row)
    game_over = False
    winner = None
    font = pygame.font.SysFont("consolas", 22)

    sync_timer = 0.0
    SYNC_INTERVAL = 1.0 / 20  # 20 Hz state sync

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0  # seconds

        # --- Network: receive ---
        if is_server and net:
            for msg in net.get_messages():
                if msg.get("type") == "move":
                    idx = msg["piece_index"]
                    if 0 <= idx < len(pieces):
                        p = pieces[idx]
                        if p.alive and p.color == "black" and not p.moving:
                            p.start_move(msg["target_col"], msg["target_row"])
                elif msg.get("type") == "stop":
                    idx = msg["piece_index"]
                    if 0 <= idx < len(pieces):
                        p = pieces[idx]
                        if p.color == "black":
                            p.stop()

        if is_client and net:
            from network import apply_state
            for msg in net.get_messages():
                if msg.get("type") == "state":
                    apply_state(pieces, msg["pieces"])
                    game_over = msg["game_over"]
                    winner = msg["winner"]

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not game_over:
                mx, my = event.pos

                # Check stop buttons first
                stop_hit = False
                for i, p in enumerate(pieces):
                    if p.stop_btn_hit(mx, my):
                        # Only allow stopping pieces the local player controls
                        if restrict_input and p.color != my_color:
                            continue
                        if is_client and net:
                            net.send_stop(i)
                        else:
                            p.stop()
                        stop_hit = True
                        break
                if stop_hit:
                    selected = None
                    legal_targets = []
                    continue

                click_col = mx // TILE
                click_row = my // TILE
                if not in_bounds(click_col, click_row):
                    selected = None
                    legal_targets = []
                    continue

                # Did we click on a legal target?
                # First check if there's a friendly piece on this tile - always re-select it
                clicked_piece = None
                for p in pieces:
                    if p.alive and not p.moving and p.col == click_col and p.row == click_row:
                        clicked_piece = p
                        break

                # In network mode, only select own pieces
                if restrict_input and clicked_piece and clicked_piece.color != my_color:
                    clicked_piece = None

                if clicked_piece and (clicked_piece is selected or clicked_piece.color == (selected.color if selected else None)):
                    # Re-select (reevaluate moves) on every click
                    selected = clicked_piece
                    legal_targets = get_legal_targets(clicked_piece, pieces)
                elif selected and (click_col, click_row) in legal_targets:
                    if is_client and net:
                        idx = pieces.index(selected)
                        net.send_move(idx, click_col, click_row)
                    else:
                        selected.start_move(click_col, click_row)
                    selected = None
                    legal_targets = []
                elif clicked_piece:
                    selected = clicked_piece
                    legal_targets = get_legal_targets(clicked_piece, pieces)
                else:
                    selected = None
                    legal_targets = []

        # --- Simulation (server or local only — client receives state) ---
        if not is_client and not game_over:
            # --- AI opponent issues moves for its color ---
            if ai:
                ai.update(dt, pieces)

            # --- Combat (before movement so damage applies until 100% arrival) ---
            process_combat(pieces, dt)

            # --- Update movement ---
            for p in pieces:
                p.update(dt, pieces)

            # --- Check game over ---
            for p in pieces:
                if p.name == "King" and not p.alive:
                    game_over = True
                    winner = "Black" if p.color == "white" else "White"

            # If selected piece died or started moving, deselect
            if selected and (not selected.alive or selected.moving):
                selected = None
                legal_targets = []

        # --- Network: send state (server only) ---
        if is_server and net:
            sync_timer += dt
            if sync_timer >= SYNC_INTERVAL:
                sync_timer = 0.0
                net.send_state(pieces, game_over, winner)

        # --- Draw ---
        draw_board(screen)
        draw_highlights(screen, selected, legal_targets, pieces)

        # Draw pieces (alive only)
        for p in pieces:
            p.draw(screen, images)

        # Draw attack dots over enemy pieces
        draw_attack_dots(screen, selected, legal_targets, pieces)

        # Status bar
        status_rect = pygame.Rect(0, TILE * BOARD, WIDTH, 40)
        pygame.draw.rect(screen, (30, 30, 30), status_rect)
        if game_over:
            txt = font.render(f"{winner} wins!  Press ESC to quit.", True, (255, 255, 100))
        elif is_network and net and not net.connected:
            txt = font.render("Disconnected!", True, (255, 80, 80))
        elif selected:
            txt = font.render(f"Selected: {selected.color} {selected.name}", True, (220, 220, 220))
        else:
            txt = font.render("Click a piece to select, then click a target.", True, (180, 180, 180))
        screen.blit(txt, (10, TILE * BOARD + 8))

        pygame.display.flip()

        # ESC to quit
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

    if net:
        net.close()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
