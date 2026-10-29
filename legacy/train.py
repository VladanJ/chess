"""
Evolutionary self-play trainer for the RTS chess AI.

Two neural-net "brains" play headless games at maximum speed (no rendering).
A population of brains competes; after each generation the winners survive and
spawn mutated children. The running champion is only replaced when the
generation's best brain beats the built-in heuristic AI more often than the
current champion does, anchoring progress to a fixed external benchmark so the
population can't drift into beating only itself. The champion is saved to disk
so the game can load it.

Usage:
    python train.py                # 1000 games, saves ai_brain.pt
    python train.py --games 2000 --pop 12 --out ai_brain.pt
"""

import argparse
import multiprocessing as mp
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor

import torch

import ChessGame as cg
from ai import AIController, PIECE_VALUE
from brain import Brain, NNPolicy, clone_brain, mutate, save_brain


DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_brain.pt")

# Simulation pacing for headless play (large dt = fast-forwarded time).
SIM_DT = 1.0
MAX_STEPS = 250
# Action rate high enough that every idle piece is commanded immediately.
TRAIN_APS = 99.0

# Champion gating: a challenger only becomes champion if it beats the built-in
# heuristic AI better than the current champion does. This anchors progress to
# an external, fixed benchmark so the population can't drift into beating only
# itself while regressing against real play.
GATE_GAMES = 8
GATE_DIFFICULTY = 10


def _material(pieces, color):
    return sum(PIECE_VALUE.get(p.name, 1)
               for p in pieces if p.alive and p.color == color)


def _king_alive(pieces, color):
    return any(p.alive for p in pieces
               if p.name == "King" and p.color == color)


@torch.no_grad()
def play_game(brain_white, brain_black, sigma=0.0,
              max_steps=MAX_STEPS, dt=SIM_DT):
    """Play one headless game. Returns 'white', 'black', or 'draw'."""
    pieces = cg.create_pieces()

    cw = AIController("white", cg.get_legal_targets,
                     policy=NNPolicy(brain_white, sigma=sigma))
    cb = AIController("black", cg.get_legal_targets,
                     policy=NNPolicy(brain_black, sigma=sigma))
    cw.actions_per_second = TRAIN_APS
    cb.actions_per_second = TRAIN_APS

    for _ in range(max_steps):
        cw.update(dt, pieces)
        cb.update(dt, pieces)
        cg.process_combat(pieces, dt)
        for p in pieces:
            p.update(dt, pieces)

        wk = _king_alive(pieces, "white")
        bk = _king_alive(pieces, "black")
        if not wk and not bk:
            return "draw"
        if not bk:
            return "white"
        if not wk:
            return "black"

    # No checkmate within the step budget — decide by remaining material.
    mw = _material(pieces, "white")
    mb = _material(pieces, "black")
    if mw > mb:
        return "white"
    if mb > mw:
        return "black"
    return "draw"


def duel(brain_a, brain_b, sigma):
    """Play brain_a vs brain_b once with randomized colors.
    Returns +1 if a wins, -1 if b wins, 0 on draw."""
    if random.random() < 0.5:
        r = play_game(brain_a, brain_b, sigma=sigma)
        return 1 if r == "white" else (-1 if r == "black" else 0)
    else:
        r = play_game(brain_b, brain_a, sigma=sigma)
        return 1 if r == "black" else (-1 if r == "white" else 0)


# --- Parallel self-play helpers -------------------------------------------
# Brains can't be cheaply shared across processes, so we ship their weights
# (state dicts) to the workers and rebuild the network on the other side.

def _brain_state(brain):
    return {k: v.detach().cpu().clone() for k, v in brain.state_dict().items()}


def _brain_from_state(state):
    b = Brain()
    b.load_state_dict(state)
    b.eval()
    return b


def _duel_task(args):
    """Worker entry point: rebuild two brains and play one duel."""
    state_a, state_b, sigma, seed = args
    torch.set_num_threads(1)          # avoid thread oversubscription per worker
    random.seed(seed)
    torch.manual_seed(seed)
    return duel(_brain_from_state(state_a), _brain_from_state(state_b), sigma)


def _play_duels(pairs, brains, sigma, executor):
    """Play the given (i, j) duels and return outcomes aligned with `pairs`
    (positive = brains[i] won). Runs in parallel when `executor` is set."""
    if executor is None:
        return [duel(brains[i], brains[j], sigma) for i, j in pairs]
    tasks = [(_brain_state(brains[i]), _brain_state(brains[j]), sigma,
              random.randrange(2 ** 31)) for i, j in pairs]
    return list(executor.map(_duel_task, tasks))


# --- Heuristic benchmark (champion gate) -----------------------------------

