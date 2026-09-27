// Run with `npm test` (Node's own test runner; Node strips the types).
import assert from "node:assert/strict";
import { test } from "node:test";
import type { Motion } from "./geometry.ts";
import { packing } from "./pack.ts";

const LANE = 1.22;

/** A runner at ``start`` metres at the gun, running ``speed`` m/s until ``end``. */
const steady = (start: number, speed: number, end = 20): Motion => ({
  at: (t) => (t < 0 || t > end ? null : start + speed * t),
  finished: true,
  end,
});

test("runners in single file all run in lane 1", () => {
  const runners = [steady(10, 7), steady(5, 7), steady(0.5, 7)];
  const packed = packing(runners, 0, LANE, 20);
  for (let t = 0; t <= 20; t += 0.5) {
    runners.forEach((_, i) => assert.equal(packed.at(i, t), 0, `runner ${i} at ${t}s`));
  }
});

test("a faster runner goes round the one ahead and cuts back in once clear", () => {
  // B closes at 1 m/s from 4 m back: blocked from 3 s, alongside at 4 s, clear at 5.5 s.
  const [a, b] = [steady(5, 6), steady(1, 7)];
  const packed = packing([a, b], 0, LANE, 20);
  assert.ok(Math.abs(packed.at(1, 4) - LANE) < 1e-6, "alongside, B is in lane 2");
  assert.equal(packed.at(1, 1), 0, "well behind, B is in lane 1");
  assert.equal(packed.at(1, 8), 0, "clear ahead, B is back in lane 1");
  for (let t = 0; t <= 20; t += 0.25) assert.equal(packed.at(0, t), 0, `A stays in lane 1 (${t}s)`);
  // Moving out takes about half a second, not an instant.
  const moving = packed.at(1, 3.2);
  assert.ok(moving > 0 && moving < LANE, `part way out at 3.2 s: ${moving}`);
});

test("a crowded start spreads over at most four lanes", () => {
  const runners = Array.from({ length: 12 }, (_, i) => steady(0.1 + i * 0.01, 7));
  const packed = packing(runners, 0, LANE, 20);
  const widest = Math.max(...runners.map((_, i) => packed.at(i, 1)));
  assert.ok(widest > 0 && widest <= 3 * LANE + 1e-6, `widest ${widest}`);
});

test("runners are packed only once past the break", () => {
  const runners = [steady(0.5, 7), steady(0, 7)];
  const packed = packing(runners, 100, LANE, 20);
  // Level, but still in their lanes until 100 m (14 s): no place across the track yet.
  assert.equal(packed.at(1, 10), 0);
  assert.ok(packed.at(1, 15) > 0, "alongside once free");
});
