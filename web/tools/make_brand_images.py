"""Render the social preview (og-image.png) and favicons into web/public with pygame.

Run with the same Python that runs the desktop game:  python web/tools/make_brand_images.py
"""
import io
import math
import os
import struct
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

WEB = Path(__file__).resolve().parent.parent
PUBLIC = WEB / "public"
OUT = PUBLIC / "og-image.png"

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


def make_og_image():
    surf = pygame.Surface((W * S, H * S))
    surf.fill(BG)

    for r in range(8):
        for c in range(8):
            pygame.draw.rect(surf, LIGHT if (r + c) % 2 == 0 else DARK,
                             (BX + c * TILE, BY + r * TILE, TILE, TILE))

    for start, end in MOVES:
        arrow(surf, start, end, (40, 100, 220), 0.45)

    for color, name, c, r, ratio in PIECES:
        # SVG loads at its intrinsic 100x100; the final image is downscaled, so this stays sharp.
        img = pygame.image.load(str(WEB / "public" / "pieces" / "war" / name / f"{color}.svg"))
        x, y = BX + int(c * TILE), BY + int(r * TILE)
        surf.blit(pygame.transform.smoothscale(img, (TILE, TILE)), (x, y))
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


def make_icon(size, rounded):
    """Crown on a 2x2 checkerboard with an HP bar, drawn at 512 and downscaled."""
    m = 512
    surf = pygame.Surface((m, m), pygame.SRCALPHA)
    rad = 96 if rounded else 0
    h = m // 2
    pygame.draw.rect(surf, LIGHT, (0, 0, h, h), border_top_left_radius=rad)
    pygame.draw.rect(surf, DARK, (h, 0, h, h), border_top_right_radius=rad)
    pygame.draw.rect(surf, DARK, (0, h, h, h), border_bottom_left_radius=rad)
    pygame.draw.rect(surf, LIGHT, (h, h, h, h), border_bottom_right_radius=rad)

    pygame.draw.polygon(surf, BG, [(88, 352), (88, 160), (172, 250), (256, 116),
                                   (340, 250), (424, 160), (424, 352)])
    for x, y in ((88, 150), (256, 106), (424, 150)):
        pygame.draw.circle(surf, BG, (x, y), 34)
    pygame.draw.rect(surf, BG, (88, 368, 336, 36), border_radius=8)

    pygame.draw.rect(surf, (60, 60, 60), (64, 428, 384, 44), border_radius=10)
    pygame.draw.rect(surf, (0, 200, 0), (64, 428, 288, 44), border_radius=10)
    pygame.draw.rect(surf, (0, 0, 0), (64, 428, 384, 44), 6, border_radius=10)
    return pygame.transform.smoothscale(surf, (size, size))


def png_bytes(surf):
    buf = io.BytesIO()
    pygame.image.save(surf, buf, "png")
    return buf.getvalue()


def write_ico(path, sizes):
    # ICO container holding PNG images (supported by all current browsers).
    images = [png_bytes(make_icon(s, rounded=True)) for s in sizes]
    offset = 6 + 16 * len(images)
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = b""
    for s, data in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + entries + b"".join(images))
    print(f"wrote {path}")


def main():
    pygame.init()
    make_og_image()
    write_ico(PUBLIC / "favicon.ico", [16, 32, 48])
    for name, size, rounded in (("icon-192.png", 192, True), ("apple-touch-icon.png", 180, False)):
        pygame.image.save(make_icon(size, rounded), str(PUBLIC / name))
        print(f"wrote {PUBLIC / name}")


if __name__ == "__main__":
    main()
