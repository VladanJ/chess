import assert from "node:assert/strict";
import { test } from "node:test";
import { AIController, Move, Policy } from "../src/ai";
import { fromFen, toFen } from "../src/fen";
import { Piece } from "../src/piece";
import { createPieces, getLegalTargets, guardCount, pawnsToPromote, processCombat } from "../src/rules";

/** Advance the simulation in small steps until *until* holds (or a step cap). */
function run(pieces: Piece[], until: () => boolean, dt = 0.02): void {
  for (let i = 0; i < 5000 && !until(); i++) {
    processCombat(pieces, dt);
    for (const p of pieces) p.update(dt, pieces);
  }
}

test("mutual lethal hits kill both pieces regardless of array order", () => {
  for (const reverse of [false, true]) {
    const black = new Piece("black", "Rook", 0, 0, 1);
    const white = new Piece("white", "Rook", 0, 1, 1);
    black.startMove(0, 1);
    white.startMove(0, 0);
    processCombat(reverse ? [white, black] : [black, white], 0.1);
    assert.equal(black.alive, false);
    assert.equal(white.alive, false);
  }
});

test("several attackers on one defender stack their damage", () => {
  const d = new Piece("black", "Rook", 1, 1, 300);
  const a1 = new Piece("white", "Rook", 1, 2, 300);
  const a2 = new Piece("white", "Rook", 2, 1, 300);
  a1.startMove(1, 1);
  a2.startMove(1, 1);
  processCombat([d, a1, a2], 1.0);
  assert.equal(d.hp, 280);
});

test("formation defense halves damage per guard", () => {
  const hit = (guards: Piece[], guarded: boolean) => {
    const d = new Piece("black", "Rook", 3, 3, 1000);
    const a = new Piece("white", "Rook", 3, 4, 1000);
    a.startMove(3, 3);
    const pieces = [d, a, ...guards];
    processCombat(pieces, 1.0, guarded);
    return 1000 - d.hp;
  };
  const knight = () => new Piece("black", "Knight", 1, 2);
  const pawn = () => new Piece("black", "Pawn", 2, 2); // black pawns guard diagonally downward
  assert.equal(hit([], true), 10);
  assert.equal(hit([knight()], true), 5);
  assert.equal(hit([knight(), pawn()], true), 2.5);
  assert.equal(hit([knight()], false), 10);
  assert.equal(hit([new Piece("black", "Pawn", 3, 2)], true), 10, "a pawn straight ahead does not guard");
});

test("guards need a clear line and must be idle", () => {
  const d = new Piece("black", "Rook", 3, 3);
  const queen = new Piece("black", "Queen", 3, 0);
  const blocker = new Piece("white", "Pawn", 3, 1);
  assert.equal(guardCount(d, 3, 3, [d, queen]), 1);
  assert.equal(guardCount(d, 3, 3, [d, queen, blocker]), 0);
  queen.startMove(4, 0);
  assert.equal(guardCount(d, 3, 3, [d, queen]), 0, "a moving piece does not guard");
});

test("only pawns at rest on the far rank are promotable", () => {
  const arrived = new Piece("white", "Pawn", 2, 0);
  const black = new Piece("black", "Pawn", 5, 7);
  const sliding = new Piece("white", "Pawn", 6, 1);
  sliding.startMove(6, 0);
  const notThere = new Piece("white", "Pawn", 1, 3);
  assert.deepEqual(pawnsToPromote([arrived, black, sliding, notThere]), [arrived, black]);
});

test("promotion keeps the health fraction", () => {
  const p = new Piece("white", "Pawn", 2, 0, 100);
  p.hp = 40;
  p.promote("Bishop", 300);
  assert.equal(p.name, "Bishop");
  assert.equal(p.maxHp, 300);
  assert.equal(p.hp, 120);
});

test("a pawn loses its double step once it leaves its start square", () => {
  const p = new Piece("white", "Pawn", 4, 6);
  p.startMove(4, 4);
  run([p], () => p.row === 5);
  p.stop();
  assert.deepEqual(getLegalTargets(p, [p]), [[4, 4]]);
});

test("a pawn stopped before leaving keeps its double step", () => {
  const p = new Piece("white", "Pawn", 6, 6);
  p.startMove(6, 4);
  p.update(0.02, [p]);
  p.stop();
  assert.deepEqual(getLegalTargets(p, [p]), [[6, 5], [6, 4]]);
});

test("a pawn's diagonal target disappears when the enemy leaves", () => {
  const pawn = new Piece("white", "Pawn", 3, 4);
  const enemy = new Piece("black", "Rook", 4, 3);
  const pieces = [pawn, enemy];
  assert.ok(getLegalTargets(pawn, pieces).some(([c, r]) => c === 4 && r === 3));
  enemy.startMove(5, 3);
  enemy.update(100, pieces);
  assert.ok(!getLegalTargets(pawn, pieces).some(([c, r]) => c === 4 && r === 3));
});

test("the AI defends its King even when a trained policy would play elsewhere", () => {
  const king = new Piece("black", "King", 4, 0);
  const defender = new Piece("black", "Rook", 0, 4);
  const attacker = new Piece("white", "Rook", 4, 4);
  const whiteKing = new Piece("white", "King", 7, 7);
  const pieces = [king, defender, attacker, whiteKing];
  const elsewhere: Policy = { choose: (): Move => [defender, [0, 7]] };
  const ai = new AIController("black", 10, elsewhere);
  ai.actionsPerSecond = 1;
  ai.update(1, pieces);
  assert.ok(defender.moving);
  assert.deepEqual([defender.targetCol, defender.targetRow], [4, 4], "rook captures the King's attacker");
});

test("FEN round-trips the standard setup and rejects bad boards", () => {
  const start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";
  assert.equal(toFen(createPieces()), start);
  const parsed = fromFen(start);
  assert.ok(parsed);
  assert.equal(parsed.length, 32);
  assert.equal(toFen(parsed), start);
  assert.deepEqual(fromFen("4k3/8/8/8/8/8/8/4K3 w - - 0 1"), [
    { color: "black", name: "King", col: 4, row: 0 },
    { color: "white", name: "King", col: 4, row: 7 },
  ]);
  for (const bad of ["", "8/8/8", "9/8/8/8/8/8/8/8", "x7/8/8/8/8/8/8/8", "ppppppppp/8/8/8/8/8/8/8"]) {
    assert.equal(fromFen(bad), null, bad);
  }
});