@torch.no_grad()
def play_vs_heuristic(brain, brain_is_white, difficulty=GATE_DIFFICULTY,
                      max_steps=MAX_STEPS, dt=SIM_DT):
    """One headless game: brain vs the built-in heuristic AI.
    Returns +1 if the brain wins, -1 if it loses, 0 on draw."""
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
            return -1
        if not _king_alive(pieces, heur_color):
            return 1

    nn_mat = _material(pieces, nn_color)
    heur_mat = _material(pieces, heur_color)
    if nn_mat > heur_mat:
        return 1
    if heur_mat > nn_mat:
        return -1
    return 0


def _heuristic_task(args):
    """Worker entry point: rebuild a brain and play one game vs the heuristic."""
    state, brain_is_white, difficulty, seed = args
    torch.set_num_threads(1)
    random.seed(seed)
    torch.manual_seed(seed)
    return play_vs_heuristic(_brain_from_state(state), brain_is_white, difficulty)


def score_vs_heuristic(brain, n_games, difficulty, executor):
    """Score rate in [0, 1] of `brain` vs the heuristic over `n_games`
    (colors alternated for fairness). Runs in parallel when `executor` is set."""
    if executor is None:
        results = [play_vs_heuristic(brain, i % 2 == 0, difficulty)
                   for i in range(n_games)]
    else:
        tasks = [(_brain_state(brain), i % 2 == 0, difficulty,
                  random.randrange(2 ** 31)) for i in range(n_games)]
        results = list(executor.map(_heuristic_task, tasks))
    wins = sum(1 for r in results if r > 0)
    draws = sum(1 for r in results if r == 0)
    return (wins + 0.5 * draws) / n_games


# --- Head-to-head benchmark (challenger vs current champion) ----------------

@torch.no_grad()
def _h2h_game(brain_a, brain_b, a_is_white):
    """One headless game between two brains.
    Returns +1 if brain_a wins, -1 if it loses, 0 on draw."""
    if a_is_white:
        r = play_game(brain_a, brain_b)
        return 1 if r == "white" else (-1 if r == "black" else 0)
    r = play_game(brain_b, brain_a)
    return 1 if r == "black" else (-1 if r == "white" else 0)


def _h2h_task(args):
    """Worker entry point: rebuild two brains and play one head-to-head game."""
    state_a, state_b, a_is_white, seed = args
    torch.set_num_threads(1)
    random.seed(seed)
    torch.manual_seed(seed)
    return _h2h_game(_brain_from_state(state_a), _brain_from_state(state_b),
                     a_is_white)


def score_vs_champion(challenger, champion, n_games, executor):
    """Win rate in [0, 1] of `challenger` vs the current `champion` over
    `n_games` (colors alternated). Runs in parallel when `executor` is set."""
    if executor is None:
        results = [_h2h_game(challenger, champion, i % 2 == 0)
                   for i in range(n_games)]
    else:
        tasks = [(_brain_state(challenger), _brain_state(champion),
                  i % 2 == 0, random.randrange(2 ** 31))
                 for i in range(n_games)]
        results = list(executor.map(_h2h_task, tasks))
    wins = sum(1 for r in results if r > 0)
    draws = sum(1 for r in results if r == 0)
    return (wins + 0.5 * draws) / n_games


