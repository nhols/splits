// Run with `npm test` (Node's own test runner; Node strips the types).
import assert from "node:assert/strict";
import { test } from "node:test";
import { CLOSEST, frameShot, mixRects, shotRect, smoothShot, type Shot } from "./camera.ts";

const near = (a: number, b: number, tolerance = 1e-9) =>
  assert.ok(Math.abs(a - b) <= tolerance, `${a} is not within ${tolerance} of ${b}`);

const SCALE = 5; // SVG units per metre
const [WIDTH, HEIGHT] = [1000, 500];

test("a tight pack is framed at the closest the camera comes", () => {
  const points = [
    { x: 500, y: 250 },
    { x: 510, y: 252 },
    { x: 505, y: 248 },
  ];
  const shot = frameShot(points, { x: 1, y: 0 }, SCALE, WIDTH / HEIGHT);
  near(shot.width, CLOSEST * SCALE);
  // It looks ahead: the pack sits behind the middle of the view.
  assert.ok(shot.centre.x > 505);
});

test("a strung-out field widens the view to fit everyone", () => {
  const points = [
    { x: 100, y: 250 },
    { x: 700, y: 250 },
  ];
  const shot = frameShot(points, { x: 1, y: 0 }, SCALE, WIDTH / HEIGHT);
  assert.ok(shot.width > 600);
  const rect = shotRect(shot, WIDTH, HEIGHT);
  assert.ok(rect.x <= 100 && rect.x + rect.w >= 700);
});

test("the view stays within the drawing and keeps its shape", () => {
  const rect = shotRect({ centre: { x: 10, y: 490 }, width: 300 }, WIDTH, HEIGHT);
  assert.deepEqual(rect, { x: 0, y: 350, w: 300, h: 150 });
  const whole = shotRect({ centre: { x: 10, y: 10 }, width: 5000 }, WIDTH, HEIGHT);
  assert.deepEqual(whole, { x: 0, y: 0, w: WIDTH, h: HEIGHT });
});

test("smoothing follows steady motion exactly and eases through a jump", () => {
  const moving = (t: number): Shot => ({ centre: { x: 100 + 50 * t, y: 200 }, width: 300 });
  const smooth = smoothShot(moving, 5, 20)!;
  near(smooth.centre.x, 350, 1e-9);
  // A cut from one place to another becomes a glide: halfway at the cut.
  const cut = (t: number): Shot => ({ centre: { x: t < 5 ? 0 : 100, y: 0 }, width: 300 });
  const at = smoothShot(cut, 5, 20)!.centre.x;
  assert.ok(at > 30 && at < 70, `${at}`);
});

test("rectangles mix part way", () => {
  assert.deepEqual(mixRects({ x: 0, y: 0, w: 100, h: 50 }, { x: 10, y: 20, w: 50, h: 25 }, 0.5), {
    x: 5,
    y: 10,
    w: 75,
    h: 37.5,
  });
});
