# Real-Time Chess

Chess with no turns. Both players move at the same time, pieces have hit points, and
combat happens on contact. Destroy the enemy King to win.

**Play:** https://real-time-chess.com

## Features

- Play against a trained neural-network AI (difficulty 1–10) or a friend on the same device
- Two piece sets: an angry chibi war band and classic Staunton-style pieces
- Options: pawn promotion (auto-Queen or pick the piece), formation defense, piece HP, sound
- Runs entirely in the browser, on desktop and mobile; no server needed

## Development

The game lives in [`web/`](web) (TypeScript, HTML5 Canvas, Vite).

```bash
cd web
npm install
npm run dev      # local dev server
npm test         # rule tests (Node's built-in test runner)
npm run build    # type-check + production build into web/dist
```

### Retraining the AI

The AI is a small neural network trained by self-play neuroevolution on the real game
rules. Retrain after changing rules or default HP:

```bash
cd web
npm run train -- --games 40000            # continue from web/public/brain.json
npm run train -- --games 40000 --fresh    # start from random brains
```

### Board editor

Add `?sandbox` to the URL to set up any position, play both sides with no cooldown, and
share the setup as a link (`?sandbox&setup=<FEN>`).

## Deployment

Pushing to `main` deploys to Cloudflare Workers. The build (root [`package.json`](package.json))
installs dependencies, runs the tests, then builds; a failing test stops the deploy.
[`wrangler.jsonc`](wrangler.jsonc) serves `web/dist` as a static site.

## Legacy

[`legacy/`](legacy) holds the original Python/Pygame desktop version and its PyTorch trainer.
It is no longer developed.
