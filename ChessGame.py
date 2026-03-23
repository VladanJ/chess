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

PIECE_SPEED = 0.2  # tiles per second (same for every piece – slow RTS pace)

HP_MAP = {
    "Pawn": 100,
    "Knight": 300,
    "Bishop": 300,
    "Rook": 500,
    "Queen": 1000,
    "King": 5000,
}

DAMAGE_PER_SECOND = 10

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
        # For knight: fade-out / fade-in animation
        self.knight_phase = None     # None | "fadeout" | "fadein"
        self.knight_alpha = 255
        self.knight_timer = 0.0
        self.knight_duration = 0.0   # seconds for half of the animation

        self.has_moved = False       # for pawn double-step

    # Where is this piece's "next tile" (the tile it is heading towards)?
    @property
    def next_tile(self):
        if self.moving:
            return (self.target_col, self.target_row)
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
        self.moving = True

        if self.name == "Knight":
            # Compute duration so speed matches other pieces (based on Manhattan-like
            # distance of a knight = 3 tiles, at PIECE_SPEED tiles/sec).
            dist = 3.0  # conceptual knight travel distance
            total_time = dist / PIECE_SPEED
            self.knight_duration = total_time / 2.0
            self.knight_phase = "fadeout"
            self.knight_timer = 0.0
            self.knight_alpha = 255

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
        tx = float(self.target_col * TILE)
        ty = float(self.target_row * TILE)
        dx = tx - self.pixel_x
        dy = ty - self.pixel_y
        dist = math.hypot(dx, dy)
        step = PIECE_SPEED * TILE * dt  # pixels this frame

        if dist <= step:
            if self._target_occupied(pieces):
                self._cancel_move()
            else:
                self.pixel_x = tx
                self.pixel_y = ty
                self._finish_move()
        else:
            self.pixel_x += dx / dist * step
            self.pixel_y += dy / dist * step

    # ------------------------------------------------------------------
    def _update_knight(self, dt, pieces):
        self.knight_timer += dt
        if self.knight_phase == "fadeout":
            t = min(self.knight_timer / self.knight_duration, 1.0)
            self.knight_alpha = int(255 * (1 - t))
            if t >= 1.0:
                if self._target_occupied(pieces):
                    # Target blocked – fade back in on origin tile
                    self.pixel_x = float(self.origin_col * TILE)
                    self.pixel_y = float(self.origin_row * TILE)
                    self.target_col = self.origin_col
                    self.target_row = self.origin_row
                else:
                    self.pixel_x = float(self.target_col * TILE)
                    self.pixel_y = float(self.target_row * TILE)
                self.knight_phase = "fadein"
                self.knight_timer = 0.0
                self.knight_alpha = 0
        elif self.knight_phase == "fadein":
            t = min(self.knight_timer / self.knight_duration, 1.0)
            self.knight_alpha = int(255 * t)
            if t >= 1.0:
                self.knight_alpha = 255
                self.knight_phase = None
                self._finish_move()

    # ------------------------------------------------------------------
    def _finish_move(self):
        moved = (self.col != self.target_col or self.row != self.target_row)
        self.col = self.target_col
        self.row = self.target_row
        self.moving = False
        if moved:
            self.has_moved = True

    def _target_occupied(self, pieces):
        """True if any other alive piece sits on the target tile."""
        for q in pieces:
            if q is not self and q.alive and q.col == self.target_col and q.row == self.target_row:
                return True
        return False

    def _cancel_move(self):
        """Snap back to origin – target was occupied on arrival."""
        self.pixel_x = float(self.origin_col * TILE)
        self.pixel_y = float(self.origin_row * TILE)
        self.target_col = self.origin_col
        self.target_row = self.origin_row
        self.moving = False

    # ------------------------------------------------------------------
    def draw(self, surface, images):
        if not self.alive:
            return
        img = images[self.color][self.name]
        if self.name == "Knight" and self.knight_phase is not None:
            img = img.copy()
            img.set_alpha(self.knight_alpha)
        surface.blit(img, (self.pixel_x, self.pixel_y))
        # health bar
        self._draw_hp(surface)

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
        elif ratio > 0.25:
            color = (220, 180, 0)
        else:
            color = (210, 30, 30)
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
    """True if a friendly piece currently occupies or is moving to (col, row)."""
    for p in pieces:
        if p is piece or not p.alive:
            continue
        if p.color != piece.color:
            continue
        if (p.col == col and p.row == row):
            return True
        if p.moving and p.target_col == col and p.target_row == row:
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
        # diagonal captures – allowed only if opponent occupies that tile
        for dc in (-1, 1):
            tc, tr = c + dc, r + direction
            if in_bounds(tc, tr):
                occ = _any_piece_at(pieces, tc, tr, exclude=piece)
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


