"""Generate the piece sets as SVGs into web/public/pieces/<set>/<Name>/<color>.svg.

Sets: "war" (chibi war band) and "classic" (Staunton-style silhouettes).
Run:  python3 web/tools/make_pieces.py   (no dependencies)
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "public" / "pieces"

# "team" is the army colour (banners, capes, manes, shields).
PALETTES = {
    "white": dict(body="#fbf6ec", shade="#e6dccb", line="#3a3340", eye="#2b2433", hi="#ffffff",
                  mouth="#3a3340", teeth="#ffffff", blush="#ff9eb5", gold="#f6c945", stache="#7a5434",
                  steel="#d3dae4", wood="#a8743f", team="#3f7fd9"),
    "black": dict(body="#4a4159", shade="#362f42", line="#17131d", eye="#fff7e8", hi="#ffffff", pupil="#17131d",
                  mouth="#fff7e8", teeth="#fff7e8", blush="#ff8fab", gold="#f2b632", stache="#d9d0e6",
                  steel="#8a849e", wood="#7a5230", team="#d9433f"),
}


def eye(p, x, y, rx, ry):
    """Dark eye with a glint, or (light palettes) a light eye with a centred pupil."""
    out = f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" fill="{p["eye"]}"/>'
    if "pupil" in p:
        out += f'<ellipse cx="{x}" cy="{y + ry * 0.12}" rx="{rx * 0.6}" ry="{ry * 0.62}" fill="{p["pupil"]}"/>'
    return out + f'<circle cx="{x + rx * 0.3}" cy="{y - ry * 0.18}" r="{rx * 0.3}" fill="{p["hi"]}"/>'


def face(p, cx, cy, s=1.0, mouth="grit", lashes=False, mustache=False, scar=False):
    ey = cy + 0.8 * s
    parts = []
    for side in (-1, 1):
        x = cx + side * 9 * s
        parts.append(eye(p, x, ey, 3.8 * s, 4.4 * s))
        parts.append(f'<ellipse cx="{cx + side * 16 * s}" cy="{cy + 6 * s}" rx="{4 * s}" ry="{2.4 * s}" '
                     f'fill="{p["blush"]}" opacity="0.45"/>')
        if lashes:
            parts.append(f'<path d="M{x + side * 3.6 * s},{ey - 1.5 * s} l{side * 3 * s},{-1.2 * s}" '
                         f'stroke="{p["eye"]}" stroke-width="{1.5 * s}" fill="none"/>')
        # Angry brow: inner end low, overlapping the top of the eye.
        parts.append(f'<path d="M{x + side * 5.5 * s},{ey - 8 * s} L{x - side * 4.5 * s},{ey - 3.6 * s}" '
                     f'stroke="{p["line"]}" stroke-width="{3.4 * s}" fill="none"/>')
    my = cy + 8 * s
    if mustache:
        parts.append(f'<path d="M{cx},{my - 3 * s} c{-3 * s},{-2 * s} {-9 * s},{-2 * s} {-12 * s},{5 * s} '
                     f'c{4 * s},{-2 * s} {8 * s},{-2.5 * s} {12 * s},{-2 * s} c{4 * s},{-0.5 * s} {8 * s},0 '
                     f'{12 * s},{2 * s} c{-3 * s},{-7 * s} {-9 * s},{-7 * s} {-12 * s},{-5 * s} Z" '
                     f'fill="{p["stache"]}" stroke="{p["line"]}" stroke-width="{1.2 * s}"/>')
        my += 3 * s
    if mouth == "grit":
        w, h = 12 * s, 5.5 * s
        parts.append(f'<rect x="{cx - w / 2}" y="{my - h / 2}" width="{w}" height="{h}" rx="{2 * s}" '
                     f'fill="{p["teeth"]}" stroke="{p["line"]}" stroke-width="{1.6 * s}"/>')
        parts.append(f'<path d="M{cx - w / 2},{my} H{cx + w / 2} M{cx - 2 * s},{my - h / 2} V{my + h / 2} '
                     f'M{cx + 2 * s},{my - h / 2} V{my + h / 2}" stroke="{p["line"]}" stroke-width="{1 * s}"/>')
    elif mouth == "shout":
        parts.append(f'<ellipse cx="{cx}" cy="{my + 1 * s}" rx="{5 * s}" ry="{4.6 * s}" fill="#5a1f2b" '
                     f'stroke="{p["line"]}" stroke-width="{1.6 * s}"/>')
        parts.append(f'<ellipse cx="{cx}" cy="{my + 3.4 * s}" rx="{3 * s}" ry="{1.6 * s}" fill="#ff6b81"/>')
        parts.append(f'<rect x="{cx - 3.2 * s}" y="{my - 3 * s}" width="{6.4 * s}" height="{2 * s}" '
                     f'rx="{0.8 * s}" fill="{p["teeth"]}"/>')
    elif mouth == "frown":
        parts.append(f'<path d="M{cx - 4.5 * s},{my + 2.5 * s} q{4.5 * s},{-4.5 * s} {9 * s},0" '
                     f'stroke="{p["mouth"]}" stroke-width="{2.2 * s}" fill="none"/>')
    elif mouth == "smirk":
        parts.append(f'<path d="M{cx - 4.5 * s},{my + 1.5 * s} q{5 * s},{1.5 * s} {9 * s},{-3 * s}" '
                     f'stroke="{p["mouth"]}" stroke-width="{2.2 * s}" fill="none"/>')
    if scar:
        sx, sy = cx + 13 * s, cy - 9 * s
        parts.append(f'<path d="M{sx},{sy} l{5 * s},{9 * s} M{sx},{sy + 4 * s} l{4 * s},{-1.5 * s} '
                     f'M{sx + 2 * s},{sy + 7.5 * s} l{4 * s},{-1.5 * s}" stroke="#c0495b" '
                     f'stroke-width="{1.5 * s}" fill="none"/>')
    return '<g stroke="none">' + "".join(parts) + "</g>"


def base(p, w=56):
    x = 50 - w / 2
    return (f'<rect x="{x}" y="80" width="{w}" height="12" rx="6" fill="{p["body"]}"/>'
            f'<rect x="{x + 4}" y="86" width="{w - 8}" height="4" rx="2" fill="{p["shade"]}" stroke="none"/>')


def shine(cx, cy, rx, ry):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#ffffff" opacity="0.35" stroke="none"/>'


def pole(p, x1, y1, x2, y2, w=3.4):
    """Outlined stick (spear shaft, sword grip, mace handle)."""
    return (f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{p["line"]}" stroke-width="{w + 3.2}" fill="none"/>'
            f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{p["wood"]}" stroke-width="{w}" fill="none"/>')


def spear(p, x, top, bottom):
    return (pole(p, x, top, x, bottom)
            + f'<path d="M{x},{top - 13} L{x + 5.5},{top} L{x},{top + 3} L{x - 5.5},{top} Z" fill="{p["steel"]}"/>'
            f'<path d="M{x - 4},{top + 4} L{x + 4},{top + 4}" stroke="{p["team"]}" stroke-width="3"/>')


def round_shield(p, cx, cy, r):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{p["team"]}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.62}" fill="none" stroke="{p["steel"]}" stroke-width="2"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.28}" fill="{p["steel"]}" stroke-width="1.5"/>')


def heater_shield(p, cx, top, w, h):
    x0, x1 = cx - w / 2, cx + w / 2
    return (f'<path d="M{x0},{top} H{x1} V{top + h * 0.45} C{x1},{top + h * 0.8} {cx + w * 0.15},{top + h * 0.95} '
            f'{cx},{top + h} C{cx - w * 0.15},{top + h * 0.95} {x0},{top + h * 0.8} {x0},{top + h * 0.45} Z" '
            f'fill="{p["team"]}"/>'
            f'<path d="M{cx},{top + 4} V{top + h - 5} M{x0 + 4},{top + h * 0.38} H{x1 - 4}" '
            f'stroke="{p["gold"]}" stroke-width="3.4" fill="none"/>')


def pawn(p):
    helmet = (f'<path d="M30,38 C30,22 39,16 50,16 C61,16 70,22 70,38 Z" fill="{p["steel"]}"/>'
              f'<rect x="25" y="34" width="50" height="7" rx="3.5" fill="{p["steel"]}"/>'
              f'<path d="M50,17 V33" stroke="{p["line"]}" stroke-width="1.6" opacity="0.5"/>')
    return (spear(p, 76, 18, 88)
            + f'<path d="M31,84 C31,66 40,58 50,58 C60,58 69,66 69,84 Z" fill="{p["body"]}"/>'
            f'<circle cx="50" cy="44" r="18" fill="{p["body"]}"/>'
            + helmet + shine(41, 24, 5, 3) + face(p, 50, 47, 0.8, mouth="shout")
            + round_shield(p, 33, 72, 10) + base(p, 46))


def rook(p):
    flag = (pole(p, 50, 3, 50, 20, 2.6)
            + f'<path d="M51.5,3 L70,7.5 L64,10.5 L70,14 L51.5,14 Z" fill="{p["team"]}"/>')
    merlons = "".join(f'<rect x="{x}" y="18" width="13" height="16" rx="3" fill="{p["body"]}"/>'
                      for x in (25, 43.5, 62))
    return (flag + merlons
            + f'<rect x="25" y="29" width="50" height="11" rx="3" fill="{p["team"]}"/>'
            f'<rect x="29" y="38" width="42" height="46" rx="8" fill="{p["body"]}"/>'
            f'<path d="M33,47 l4,4 l-3,3 l4,4" stroke="{p["line"]}" stroke-width="1.6" fill="none" opacity="0.6"/>'
            + face(p, 50, 59, scar=True) + base(p))


def knight(p):
    mane = "".join(f'<circle cx="{x}" cy="{y}" r="7" fill="{p["team"]}"/>'
                   for x, y in ((70, 24), (76, 36), (78, 50), (77, 64), (74, 76)))
    puffs = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ffffff" opacity="0.85" stroke="none"/>'
                    for x, y, r in ((12, 47, 3.5), (8, 41, 3), (13, 37, 2.5)))
    return (mane
            + f'<path d="M58,24 L60,6 L69,22 Z" fill="{p["body"]}"/>'
            f'<path d="M32,84 C32,72 36,64 43,59 C34,61 24,59 20,51 C16,42 23,33 34,29 '
            f'C41,23 49,19 57,19 C69,19 75,32 75,48 C75,62 71,72 71,84 Z" fill="{p["body"]}"/>'
            # Steel chanfron plate down the face, with a team-colour plume on top.
            f'<path d="M57,21 C49,21 40,25 33,31 L38,37 C44,32 51,29 59,28 Z" fill="{p["steel"]}"/>'
            f'<path d="M58,20 C58,12 63,8 68,9 C65,12 63,16 62,21 Z" fill="{p["team"]}"/>'
            + puffs
            + f'<g stroke="none">' + eye(p, 48, 41, 4.6, 5.2)
            + f'<path d="M41,32 L54,37.5" stroke="{p["line"]}" stroke-width="3.6"/>'
            f'<ellipse cx="44" cy="51" rx="4.2" ry="2.4" fill="{p["blush"]}" opacity="0.45"/>'
            f'<ellipse cx="23.5" cy="44.5" rx="1.6" ry="2.4" fill="{p["line"]}"/>'
            f'<rect x="21" y="50.5" width="10" height="5" rx="1.8" fill="{p["teeth"]}" stroke="{p["line"]}" '
            f'stroke-width="1.5"/>'
            f'<path d="M21,53 H31 M24.5,50.5 V55.5 M27.5,50.5 V55.5" stroke="{p["line"]}" stroke-width="1"/></g>'
            + base(p))


def bishop(p):
    spikes = "".join(f'<path d="M{78 + 8 * dx},{22 + 8 * dy} L{78 + 13 * dx},{22 + 13 * dy}" '
                     f'stroke="{p["line"]}" stroke-width="3.4"/>'
                     for dx, dy in ((1, 0), (-1, 0), (0, -1), (0.7, -0.7), (-0.7, -0.7), (0.7, 0.7)))
    mace = (pole(p, 78, 86, 78, 28)
            + spikes + f'<circle cx="78" cy="22" r="8.5" fill="{p["steel"]}"/>')
    return (mace
            + f'<circle cx="50" cy="13" r="5.5" fill="{p["team"]}"/>'
            f'<path d="M50,19 C66,30 73,46 73,60 C73,75 63,84 50,84 C37,84 27,75 27,60 '
            f'C27,46 34,30 50,19 Z" fill="{p["body"]}"/>'
            f'<path d="M55,29 L63,42" stroke="{p["line"]}" stroke-width="3" fill="none"/>'
            f'<path d="M30.5,72 C40,77 60,77 69.5,72" stroke="{p["team"]}" stroke-width="5" fill="none"/>'
            + shine(38, 44, 3.5, 6) + face(p, 50, 58, mouth="frown") + base(p, 50))


def crowned(p, crown, back="", front="", **face_kw):
    return (back
            + f'<path d="M27,86 C29,72 39,68 50,68 C61,68 71,72 73,86 Z" fill="{p["team"]}"/>'
            f'<circle cx="50" cy="54" r="23" fill="{p["body"]}"/>'
            + crown + shine(40, 44, 5, 4) + face(p, 50, 56, **face_kw) + front + base(p))


def queen(p):
    g = p["gold"]
    crown = (f'<path d="M31,38 L34,20 L42,30 L50,15 L58,30 L66,20 L69,38 Z" fill="{g}"/>'
             + "".join(f'<circle cx="{x}" cy="{y}" r="3.6" fill="{g}"/>' for x, y in ((34, 19), (50, 14), (66, 19))))
    sword = (f'<path d="M80,6 L84.5,13 L84.5,62 L75.5,62 L75.5,13 Z" fill="{p["steel"]}"/>'
             f'<path d="M80,14 V58" stroke="{p["line"]}" stroke-width="1.2" opacity="0.4"/>'
             + pole(p, 80, 67, 80, 76, 4)
             + f'<rect x="70" y="61" width="20" height="5.5" rx="2.5" fill="{g}"/>'
             f'<circle cx="80" cy="79" r="3.6" fill="{g}"/>')
    return crowned(p, crown, back=sword, mouth="smirk", lashes=True)


def king(p):
    g = p["gold"]
    crown = (f'<rect x="46.5" y="4" width="7" height="18" rx="2.5" fill="{g}"/>'
             f'<rect x="41" y="8.5" width="18" height="7" rx="2.5" fill="{g}"/>'
             f'<path d="M31,39 L31,23 L40,31 L50,21 L60,31 L69,23 L69,39 Z" fill="{g}"/>')
    return crowned(p, crown, front=heater_shield(p, 28, 62, 20, 24), mouth="frown", mustache=True, scar=True)


WAR = {"Pawn": pawn, "Rook": rook, "Knight": knight, "Bishop": bishop, "Queen": queen, "King": king}


# --- Classic (Staunton-style silhouettes) -------------------------------------

CLASSIC_PALETTES = {
    "white": dict(line="#1c1c1c", body="#ffffff", detail="#1c1c1c"),
    "black": dict(line="#000000", body="#2b2b2b", detail="#e6e6e6"),
}


def c_base(p, x0=24, x1=76):
    return (f'<path d="M{x0},90 V84 Q{x0},79 {x0 + 5},79 H{x1 - 5} Q{x1},79 {x1},84 V90 Z" fill="{p["body"]}"/>')


def c_collar(p, x0, x1, y, h=6):
    return f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="{h}" rx="2" fill="{p["body"]}"/>'


def c_detail(p, d, w=2):
    return f'<path d="{d}" stroke="{p["detail"]}" stroke-width="{w}" fill="none"/>'


def c_pawn(p):
    return (f'<path d="M35,80 C37,66 43,56 45,49 H55 C57,56 63,66 65,80 Z" fill="{p["body"]}"/>'
            + c_collar(p, 37, 63, 43) + f'<circle cx="50" cy="30" r="12" fill="{p["body"]}"/>' + c_base(p, 28, 72))


def c_rook(p):
    return (f'<path d="M33,73 L36,38 H64 L67,73 Z" fill="{p["body"]}"/>'
            + c_collar(p, 29, 71, 72, 8)
            + c_collar(p, 31, 69, 33, 6)
            + f'<path d="M28,34 V15 H37 V22 H45 V15 H55 V22 H63 V15 H72 V34 Z" fill="{p["body"]}"/>'
            + c_base(p)
            + c_detail(p, "M36,38 H64 M33,72 H67"))


def c_knight(p):
    return (f'<path d="M33,80 C33,66 40,58 45,52 C39,54 32,57 26,59 C19,61 15,55 18,50 '
            f'C23,41 31,33 37,27 C39,21 42,16 45,11 L50,19 C57,17 65,20 70,28 '
            f'C78,41 78,60 74,80 Z" fill="{p["body"]}"/>'
            + c_detail(p, "M60,24 C67,35 70,52 68,74", 2.2)
            + f'<circle cx="41" cy="31" r="2.6" fill="{p["detail"]}" stroke="none"/>'
            f'<circle cx="22" cy="53" r="1.6" fill="{p["detail"]}" stroke="none"/>'
            + c_base(p))


def c_bishop(p):
    return (f'<path d="M38,79 C40,74 41,70 41,66 H59 C59,70 60,74 62,79 Z" fill="{p["body"]}"/>'
            + c_collar(p, 35, 65, 60)
            + f'<path d="M50,20 C64,31 67,47 61,60 H39 C33,47 36,31 50,20 Z" fill="{p["body"]}"/>'
            f'<circle cx="50" cy="15" r="5" fill="{p["body"]}"/>'
            + c_detail(p, "M55,32 L47,45", 2.4)
            + c_base(p, 26, 74))


def c_queen(p):
    tips = ((21, 30), (36, 24), (50, 19), (64, 24), (79, 30))
    return (f'<path d="M32,73 L21,32 L36,53 L36,26 L45,50 L50,21 L55,50 L64,26 L64,53 L79,32 L68,73 Z" '
            f'fill="{p["body"]}"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="4" fill="{p["body"]}"/>' for x, y in tips)
            + c_collar(p, 31, 69, 72, 8)
            + c_base(p)
            + c_detail(p, "M30,64 Q50,58 70,64"))


def c_king(p):
    return (f'<rect x="46.5" y="6" width="7" height="22" rx="1.5" fill="{p["body"]}"/>'
            f'<rect x="40" y="12" width="20" height="7" rx="1.5" fill="{p["body"]}"/>'
            f'<path d="M32,73 C24,60 20,47 29,39 C36,33 45,36 50,45 C55,36 64,33 71,39 '
            f'C80,47 76,60 68,73 Z" fill="{p["body"]}"/>'
            f'<path d="M43,40 C43,30 57,30 57,40 L50,47 Z" fill="{p["body"]}"/>'
            + c_collar(p, 31, 69, 72, 8)
            + c_base(p)
            + c_detail(p, "M31,64 Q50,58 69,64 M50,47 V62"))


CLASSIC = {"Pawn": c_pawn, "Rook": c_rook, "Knight": c_knight, "Bishop": c_bishop, "Queen": c_queen,
           "King": c_king}

SETS = {"war": (WAR, PALETTES, 3.2), "classic": (CLASSIC, CLASSIC_PALETTES, 2.6)}


def main():
    for set_name, (pieces, palettes, stroke) in SETS.items():
        for name, draw in pieces.items():
            for color, p in palettes.items():
                svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
                       f'<g stroke="{p["line"]}" stroke-width="{stroke}" stroke-linejoin="round" '
                       f'stroke-linecap="round">{draw(p)}</g></svg>\n')
                path = OUT / set_name / name / f"{color}.svg"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(svg)
        print(f"wrote {OUT / set_name}")


if __name__ == "__main__":
    main()
