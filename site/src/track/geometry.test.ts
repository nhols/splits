// Run with `npm test` (Node's own test runner; Node strips the types).
import assert from "node:assert/strict";
import { test } from "node:test";
import { course, cutIn, indoorTrack, lapLength, laneRadius, lineRadius, motion, onStraight, outdoorTrack, pointAt, pulseAt, radiusAt, startOf } from "./geometry.ts";

const near = (a: number, b: number, tolerance = 1e-6) =>
  assert.ok(Math.abs(a - b) <= tolerance, `${a} is not within ${tolerance} of ${b}`);

test("lane 1 of the standard track measures 400 m", () => {
  near(lapLength(outdoorTrack(), laneRadius(outdoorTrack(), 1)), 400, 0.01);
});

test("the 400 m stagger in lane 8 is 53.03 m", () => {
  const track = outdoorTrack();
  near(lapLength(track, laneRadius(track, 8)) - 400, 53.03, 0.01);
});

test("every lane of a 400 m race finishes on the finish line", () => {
  const track = outdoorTrack(9);
  const race = course(track, 400);
  for (let lane = 1; lane <= 9; lane++) {
    const { p } = race.frame(lane, 400);
    near(p.x, track.straight / 2, 1e-6);
    near(p.y, laneRadius(track, lane), 1e-6);
  }
});

test("the 200 m starts at the beginning of the second bend", () => {
  const track = outdoorTrack();
  const start = course(track, 200).frame(1, 0).p;
  // Standard straights and radius make lane 1 400.001 m, so within a centimetre.
  near(start.x, -track.straight / 2, 0.01);
  near(start.y, -laneRadius(track, 1), 0.01);
});

test("indoors, lane 1 measures 200 m and the 400 m breaks after two bends", () => {
  const track = indoorTrack();
  near(lapLength(track, laneRadius(track, 1)), 200, 1e-9);
  const race = course(track, 400);
  near(race.breakAt!, 2 * Math.PI * laneRadius(track, 1) + track.straight, 1e-9);
  // The break line, at the start of the home straight, is the arc a straight's length from the
  // finish in lane 1, where runners head once out of their lanes.
  const finish = { x: track.straight / 2, y: laneRadius(track, 1) };
  for (let lane = 1; lane <= 6; lane++) {
    const at = race.frame(lane, race.breakAt!).p;
    near(Math.hypot(at.x - finish.x, at.y - finish.y), track.straight, 0.02);
  }
  // Positions are continuous through the break, and everyone finishes on the line.
  for (let lane = 1; lane <= 6; lane++) {
    const before = race.frame(lane, race.breakAt! - 1e-4).p;
    const after = race.frame(lane, race.breakAt! + 1e-4).p;
    near(Math.hypot(after.x - before.x, after.y - before.y), 0, 1e-3);
    near(race.frame(lane, 400).p.x, track.straight / 2, 1e-6);
  }
});

test("points run anticlockwise from the finish line", () => {
  const track = outdoorTrack();
  const r = laneRadius(track, 1);
  const p = pointAt(track, r, 1);
  assert.ok(p.x > track.straight / 2 && p.y < r, "into the first bend: rightwards and up");
});

test("motion passes through every published time and never runs backwards", () => {
  const knots = [
    { t: 0, d: 0 },
    { t: 0.15, d: 0 },
    { t: 11.08, d: 100 },
    { t: 21.06, d: 200 },
    { t: 31.97, d: 300 },
    { t: 44.31, d: 400 },
  ];
  const m = motion(knots, true);
  for (const k of knots) near(m.at(k.t)!, k.d, 1e-9);
  let previous = -1;
  for (let t = 0; t <= 45; t += 0.01) {
    const d = m.at(t)!;
    assert.ok(d >= previous - 1e-9, `ran backwards at ${t}`);
    previous = d;
  }
  near(m.at(0.1)!, 0, 1e-9); // still in the blocks before the reaction
  near(m.at(50)!, 400, 1e-9); // stays at the line after finishing
});

