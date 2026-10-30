"""Render the social preview (og-image.png), favicons and portal covers with pygame.

Run with the same Python that runs the desktop game:  python web/tools/make_brand_images.py
Covers (title-only text, no borders/logos, per CrazyGames rules) go to web/portals/covers/.
"""
import io
import math
import os
import random
import struct
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

import make_pieces as pieces  # noqa: E402  (same folder: shared palette and shapes)

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


# --- Portal covers -------------------------------------------------------------

COVERS = WEB / "portals" / "covers"
BLUE, RED, GOLD = (63, 127, 217), (217, 67, 63), (246, 201, 69)


def piece_image(color, name, size):
    """War-band piece rendered from its SVG at *size* px (sharp, not upscaled)."""
    return svg_image((PUBLIC / "pieces" / "war" / name / f"{color}.svg").read_text(), size)


def svg_image(svg, size):
    """Renders a 100x100-viewBox SVG at *size* px."""
    svg = svg.replace('width="100" height="100"', f'width="{size}" height="{size}"', 1)
    # SDL_image's SVG loader ignores viewBox scaling, so scale the drawing explicitly.
    head, body = svg.split(">", 1)
    svg = f'{head}><g transform="scale({size / 100})">{body.replace("</svg>", "</g></svg>")}'
    return pygame.image.load(io.BytesIO(svg.encode()), "piece.svg")


def king_back_svg(color):
    """The war-band King seen from behind: cape, crown, mustache tips, sword raised."""
    p = pieces.PALETTES[color]
    g = p["gold"]
    crown = (f'<rect x="46.5" y="4" width="7" height="18" rx="2.5" fill="{g}"/>'
             f'<rect x="41" y="8.5" width="18" height="7" rx="2.5" fill="{g}"/>'
             f'<path d="M31,39 L31,23 L40,31 L50,21 L60,31 L69,23 L69,39 Z" fill="{g}"/>')
    tips = "".join(f'<path d="M{50 + side * 23},{63} q{side * 8},{-1} {side * 9},{6} q{-side * 4},{-3} {-side * 9},{-2} Z" '
                   f'fill="{p["stache"]}" stroke-width="1.6"/>' for side in (-1, 1))
    sword = (pieces.pole(p, 72, 66, 82, 44, 4)
             + f'<path d="M80,46 L93,8 L98,11 L86,48 Z" fill="{p["steel"]}"/>'
             f'<path d="M76,41 L91,50" stroke="{g}" stroke-width="5.5"/>'
             f'<circle cx="73" cy="64" r="5.5" fill="{p["body"]}"/>')
    body = (f'<path d="M24,88 C26,64 36,60 50,60 C64,60 74,64 76,88 Z" fill="{p["team"]}"/>'
            f'<path d="M50,64 V86 M40,68 L36,86 M60,68 L64,86" stroke="{p["line"]}" stroke-width="1.4" opacity="0.35"/>'
            + tips
            + f'<circle cx="50" cy="54" r="23" fill="{p["body"]}"/>'
            + crown + pieces.shine(42, 46, 6, 4) + sword + pieces.base(p))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
            f'<g stroke="{p["line"]}" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round">'
            f'{body}</g></svg>')


def side_svg(color, body):
    p = pieces.PALETTES[color]
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
            f'<g stroke="{p["line"]}" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round">'
            f'{body}</g></svg>')


