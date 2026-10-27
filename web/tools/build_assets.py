"""Copy game assets into web/public: piece images and the trained brain.

Run from anywhere:  python web/tools/build_assets.py [path/to/ai_brain.pt]
The brain is exported as JSON weights for the TypeScript MLP (brain.ts).
"""

import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.dirname(HERE)
ROOT = os.path.dirname(WEB)
PUBLIC = os.path.join(WEB, "public")


def copy_pieces():
    shutil.copytree(os.path.join(ROOT, "pieces"), os.path.join(PUBLIC, "pieces"),
                    dirs_exist_ok=True)
    print("Copied pieces/ -> web/public/pieces/")


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
    copy_pieces()
    export_brain(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "ai_brain.pt"))
