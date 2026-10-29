"""Head-to-head: new champion vs old champion (not a permanent test)."""
import argparse
import random

from brain import load_brain
from train import play_game


def compare(new_path, old_path, games, seed, sigma):
    if seed is not None:
        random.seed(seed)
    new = load_brain(new_path)
    old = load_brain(old_path)

    new_wins = old_wins = draws = 0
    for i in range(games):
        if i % 2 == 0:                      # new plays white
            r = play_game(new, old, sigma=sigma)
            winner = "new" if r == "white" else ("old" if r == "black" else "draw")
        else:                               # new plays black
            r = play_game(old, new, sigma=sigma)
            winner = "new" if r == "black" else ("old" if r == "white" else "draw")
        if winner == "new":
            new_wins += 1
        elif winner == "old":
            old_wins += 1
        else:
            draws += 1

    print(f"New ({new_path}) vs Old ({old_path}) over {games} games:")
    print(f"  new wins {new_wins} | old wins {old_wins} | draws {draws}")
    print(f"  new win rate {new_wins / games * 100:.1f}%  |  "
          f"score rate {(new_wins + 0.5 * draws) / games * 100:.1f}%")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--new", default="ai_brain.pt")
    p.add_argument("--old", default="ai_brain_91.pt")
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--sigma", type=float, default=0.05,
                   help="Exploration noise so deterministic brains vary")
    a = p.parse_args()
    compare(a.new, a.old, a.games, a.seed, a.sigma)