def profile_face(p, ex, ey, front, s=1.0, mustache=False, mouth="grit"):
    """Angry face seen from the side, looking right; *front* is the head's right edge."""
    parts = [pieces.eye(p, ex, ey, 3.8 * s, 4.6 * s),
             f'<ellipse cx="{ex - 5 * s}" cy="{ey + 8 * s}" rx="{4 * s}" ry="{2.4 * s}" fill="{p["blush"]}" opacity="0.45"/>',
             f'<path d="M{ex - 5 * s},{ey - 9 * s} L{ex + 5 * s},{ey - 4.5 * s}" stroke="{p["line"]}" stroke-width="{3.6 * s}"/>',
             f'<path d="M{front - 1},{ey + 1 * s} q{5 * s},{2 * s} {0.5 * s},{6 * s}" fill="{p["body"]}" stroke="{p["line"]}" stroke-width="2.4"/>']
    my = ey + 11 * s
    if mustache:
        parts.append(f'<path d="M{front - 10 * s},{my - 3 * s} c{6 * s},{-3 * s} {12 * s},{-3 * s} {15 * s},{2 * s} '
                     f'c{-4 * s},{-1 * s} {-8 * s},{0} {-11 * s},{3 * s} Z" fill="{p["stache"]}" stroke="{p["line"]}" stroke-width="1.4"/>')
        my += 3 * s
    if mouth == "grit":
        parts.append(f'<rect x="{front - 9 * s}" y="{my - 2.5 * s}" width="{7 * s}" height="{5 * s}" rx="{1.5 * s}" '
                     f'fill="{p["teeth"]}" stroke="{p["line"]}" stroke-width="1.4"/>'
                     f'<path d="M{front - 9 * s},{my} H{front - 2 * s} M{front - 5.5 * s},{my - 2.5 * s} V{my + 2.5 * s}" '
                     f'stroke="{p["line"]}" stroke-width="0.9"/>')
    else:  # battle cry
        parts.append(f'<ellipse cx="{front - 5 * s}" cy="{my + 1 * s}" rx="{4 * s}" ry="{4.5 * s}" fill="#5a1f2b" '
                     f'stroke="{p["line"]}" stroke-width="1.4"/>')
    return '<g stroke="none">' + "".join(parts) + "</g>"


def king_side_svg(color):
    """War-band King in profile, charging right: cape streaming back, sword thrust forward."""
    p = pieces.PALETTES[color]
    g = p["gold"]
    cape = f'<path d="M44,60 C30,62 14,70 6,86 C18,82 30,86 40,90 L52,88 Z" fill="{p["team"]}"/>'
    robe = f'<path d="M30,88 C32,70 42,66 54,66 C66,66 72,72 74,88 Z" fill="{p["team"]}"/>'
    head = f'<circle cx="52" cy="50" r="22" fill="{p["body"]}"/>'
    crown = (f'<path d="M33,35 L34,19 L43,27 L52,16 L61,27 L70,19 L71,35 Z" fill="{g}"/>'
             f'<rect x="49" y="2" width="6" height="16" rx="2" fill="{g}"/>'
             f'<rect x="44.5" y="6" width="15" height="6" rx="2" fill="{g}"/>')
    sword = (pieces.pole(p, 62, 74, 74, 68, 4)
             + f'<path d="M74,64 L99,50 L99,56 L77,71 Z" fill="{p["steel"]}"/>'
             f'<path d="M72,60 L78,74" stroke="{g}" stroke-width="5.5"/>'
             f'<circle cx="62" cy="74" r="5.5" fill="{p["body"]}"/>')
    return side_svg(color, cape + robe + head + crown + pieces.shine(44, 40, 5, 4)
                    + profile_face(p, 63, 49, 74, mustache=True) + sword + pieces.base(p))


def pawn_side_svg(color):
    """War-band Pawn in profile, charging right with its spear levelled."""
    p = pieces.PALETTES[color]
    spear = (pieces.pole(p, 14, 74, 86, 52)
             + f'<path d="M84,48 L99,47 L88,58 Z" fill="{p["steel"]}"/>'
             f'<path d="M80,51 L84,58" stroke="{p["team"]}" stroke-width="3"/>')
    body = f'<path d="M31,84 C31,66 40,58 50,58 C60,58 69,66 69,84 Z" fill="{p["body"]}"/>'
    head = f'<circle cx="50" cy="45" r="18" fill="{p["body"]}"/>'
    helmet = (f'<path d="M31,40 C31,25 40,19 50,19 C60,19 69,25 69,40 Z" fill="{p["steel"]}"/>'
              f'<path d="M28,40 H74" stroke="{p["line"]}" stroke-width="7"/>'
              f'<path d="M28,40 H74" stroke="{p["steel"]}" stroke-width="3.6"/>')
    return side_svg(color, pieces.round_shield(p, 32, 70, 11) + body + head + helmet
                    + profile_face(p, 59, 47, 68, s=0.8, mouth="shout") + spear + pieces.base(p, 46))