def train(total_games=1000, pop_size=8, sigma=0.15, explore=0.05,
          out_path=DEFAULT_OUT, seed=None, resume=False, workers=None,
          eval_games=GATE_GAMES, eval_difficulty=GATE_DIFFICULTY):
    if seed is not None:
        random.seed(seed)
        torch.manual_seed(seed)

    # Seed the population from an existing champion (continue learning) or
    # start fresh from random brains.
    if resume and os.path.exists(out_path):
        from brain import load_brain
        base = load_brain(out_path)
        champion = clone_brain(base)
        population = [clone_brain(base)]
        population += [mutate(base, sigma) for _ in range(pop_size - 1)]
        print(f"Resuming from champion: {out_path}")
    else:
        population = [Brain() for _ in range(pop_size)]
        champion = clone_brain(population[0])

    games_played = 0
    generation = 0
    next_milestone = 1000
    start = time.time()

    if workers is None:
        workers = os.cpu_count() or 1
    executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    print(f"Training: target {total_games} games, population {pop_size}, "
          f"workers {workers if executor else 1}")

    try:
        # Benchmark the starting champion so challengers have a bar to clear.
        champion_score = score_vs_heuristic(champion, eval_games,
                                            eval_difficulty, executor)
        games_played += eval_games
        print(f"Champion baseline vs heuristic (diff {eval_difficulty}): "
              f"{champion_score * 100:.0f}%")

        while games_played < total_games:
            generation += 1
            scores = [0.0] * pop_size

            # --- Round: each brain duels a random opponent (parallel) ---
            n = min(pop_size, total_games - games_played)
            pairs = []
            for i in range(n):
                j = random.randrange(pop_size - 1)
                if j >= i:
                    j += 1
                pairs.append((i, j))
            for (i, j), outcome in zip(
                    pairs, _play_duels(pairs, population, explore, executor)):
                scores[i] += outcome
                scores[j] -= outcome
                games_played += 1

            # --- Gate the champion on heuristic performance ---
            # Self-play decides selection within the population, but the
            # champion only changes when the generation's best brain beats the
            # heuristic benchmark more often than the current champion does.
            best_idx = max(range(pop_size), key=lambda k: scores[k])
            challenger = population[best_idx]
            tag = ""
            if total_games - games_played >= eval_games:
                ch_score = score_vs_heuristic(challenger, eval_games,
                                              eval_difficulty, executor)
                games_played += eval_games
                # The challenger must (a) do at least as well as the champion
                # against the fixed heuristic benchmark AND (b) beat the current
                # champion head-to-head. Requiring a direct win keeps training
                # improving even after the heuristic score saturates at 100%.
                h2h_games = 4
                if (ch_score >= champion_score
                        and total_games - games_played >= h2h_games):
                    h2h = score_vs_champion(challenger, champion,
                                            h2h_games, executor)
                    games_played += h2h_games
                    if h2h > 0.5:
                        champion = clone_brain(challenger)
                        champion_score = ch_score
                        save_brain(champion, out_path)
                        tag = (f"  <- new champion "
                               f"(heuristic {ch_score * 100:.0f}%, "
                               f"h2h {h2h * 100:.0f}%, saved)")

            # --- Selection: keep top half, refill with mutated children ---
            ranked = sorted(range(pop_size), key=lambda k: scores[k],
                            reverse=True)
            survivors = ranked[: max(1, pop_size // 2)]
            new_pop = [population[k] for k in survivors]
            while len(new_pop) < pop_size:
                parent = population[random.choice(survivors)]
                new_pop.append(mutate(parent, sigma))
            population = new_pop

            if generation % 5 == 0 or tag:
                elapsed = time.time() - start
                print(f"gen {generation:4d} | games "
                      f"{games_played:5d}/{total_games} "
                      f"| best score {scores[best_idx]:+.0f} "
                      f"| champ {champion_score * 100:.0f}% "
                      f"| {elapsed:5.1f}s{tag}")

            # --- Milestone report every 1000 games ---
            while games_played >= next_milestone:
                elapsed = time.time() - start
                print(f"=== PROGRESS {next_milestone}/{total_games} games "
                      f"| champion vs heuristic {champion_score * 100:.0f}% "
                      f"| {elapsed:.1f}s elapsed ===", flush=True)
                next_milestone += 1000
    finally:
        if executor is not None:
            executor.shutdown()

    # Ensure a champion file exists even if it was never replaced.
    if not os.path.exists(out_path):
        save_brain(champion, out_path)

    print(f"Done. {games_played} games in {time.time() - start:.1f}s. "
          f"Champion saved to {out_path}")
    return champion


def main():
    parser = argparse.ArgumentParser(description="Self-play trainer for chess AI")
    parser.add_argument("--games", type=int, default=1000,
                        help="Total number of self-play games (default 1000)")
    parser.add_argument("--pop", type=int, default=8,
                        help="Population size (default 8)")
    parser.add_argument("--sigma", type=float, default=0.15,
                        help="Mutation strength (default 0.15)")
    parser.add_argument("--explore", type=float, default=0.05,
                        help="Per-move score exploration noise (default 0.05)")
    parser.add_argument("--out", type=str, default=DEFAULT_OUT,
                        help="Where to save the champion brain")
    parser.add_argument("--resume", action="store_true",
                        help="Continue training from the existing champion file")
    parser.add_argument("--workers", type=int, default=None,
                        help="Parallel worker processes (default: CPU count; "
                             "use 1 to disable multiprocessing)")
    parser.add_argument("--eval-games", type=int, default=GATE_GAMES,
                        help="Games vs the heuristic used to gate the champion "
                             f"(default {GATE_GAMES})")
    parser.add_argument("--eval-difficulty", type=int, default=GATE_DIFFICULTY,
                        help="Heuristic difficulty 0-10 for the champion gate "
                             f"(default {GATE_DIFFICULTY})")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed")
    args = parser.parse_args()

    train(total_games=args.games, pop_size=args.pop, sigma=args.sigma,
          explore=args.explore, out_path=args.out, seed=args.seed,
          resume=args.resume, workers=args.workers,
          eval_games=args.eval_games, eval_difficulty=args.eval_difficulty)


if __name__ == "__main__":
    mp.freeze_support()
    main()