def _any_piece_at(pieces, col, row, exclude=None):
    for p in pieces:
        if p is exclude or not p.alive:
            continue
        if p.col == col and p.row == row:
            return p
    return None


def _pawn_path_clear(pieces, piece, tc, tr):
    """For pawn forward moves, the target must not contain ANY piece."""
    occ = _any_piece_at(pieces, tc, tr, exclude=piece)
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
    """
    For every piece, collect the set of tiles it 'threatens':
      - its current tile
      - if moving, its next (target) tile
    If any enemy piece's next_tile is in that set, deal damage.
    Symmetric: both can damage each other.
    """
    damage_per_frame = DAMAGE_PER_SECOND * dt

    for p in pieces:
        if not p.alive:
            continue
        # Tiles this piece occupies / claims
        my_tiles = {p.current_tile}
        if p.next_tile:
            my_tiles.add(p.next_tile)

        for q in pieces:
            if q is p or not q.alive or q.color == p.color:
                continue
            # Opponent q's next_tile collides with one of my tiles?
            if q.next_tile and q.next_tile in my_tiles:
                q.hp -= damage_per_frame
                if q.hp <= 0:
                    q.hp = 0
                    q.alive = False


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


def draw_highlights(surface, selected, legal_targets):
    if selected is None:
        return
    # highlight selected tile
    hs = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    hs.fill(HIGHLIGHT_COLOR)
    surface.blit(hs, (selected.col * TILE, selected.row * TILE))
    # draw legal move dots
    for (tc, tr) in legal_targets:
        cx = tc * TILE + TILE // 2
        cy = tr * TILE + TILE // 2
        dot = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        pygame.draw.circle(dot, MOVE_DOT_COLOR, (TILE // 2, TILE // 2), 15)
        surface.blit(dot, (tc * TILE, tr * TILE))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Real-Time Chess")
    clock = pygame.time.Clock()

    base_path = os.path.dirname(os.path.abspath(__file__))
    images = load_piece_images(base_path)
    pieces = create_pieces()

    selected = None        # currently selected Piece (or None)
    legal_targets = []     # list of (col, row)
    game_over = False
    winner = None
    font = pygame.font.SysFont("consolas", 22)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0  # seconds

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not game_over:
                mx, my = event.pos
                click_col = mx // TILE
                click_row = my // TILE
                if not in_bounds(click_col, click_row):
                    selected = None
                    legal_targets = []
                    continue

                # Did we click on a legal target?
                if selected and (click_col, click_row) in legal_targets:
                    selected.start_move(click_col, click_row)
                    selected = None
                    legal_targets = []
                else:
                    # Try to select a piece at this tile
                    clicked_piece = None
                    for p in pieces:
                        if p.alive and not p.moving and p.col == click_col and p.row == click_row:
                            clicked_piece = p
                            break
                    if clicked_piece:
                        selected = clicked_piece
                        legal_targets = get_legal_targets(clicked_piece, pieces)
                    else:
                        selected = None
                        legal_targets = []

        if not game_over:
            # --- Update movement ---
            for p in pieces:
                p.update(dt, pieces)

            # --- Combat ---
            process_combat(pieces, dt)

            # --- Check game over ---
            for p in pieces:
                if p.name == "King" and not p.alive:
                    game_over = True
                    winner = "Black" if p.color == "white" else "White"

            # If selected piece died or started moving, deselect
            if selected and (not selected.alive or selected.moving):
                selected = None
                legal_targets = []

        # --- Draw ---
        draw_board(screen)
        draw_highlights(screen, selected, legal_targets)

        # Draw pieces (alive only)
        for p in pieces:
            p.draw(screen, images)

        # Status bar
        status_rect = pygame.Rect(0, TILE * BOARD, WIDTH, 40)
        pygame.draw.rect(screen, (30, 30, 30), status_rect)
        if game_over:
            txt = font.render(f"{winner} wins!  Press ESC to quit.", True, (255, 255, 100))
        else:
            if selected:
                txt = font.render(f"Selected: {selected.color} {selected.name}", True, (220, 220, 220))
            else:
                txt = font.render("Click a piece to select, then click a target.", True, (180, 180, 180))
        screen.blit(txt, (10, TILE * BOARD + 8))

        pygame.display.flip()

        # ESC to quit
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            running = False

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