def glow(surf, center, radius, color, strength=110):
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for i in range(40, 0, -1):
        a = int(strength * (1 - i / 40) ** 2 / 6)
        pygame.draw.circle(layer, (*color, a), center, int(radius * i / 40))
    surf.blit(layer, (0, 0))


def floor(surf, horizon, cx, tile):
    """Perspective checkerboard from the horizon to the bottom edge, fading into the distance."""
    w, h = surf.get_size()
    depth = 0.55
    project = lambda u, v: (cx + u * tile / (1 + v * depth), horizon + (h - horizon) / (1 + v * depth))
    for v in range(14, -1, -1):
        fade = 1 / (1 + v * 0.35)
        for u in range(-16, 16):
            base = LIGHT if (u + v) % 2 == 0 else DARK
            col = tuple(int(c * (0.35 + 0.65 * fade)) for c in base)
            pygame.draw.polygon(surf, col, [project(u, v), project(u + 1, v), project(u + 1, v + 1), project(u, v + 1)])
    # Darken toward the horizon so the pieces pop.
    haze = pygame.Surface((w, h - horizon), pygame.SRCALPHA)
    for y in range(h - horizon):
        a = int(200 * (1 - y / (h - horizon)) ** 3)
        pygame.draw.line(haze, (20, 22, 30, a), (0, y), (w, y))
    surf.blit(haze, (0, horizon))


