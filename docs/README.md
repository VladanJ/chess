# Real-Time Chess — Technical Documentation

> A field guide to the project, written for engineers. No hand-waving.

This folder contains the long-form, human-readable documentation for the
real-time chess project. It is organised as a short technical book. Read the
chapters in order if you are new, or jump straight to the part you need.

## Table of Contents

| Chapter | File | What it covers |
|---|---|---|
| 1 — Project Overview | [01-overview.md](01-overview.md) | What the game is, how the pieces fit together, the data flow |
| 2 — The Neural Network | [02-neural-network.md](02-neural-network.md) | **Architecture deep-dive.** Every layer, neuron and parameter (889 of them), the 10-feature input, learned-weight statistics, **weight heatmaps**, and feature-importance analysis |
| 3 — The Machine Learning Engine | [03-machine-learning.md](03-machine-learning.md) | **How the weights are found.** Neuroevolution, mutation, self-play, the champion gate, why naïve self-play regresses, parallel training, evaluation |

Generated figures and the script that produces them live in [assets/](assets/).

## The 30-second summary

This is a **real-time** chess variant (no turns; pieces slide and fight in
continuous time) with an AI opponent that comes in two flavours:

1. A **hand-written heuristic** (`ai.py`) — fast, torch-free, "captures first,
   then advance on the king."
2. A **learned neural policy** (`brain.py`) — a tiny MLP that scores candidate
   moves, trained entirely by **neuroevolution** (`train.py`), no gradient
   descent, no human games.

The trained brain beats the strongest heuristic setting roughly **91% of the
time**. Chapter 2 explains exactly how that number was earned — and the one
design decision (the *champion gate*) that made the difference between a model
that improves and one that quietly destroys itself.
