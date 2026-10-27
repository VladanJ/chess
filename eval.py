"""
Evaluate the trained neural-net brain against the built-in heuristic AI.

Plays headless games (colors randomized each game) and reports the trained
brain's win / loss / draw record and win rate.

Usage:
    python eval.py                 # 100 games vs heuristic, brain = ai_brain.pt
    python eval.py --games 200 --difficulty 10 --brain ai_brain.pt
"""

import argparse
import os
import random

import ChessGame as cg
from ai import AIController
from brain import NNPolicy, load_brain
from train import SIM_DT, MAX_STEPS, TRAIN_APS, _material, _king_alive

DEFAULT_BRAIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_brain.pt")


def play_match(brain, brain_is_white, difficulty, max_steps=MAX_STEPS, dt=SIM_DT):
    """One headless game: NN brain vs heuristic AI. Returns 'brain', 'heuristic'
    or 'draw'."""
    pieces = cg.create_pieces()

    nn_color = "white" if brain_is_white else "black"
    heur_color = "black" if brain_is_white else "white"

    nn_ctrl = AIController(nn_color, cg.get_legal_targets,
                          policy=NNPolicy(brain))
    heur_ctrl = AIController(heur_color, cg.get_legal_targets,
                            difficulty=difficulty)
    nn_ctrl.actions_per_second = TRAIN_APS
    heur_ctrl.actions_per_second = TRAIN_APS

    for _ in range(max_steps):
        nn_ctrl.update(dt, pieces)
        heur_ctrl.update(dt, pieces)
        cg.process_combat(pieces, dt)
        for p in pieces:
            p.update(dt, pieces)

        if not _king_alive(pieces, nn_color):
            return "heuristic"
        if not _king_alive(pieces, heur_color):
            return "brain"

    # Decide by remaining material.
    nn_mat = _material(pieces, nn_color)
    heur_mat = _material(pieces, heur_color)
    if nn_mat > heur_mat:
        return "brain"
    if heur_mat > nn_mat:
        return "heuristic"
    return "draw"


def evaluate(brain_path=DEFAULT_BRAIN, games=100, difficulty=10, seed=None):
    if seed is not None:
        random.seed(seed)
    brain = load_brain(brain_path)

    wins = losses = draws = 0
    for i in range(games):
        brain_is_white = (i % 2 == 0)  # alternate colors for fairness
        result = play_match(brain, brain_is_white, difficulty)
        if result == "brain":
            wins += 1
        elif result == "heuristic":
            losses += 1
        else:
            draws += 1

    decided = wins + losses
    win_rate = (wins / games) * 100
    score_rate = ((wins + 0.5 * draws) / games) * 100
    print(f"Trained brain ({brain_path}) vs heuristic (difficulty {difficulty})")
    print(f"  games {games} | wins {wins} | losses {losses} | draws {draws}")
    print(f"  win rate {win_rate:.1f}%  |  score rate {score_rate:.1f}%")
    if decided:
        print(f"  decided-game win rate {wins / decided * 100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained AI vs heuristic")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--difficulty", type=int, default=10,
                        help="Heuristic opponent difficulty 0-10 (default 10)")
    parser.add_argument("--brain", type=str, default=DEFAULT_BRAIN)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    evaluate(brain_path=args.brain, games=args.games,
             difficulty=args.difficulty, seed=args.seed)


if __name__ == "__main__":
    main()