test("runners accelerate from the blocks and carry their speed smoothly into the race", () => {
  const knots = [
    { t: 0, d: 0 },
    { t: 0.15, d: 0 },
    { t: 5.96, d: 50 },
    { t: 10.63, d: 100 },
    { t: 15.37, d: 150 },
    { t: 43.4, d: 400 },
  ];
  const m = motion(knots, true);
  const speed = (t: number) => (m.at(t + 1e-4)! - m.at(t - 1e-4)!) / 2e-4;
  let previous = 0;
  for (let t = 0.2; t < 5.96; t += 0.05) {
    const v = speed(t);
    assert.ok(v >= previous - 1e-6, `slowed during the acceleration at ${t}`);
    assert.ok(v < 12.5, `implausibly fast at ${t}: ${v}`);
    previous = v;
  }
  // No jolt at the first split: the speed arriving equals the speed leaving.
  const arriving = (m.at(5.96)! - m.at(5.96 - 1e-4)!) / 1e-4;
  const leaving = (m.at(5.96 + 1e-4)! - m.at(5.96)!) / 1e-4;
  near(arriving, leaving, 0.01);
});

test("without splits, runners hold an even pace after accelerating", () => {
  const m = motion([{ t: 0, d: 0 }, { t: 0.2, d: 0 }, { t: 51.7, d: 400 }], true);
  const halfway = m.at(26)!;
  assert.ok(halfway > 185 && halfway < 205, `${halfway} m at halfway`);
  near(m.at(51.7)!, 400, 1e-9);
});

// A 200 m shape, every 10 m (the men's, rounded).
const SHAPE_200 = [
  0.089, 0.144, 0.193, 0.24, 0.286, 0.331, 0.376, 0.42, 0.464, 0.509, 0.555, 0.6, 0.646, 0.692, 0.738, 0.785, 0.833, 0.882, 0.94, 1,
].map((share, i) => ({ distance: (i + 1) * 10, share }));

/** When ``m`` reached ``d`` (it never runs backwards, so bisect). */
const when = (m: ReturnType<typeof motion>, d: number) => {
  let [lo, hi] = [0, m.end];
  for (let k = 0; k < 60; k++) {
    const mid = (lo + hi) / 2;
    if (m.at(mid)! < d) lo = mid;
    else hi = mid;
  }
  return hi;
};

test("with a shape, runners pass every split exactly, smoothly, never running backwards", () => {
  const knots = [
    { t: 0, d: 0 },
    { t: 0.133, d: 0 },
    { t: 5.6, d: 50 },
    { t: 9.92, d: 100 },
    { t: 14.44, d: 150 },
    { t: 19.19, d: 200 },
  ];
  const m = motion(knots, true, SHAPE_200);
  for (const { t, d } of knots.slice(2)) near(m.at(t)!, d, 1e-6);
  near(m.at(0.1)!, 0, 1e-9);
  let previous = -1;
  for (let t = 0; t <= 20; t += 0.01) {
    const d = m.at(t)!;
    assert.ok(d >= previous - 1e-9, `ran backwards at ${t}`);
    previous = d;
  }
  // No jolt at a split: the speed arriving is the speed leaving.
  const speed = (t: number, dt: number) => Math.abs(m.at(t + dt)! - m.at(t)!) / Math.abs(dt);
  near(speed(9.92, -0.05), speed(9.92, 0.05), 0.15);
});

test("with a shape, a runner with only a finish time runs the typical race", () => {
  const m = motion([{ t: 0, d: 0 }, { t: 0.15, d: 0 }, { t: 20.15, d: 200 }], true, SHAPE_200);
  for (const { distance, share } of SHAPE_200) near(when(m, distance), 0.15 + share * 20, 1e-3);
});

test("without a shape (above 800 m), the curve runs through the splits in metres", () => {
  const knots = [{ t: 0, d: 0 }, { t: 60, d: 400 }, { t: 125, d: 800 }, { t: 210, d: 1500 }];
  const m = motion(knots, true, null);
  for (const { t, d } of knots) near(m.at(t)!, d, 1e-6);
});

test("sprints up to the 110 m hurdles are run on the straight", () => {
  assert.ok(onStraight(60) && onStraight(100) && onStraight(110));
  assert.ok(!onStraight(200) && !onStraight(400));
});

test("a pulse trails the last moment's running, and a runner who stops fades out", () => {
  const knots = [{ t: 0, d: 0 }, { t: 0.15, d: 0 }, { t: 5.6, d: 50 }, { t: 9.8, d: 100 }];
  const running = motion(knots, true);
  const pulse = pulseAt(running, true, 5.6)!;
  near(pulse.to, 50, 1e-9);
  assert.ok(pulse.from > 38 && pulse.from < 45, `trail from ${pulse.from} m`);
  // In the blocks and past the line, a short bar where the runner stands.
  near(pulseAt(running, true, 0)!.from, -2.2, 1e-9);
  near(pulseAt(running, true, 12)!.to, 100, 1e-9);
  // Without a finish, the runner fades out after their last known point.
  const stopped = motion(knots.slice(0, 3), false);
  assert.ok(pulseAt(stopped, false, 6.2)!.opacity < 1);
  assert.equal(pulseAt(stopped, false, 8), null);
});