def place(surf, color, name, x, feet_y, size, flip=False, hp=None, angle=0.0, img=None):
    """Piece standing on the floor at (x, feet_y), with a soft shadow and optional HP bar.
    *angle* leans the piece (degrees, positive = counter-clockwise)."""
    img = img or piece_image(color, name, size)
    if flip:
        img = pygame.transform.flip(img, True, False)
    shadow = pygame.Surface((int(size * 0.7), int(size * 0.14)), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 110), shadow.get_rect())
    surf.blit(shadow, (x - shadow.get_width() // 2, feet_y - shadow.get_height() // 2))
    if angle:
        rotated = pygame.transform.rotozoom(img, angle, 1.0)
        center = (x, feet_y - int(size * 0.9) + size // 2)
        surf.blit(rotated, rotated.get_rect(center=center))
    else:
        surf.blit(img, (x - size // 2, feet_y - int(size * 0.9)))
    if hp is not None:
        bw, bh = int(size * 0.6), max(6, size // 22)
        bx, by = x - bw // 2, feet_y - int(size * 0.9) - bh - int(size * 0.01)
        pygame.draw.rect(surf, (40, 40, 46), (bx, by, bw, bh), border_radius=bh // 2)
        fill = (0, 200, 0) if hp > 0.5 else (220, 140, 0)
        pygame.draw.rect(surf, fill, (bx, by, int(bw * hp), bh), border_radius=bh // 2)
        pygame.draw.rect(surf, (10, 10, 14), (bx, by, bw, bh), max(2, bh // 4), border_radius=bh // 2)


def clash(surf, center, r):
    """Spark burst where the two armies meet."""
    cx, cy = center
    for k, (rad, col) in enumerate(((r, (255, 170, 40)), (r * 0.62, (255, 230, 120)), (r * 0.3, (255, 255, 235)))):
        pts = []
        for i in range(24):
            a = i * math.pi / 12 + k * 0.13
            d = rad if i % 2 == 0 else rad * 0.42
            pts.append((cx + math.cos(a) * d, cy + math.sin(a) * d))
        pygame.draw.polygon(surf, col, pts)
    for i in range(10):
        a = i * 2 * math.pi / 10 + 0.3
        d = r * 1.35
        pygame.draw.circle(surf, (255, 220, 120), (cx + math.cos(a) * d, cy + math.sin(a) * d), max(3, r // 14))


def title(surf, lines, size, top):
    """Big outlined title, centred; the only text allowed on covers."""
    font = pygame.font.SysFont("impact,arialblack,dejavusans", size, bold=False)
    y = top
    for line in lines:
        text = font.render(line, True, (255, 244, 214))
        outline = font.render(line, True, (16, 14, 22))
        x = (surf.get_width() - text.get_width()) // 2
        t = max(3, size // 18)
        for dx in range(-t, t + 1, max(1, t // 2)):
            for dy in range(-t, t + 1, max(1, t // 2)):
                surf.blit(outline, (x + dx, y + dy + t // 2))
        surf.blit(text, (x, y))
        y += int(size * 0.98)


def backdrop(surf):
    W2, H2 = surf.get_size()
    for y in range(H2):
        t = y / H2
        pygame.draw.line(surf, (int(18 + 20 * t), int(19 + 18 * t), int(26 + 26 * t)), (0, y), (W2, y))


def speed_lines_radial(surf, center, r0, r1, rng, count=70):
    """Zoom-style streaks bursting out from *center* (a charge toward the camera)."""
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    cx, cy = center
    for _ in range(count):
        a = rng.uniform(0, 2 * math.pi)
        start = rng.uniform(r0, r0 * 1.6)
        end = start + rng.uniform(0.35, 1.0) * (r1 - r0)
        w = rng.uniform(0.006, 0.018) * r1
        p1 = (cx + math.cos(a) * start, cy + math.sin(a) * start)
        pa = (cx + math.cos(a + w / end) * end, cy + math.sin(a + w / end) * end)
        pb = (cx + math.cos(a - w / end) * end, cy + math.sin(a - w / end) * end)
        pygame.draw.polygon(layer, (255, 236, 200, rng.randint(40, 110)), [p1, pa, pb])
    surf.blit(layer, (0, 0))


def speed_lines_side(surf, x, top, bottom, length, direction, rng, count=26):
    """Horizontal streaks trailing behind a piece charging in *direction* (+1 right, -1 left)."""
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for _ in range(count):
        y = rng.uniform(top, bottom)
        x0 = x - direction * rng.uniform(0, length * 0.25)
        x1 = x0 - direction * rng.uniform(0.4, 1.0) * length
        th = max(2, int(rng.uniform(0.002, 0.006) * length))
        pygame.draw.line(layer, (255, 236, 200, rng.randint(40, 100)), (x0, y), (x1, y), th)
    surf.blit(layer, (0, 0))


def dust(surf, x, y, size, rng, direction=0, count=14):
    """Puffs kicked up at a charging piece's feet, drifting opposite to *direction*."""
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for _ in range(count):
        dx = rng.uniform(-0.5, 0.5) * size - direction * rng.uniform(0, 0.6) * size
        dy = rng.uniform(-0.12, 0.05) * size
        r = rng.uniform(0.05, 0.13) * size
        pygame.draw.circle(layer, (205, 180, 150, rng.randint(60, 120)), (x + dx, y + dy), r)
    surf.blit(layer, (0, 0))


def finish(surf, w, h, lines_landscape=("REAL-TIME CHESS",), lines_tall=("REAL-TIME", "CHESS")):
    W2, H2 = surf.get_size()
    if w > h:
        title(surf, list(lines_landscape), int(H2 * 0.15), int(H2 * 0.05))
    else:
        title(surf, list(lines_tall), int(W2 * (0.18 if h > w else 0.16)), int(H2 * 0.04))
    return pygame.transform.smoothscale(surf, (w, h))


# Cover: "Charge" -------------------------------------------------------------

def cover_charge(w, h):
    rng = random.Random(7)
    s = 2
    W2, H2 = w * s, h * s
    surf = pygame.Surface((W2, H2))
    backdrop(surf)

    if h > w:
        # Over the White King's shoulder: the Black King charges straight at the camera.
        horizon = int(H2 * 0.42)
        bk_x, bk_feet, bk = int(W2 * 0.6), int(H2 * 0.68), int(W2 * 0.5)
        glow(surf, (bk_x, bk_feet - bk // 2), int(bk * 1.5), RED, 150)
        floor(surf, horizon, W2 // 2, int(W2 / 6))
        speed_lines_radial(surf, (bk_x, bk_feet - int(bk * 0.45)), bk * 0.55, W2 * 0.9, rng)
        place(surf, "black", "Pawn", int(W2 * 0.27), int(H2 * 0.57), int(W2 * 0.22), angle=4)
        place(surf, "black", "Rook", int(W2 * 0.88), int(H2 * 0.56), int(W2 * 0.24), angle=-4)
        dust(surf, bk_x, bk_feet, bk, rng)
        place(surf, "black", "King", bk_x, bk_feet, bk, hp=0.55, angle=-6)
        glow(surf, (int(W2 * 0.3), H2), int(W2 * 0.7), BLUE, 120)
        place(surf, "white", "King", int(W2 * 0.3), int(H2 * 1.1), int(W2 * 0.95),
              img=svg_image(king_back_svg("white"), int(W2 * 0.95)))
    else:
        # Side view: both Kings charge in from the edges and collide in the middle.
        horizon = int(H2 * 0.56)
        king = int(min(W2, H2) * (0.6 if w > h else 0.5))
        gap = int(W2 * (0.13 if w > h else 0.17))
        feet = int(H2 * 0.9)
        glow(surf, (W2 // 2 - gap, horizon), int(king * 1.4), BLUE, 130)
        glow(surf, (W2 // 2 + gap, horizon), int(king * 1.4), RED, 130)
        floor(surf, horizon, W2 // 2, int(W2 / 9))
        soldier = int(king * 0.5)
        back = feet - int(king * 0.28)
        # Profiles face right; the Black army is mirrored so the two sides face each other.
        for side, color in ((-1, "white"), (1, "black")):
            for i, name in enumerate(("Pawn", "Knight")):
                sx = W2 // 2 + side * (gap + int(king * (0.6 + 0.3 * i)))
                speed_lines_side(surf, sx, back - soldier * 0.8, back - soldier * 0.1, soldier * 1.2, -side, rng, 8)
                img = svg_image(pawn_side_svg(color), soldier) if name == "Pawn" else piece_image(color, name, soldier)
                # The game's Knight looks left, the drawn profiles look right.
                flip = (side == 1) if name == "Pawn" else (side == -1)
                place(surf, color, name, sx, back, soldier, flip=flip, angle=side * 8, img=img)
            kx = W2 // 2 + side * gap
            speed_lines_side(surf, kx, feet - king * 0.85, feet - king * 0.1, king * 1.4, -side, rng)
            dust(surf, kx, feet, king, rng, direction=-side)
        place(surf, "white", "King", W2 // 2 - gap, feet, king, hp=0.8, angle=-12,
              img=svg_image(king_side_svg("white"), king))
        place(surf, "black", "King", W2 // 2 + gap, feet, king, flip=True, hp=0.45, angle=12,
              img=svg_image(king_side_svg("black"), king))
        clash(surf, (W2 // 2, feet - int(king * 0.55)), int(king * 0.2))
    return finish(surf, w, h)


def main():
    pygame.init()
    make_og_image()
    write_ico(PUBLIC / "favicon.ico", [16, 32, 48])
    for name, size, rounded in (("icon-192.png", 192, True), ("apple-touch-icon.png", 180, False)):
        pygame.image.save(make_icon(size, rounded), str(PUBLIC / name))
        print(f"wrote {PUBLIC / name}")
    COVERS.mkdir(parents=True, exist_ok=True)
    for w, h in ((1920, 1080), (800, 1200), (800, 800)):
        path = COVERS / f"cover-{w}x{h}.png"
        pygame.image.save(cover_charge(w, h), str(path))
        print(f"wrote {path}")
    # Opening frames for the preview videos (the cover at video resolution).
    for w, h in ((1920, 1080), (1080, 1620)):
        path = WEB / "tools" / "video" / f"intro-{w}x{h}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(cover_charge(w, h), str(path))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
