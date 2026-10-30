"""Render web/public/og-image.png (1200x630 social link preview) with pygame.

Run with the same Python that runs the desktop game:  python web/tools/make_og_image.py
"""
import math
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

WEB = Path(__file__).resolve().parent.parent
OUT = WEB / "public" / "og-image.png"

W, H = 1200, 630
S = 2  # supersample, then downscale for smooth edges
TILE = 70 * S
BX, BY = 35 * S, 35 * S

BG = (24, 26, 32)
LIGHT, DARK = (240, 217, 181), (181, 136, 99)
TEXT, SUB, MUTED, ACCENT = (235, 235, 245), (200, 205, 215), (140, 145, 155), (110, 160, 230)

# (color, name, col, row, hp_ratio); fractional col/row = mid-slide.
PIECES = [
    ("black", "Rook", 0, 0, 1.0), ("black", "King", 4, 0, 1.0), ("black", "Bishop", 5, 0, 1.0),
    ("black", "Rook", 7, 0, 0.7), ("black", "Pawn", 0, 1, 1.0), ("black", "Pawn", 1, 1, 1.0),
    ("black", "Pawn", 5, 1, 1.0), ("black", "Pawn", 6, 1, 1.0), ("black", "Pawn", 7, 1, 1.0),
    ("black", "Knight", 2, 2, 0.35), ("black", "Queen", 3, 3, 0.55), ("black", "Knight", 6, 2, 1.0),
    ("white", "Pawn", 1, 3, 1.0), ("white", "Pawn", 4, 4, 0.18), ("white", "Knight", 2, 5, 0.9),
    ("white", "Queen", 4.4, 5.6, 0.8), ("white", "Pawn", 0, 6, 1.0), ("white", "Pawn", 5, 6, 1.0),
    ("white", "Pawn", 6, 6, 1.0), ("white", "Pawn", 7, 6, 1.0), ("white", "Rook", 0, 7, 1.0),
    ("white", "Bishop", 2, 7, 1.0), ("white", "King", 4, 7, 1.0), ("white", "Rook", 7, 7, 0.6),
]
ATTACKS = [((1, 3), (2, 2)), ((3, 3), (4, 4))]  # red: attacker -> target
MOVES = [((3, 7), (7, 3))]  # blue: origin -> destination


def center(c, r):
    return BX + c * TILE + TILE // 2, BY + r * TILE + TILE // 2


def arrow(surf, start, end, color, spread):
    (sx, sy), (ex, ey) = center(*start), center(*end)
    pygame.draw.line(surf, color, (sx, sy), (ex, ey), 4 * S)
    ang = math.atan2(ey - sy, ex - sx)
    for sign in (1, -1):
        hx = ex - 16 * S * math.cos(ang + sign * spread)
        hy = ey - 16 * S * math.sin(ang + sign * spread)
        pygame.draw.line(surf, color, (ex, ey), (hx, hy), 4 * S)


def hp_bar(surf, x, y, ratio):
    bw, bh = TILE - 10 * S, 5 * S
    bx, by = x + 5 * S, y + TILE - 9 * S
    pygame.draw.rect(surf, (60, 60, 60), (bx, by, bw, bh))
    color = (0, 200, 0) if ratio > 0.5 else (220, 140, 0) if ratio > 0.2 else (210, 30, 30)
    pygame.draw.rect(surf, color, (bx, by, int(bw * ratio), bh))
    pygame.draw.rect(surf, (0, 0, 0), (bx, by, bw, bh), S)


def main():
    pygame.init()
    surf = pygame.Surface((W * S, H * S))
    surf.fill(BG)

    for r in range(8):
        for c in range(8):
            pygame.draw.rect(surf, LIGHT if (r + c) % 2 == 0 else DARK,
                             (BX + c * TILE, BY + r * TILE, TILE, TILE))

    for start, end in MOVES:
        arrow(surf, start, end, (40, 100, 220), 0.45)

    for color, name, c, r, ratio in PIECES:
        img = pygame.image.load(WEB / "public" / "pieces" / name / f"{color}.png")
        w = int(TILE * 0.7) if name in ("Pawn", "Rook") else TILE
        x, y = BX + int(c * TILE), BY + int(r * TILE)
        surf.blit(pygame.transform.smoothscale(img, (w, TILE)), (x + (TILE - w) // 2, y))
        hp_bar(surf, x, y, ratio)

    for start, end in ATTACKS:
        arrow(surf, start, end, (220, 30, 30), 0.8)

    def font(size, bold=False):
        return pygame.font.SysFont("consolas,dejavusansmono,couriernew", size * S, bold=bold)

    tx = 650 * S
    title = font(76, bold=True)
    surf.blit(title.render("Real-Time", True, TEXT), (tx, 70 * S))
    surf.blit(title.render("Chess", True, TEXT), (tx, 150 * S))

    sub = font(30)
    for i, line in enumerate(["No turns.", "Pieces have HP.", "Destroy the enemy King."]):
        y = (275 + i * 50) * S
        pygame.draw.circle(surf, ACCENT, (tx + 8 * S, y + 17 * S), 6 * S)
        surf.blit(sub.render(line, True, SUB), (tx + 30 * S, y))

    surf.blit(font(22).render("Free in your browser. vs AI or a friend.", True, MUTED), (tx, 470 * S))
    surf.blit(font(34, bold=True).render("real-time-chess.com", True, ACCENT), (tx, 530 * S))

    pygame.image.save(pygame.transform.smoothscale(surf, (W, H)), str(OUT))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