test("every race ends on the finish line, wherever it starts", () => {
  const track = outdoorTrack(9);
  const lap = lapLength(track, laneRadius(track, 1));
  // Lane 1 of the standard track measures 400.005 m, so starts are right to the centimetre.
  near(startOf(track, 1500), 100, 0.02); // three laps and three quarters: 100 m past the line
  near(startOf(track, 1609.344), lap - 9.344, 0.03); // the mile starts 9.34 m short of it
  near(startOf(track, 800), 0, 0.02);
  for (const distance of [800, 1000, 1500, 1609.344, 3000, 5000, 10000]) {
    const race = course(track, distance, 12);
    for (const position of [1, 6, 12]) near(race.frame(position, distance).p.x, track.straight / 2, 1e-6);
  }
});

test("the 800 m runs in lanes for a bend, to an arced break line", () => {
  const track = outdoorTrack(8);
  const race = course(track, 800, 8);
  near(race.breakAt!, Math.PI * laneRadius(track, 1), 1e-9);
  // Everyone reaches the break line at the same distance, each lane a straight's length from the
  // end of the back straight in lane 1, where they head: the arc World Athletics marks.
  const end = { x: -track.straight / 2, y: -laneRadius(track, 1) };
  for (let lane = 1; lane <= 8; lane++) {
    const at = race.frame(lane, race.breakAt!).p;
    near(Math.hypot(at.x - end.x, at.y - end.y), track.straight, 0.02);
  }
  // Lane 8's stagger is World Athletics' for the 800 m: one bend, and 0.42 m more for cutting in.
  near(Math.PI * (laneRadius(track, 8) - laneRadius(track, 1)) + cutIn(track, 8), 26.933, 0.01);
  // And the cut-in is taken back by the end of the straight, where lane 8 is level with lane 1.
  near(race.frame(8, race.breakAt! + track.straight).p.x, race.frame(1, race.breakAt! + track.straight).p.x, 1e-6);
});

test("a waterfall start is curved: those further out stand further ahead, by as much as they must cut in", () => {
  const track = outdoorTrack(8);
  const race = course(track, 1500, 12);
  const r1 = laneRadius(track, 1);
  // How far along lane 1 a point is, from the start of the first bend (the 1500 m starts on it).
  const along = (p: { x: number; y: number }) => (Math.PI / 2 - Math.atan2(p.y, p.x - track.straight / 2)) * r1;
  const at = (position: number) => along(race.frame(position, 0).p);
  for (let position = 2; position <= 12; position++) assert.ok(at(position) > at(position - 1), `starter ${position} is not ahead`);
  // The outside starter's shortest route cuts diagonally across the back straight to lane 1 at
  // its end, and is as long as lane 1's route there, round the rest of the bend and down it.
  const outside = race.frame(12, 0).p;
  const lane1 = race.frame(1, 0).p;
  const end = { x: -track.straight / 2, y: -r1 };
  const bendDone = (Math.PI / 2 - Math.atan2(lane1.y, lane1.x - track.straight / 2)) * r1;
  const lane1Route = Math.PI * r1 - bendDone + track.straight;
  near(Math.hypot(outside.x - end.x, outside.y - end.y), lane1Route, 0.05);
  // By 60 m everyone has funnelled in and is level along the track.
  near(race.frame(12, 60).p.x, race.frame(1, 60).p.x, 1e-6);
  near(race.frame(12, 60).p.y, race.frame(1, 60).p.y, 1e-6);
  assert.ok(race.startLine && race.startLine.length > 2);
});

test("from a waterfall start runners spread across the track, then gather on the inside", () => {
  const track = outdoorTrack(8);
  const race = course(track, 1500, 12);
  const out = (position: number, d: number) => radiusAt(track, race.frame(position, d).p) - track.kerb;
  assert.ok(out(12, 0) > out(1, 0) + 5, "the outside starter is across the track");
  assert.ok(out(12, 0) < lineRadius(track, 8) - track.kerb, "and on it");
  assert.ok(out(12, 200) < 3, "after 200 m the field is on the inside lanes");
});
