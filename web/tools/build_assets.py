"""Export the trained brain into web/public as JSON weights for the TypeScript MLP (brain.ts).

Run from anywhere:  python web/tools/build_assets.py [path/to/ai_brain.pt]
Piece images are generated separately by make_pieces.py.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.dirname(HERE)
ROOT = os.path.dirname(WEB)
PUBLIC = os.path.join(WEB, "public")


def export_brain(src):
    try:
        import torch
    except ImportError:
        print("torch not installed; skipping brain export (web AI uses heuristic).")
        return
    if not os.path.exists(src):
        print(f"{src} not found; skipping brain export.")
        return
    sd = torch.load(src, map_location="cpu")
    # brain.py Sequential: Linear(0), Tanh, Linear(2), Tanh, Linear(4)
    layers = [{"w": sd[f"net.{i}.weight"].tolist(), "b": sd[f"net.{i}.bias"].tolist()}
              for i in (0, 2, 4)]
    dst = os.path.join(PUBLIC, "brain.json")
    with open(dst, "w") as f:
        json.dump({"layers": layers}, f)
    print(f"Exported {src} -> web/public/brain.json")


if __name__ == "__main__":
    os.makedirs(PUBLIC, exist_ok=True)
    export_brain(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "legacy", "ai_brain.pt"))
