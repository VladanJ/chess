"""
Generate SVG visualisations of the trained chess brain's weights.

Dependency-free (only torch, which the project already uses). Produces
diverging-colour heatmaps for every weight matrix in ai_brain.pt, plus a
bias strip, written next to this script. Re-run after retraining to refresh
the figures in the documentation:

    python docs/assets/visualize_weights.py [path/to/brain.pt]
"""

import os
import sys

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BRAIN = os.path.join(HERE, "..", "..", "ai_brain.pt")

# Feature names in the exact order produced by NNPolicy._features (brain.py).
FEATURE_LABELS = [
    "piece_value",   # 0
    "piece_hp",      # 1
    "is_capture",    # 2
    "cap_value",     # 3
    "cap_hp",        # 4
    "new_king_dist", # 5
    "delta_king_dist", # 6
    "advance",       # 7
    "mat_balance",   # 8
    "center",        # 9
]


def _color(v, vmax):
    """Diverging blue(-)-white(0)-red(+) colour for a weight value."""
    if vmax <= 0:
        vmax = 1e-6
    t = max(-1.0, min(1.0, v / vmax))
    if t >= 0:  # white -> red
        r = 255
        g = int(255 * (1 - t))
        b = int(255 * (1 - t))
    else:       # white -> blue
        r = int(255 * (1 + t))
        g = int(255 * (1 + t))
        b = 255
    return f"#{r:02x}{g:02x}{b:02x}"


def _esc(s):
    """Escape text for safe inclusion in SVG/XML content."""
    return (str(s).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def heatmap_svg(mat, row_label, col_label, col_names=None,
                title="", cell=22, pad_left=120, pad_top=80, pad_right=20,
                pad_bottom=30):
    """Return an SVG string rendering a 2-D tensor as a heatmap."""
    rows, cols = mat.shape
    vmax = float(mat.abs().max())
    w = pad_left + cols * cell + pad_right
    h = pad_top + rows * cell + pad_bottom
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'font-family="monospace" font-size="11">',
        f'<rect width="{w}" height="{h}" fill="white"/>',
        f'<text x="{pad_left}" y="20" font-size="14" font-weight="bold">{_esc(title)}</text>',
        f'<text x="{pad_left}" y="38" fill="#555">range [-{vmax:.3f}, +{vmax:.3f}]  '
        f'blue = negative, red = positive</text>',
    ]
    # Column headers.
    for c in range(cols):
        x = pad_left + c * cell + cell / 2
        name = col_names[c] if col_names else str(c)
        out.append(
            f'<text x="{x}" y="{pad_top - 6}" text-anchor="start" '
            f'transform="rotate(-45 {x} {pad_top - 6})" fill="#333">{_esc(name)}</text>')
    # Row labels (every row index).
    for r in range(rows):
        y = pad_top + r * cell + cell / 2 + 4
        out.append(
            f'<text x="{pad_left - 8}" y="{y}" text-anchor="end" fill="#333">'
            f'{_esc(row_label)} {r}</text>')
    # Cells.
    for r in range(rows):
        for c in range(cols):
            v = float(mat[r, c])
            x = pad_left + c * cell
            y = pad_top + r * cell
            cname = col_names[c] if col_names else c
            out.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{_color(v, vmax)}" stroke="#eee" stroke-width="0.5">'
                f'<title>{_esc(row_label)} {r} from {_esc(cname)}: '
                f'{v:+.4f}</title></rect>')
    out.append(f'<text x="{pad_left}" y="{h - 8}" fill="#555">'
               f'{_esc(col_label)} (columns)  x  {_esc(row_label)} (rows)</text>')
    out.append('</svg>')
    return "\n".join(out)


def bias_svg(vec, label, title, cell=22, pad_left=120, pad_top=60, pad=20):
    n = vec.shape[0]
    vmax = float(vec.abs().max())
    w = pad_left + n * cell + pad
    h = pad_top + cell + 40
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'font-family="monospace" font-size="11">',
        f'<rect width="{w}" height="{h}" fill="white"/>',
        f'<text x="{pad_left}" y="20" font-size="14" font-weight="bold">{_esc(title)}</text>',
        f'<text x="{pad_left}" y="38" fill="#555">range [-{vmax:.3f}, +{vmax:.3f}]</text>',
        f'<text x="{pad_left - 8}" y="{pad_top + cell/2 + 4}" text-anchor="end">{_esc(label)}</text>',
    ]
    for i in range(n):
        v = float(vec[i])
        x = pad_left + i * cell
        out.append(
            f'<rect x="{x}" y="{pad_top}" width="{cell}" height="{cell}" '
            f'fill="{_color(v, vmax)}" stroke="#eee" stroke-width="0.5">'
            f'<title>{i}: {v:+.4f}</title></rect>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BRAIN
    sd = torch.load(path, map_location="cpu")
    w0, b0 = sd["net.0.weight"], sd["net.0.bias"]
    w2, b2 = sd["net.2.weight"], sd["net.2.bias"]
    w4, b4 = sd["net.4.weight"], sd["net.4.bias"]

    figs = {
        "weights_layer0.svg": heatmap_svg(
            w0, "h1", "input feature", FEATURE_LABELS,
            title="Layer 0  Linear(10 -> 24)  weights"),
        "weights_layer2.svg": heatmap_svg(
            w2, "h2", "h1 neuron", None,
            title="Layer 2  Linear(24 -> 24)  weights"),
        "weights_layer4.svg": heatmap_svg(
            w4, "out", "h2 neuron", None,
            title="Layer 4  Linear(24 -> 1)  weights (the read-out)"),
        "bias_layer0.svg": bias_svg(b0, "h1", "Layer 0 bias (24 hidden neurons)"),
        "bias_layer2.svg": bias_svg(b2, "h2", "Layer 2 bias (24 hidden neurons)"),
    }
    for name, svg in figs.items():
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)


if __name__ == "__main__":
    main()
