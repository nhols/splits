// Track geometry: where a runner is, given the distance they have run, the lane they run in
// and the kind of race. Distances follow the World Athletics rules: each lane is measured
// along a line 0.30 m outside the kerb (lane 1) or 0.20 m outside the lane's inner line
// (other lanes), and staggered starts make every lane the same distance to the finish.
//
// Coordinates are metres from the centre of the infield, x to the right and y down, with the
// home straight along the bottom and the finish line at its right-hand end, so athletes run
// anticlockwise, the infield on their left.

export interface Track {
  kind: "outdoor" | "indoor";
  /** Length of each straight. */
  straight: number;
  /** Radius of the kerb (the inside edge of lane 1) on the bends. */
  kerb: number;
  laneWidth: number;
  lanes: number;
}

/** The standard 400 m track: 84.39 m straights and 36.50 m bends. */
export function outdoorTrack(lanes = 8): Track {
  return { kind: "outdoor", straight: 84.39, kerb: 36.5, laneWidth: 1.22, lanes };
}

/** A 200 m indoor oval: bends of 17.20 m radius, the straights sized so lane 1 measures 200 m.
 * Real indoor tracks vary, and their bends are banked; this is drawn to typical dimensions. */
export function indoorTrack(lanes = 6): Track {
  const kerb = 17.2;
  return { kind: "indoor", straight: (200 - 2 * Math.PI * (kerb + 0.3)) / 2, kerb, laneWidth: 1.0, lanes };
}

export interface Point {
  x: number;
  y: number;
}

/** The radius of the line along which a lane is measured. */
export function laneRadius(track: Track, lane: number): number {
  return lane <= 1 ? track.kerb + 0.3 : track.kerb + (lane - 1) * track.laneWidth + 0.2;
}

/** Radius of the line between two lanes (0: the kerb; n: the outside of lane n). */
export function lineRadius(track: Track, line: number): number {
  return track.kerb + line * track.laneWidth;
}

export function lapLength(track: Track, radius: number): number {
  return 2 * track.straight + 2 * Math.PI * radius;
}

/** The point ``s`` metres along the loop of the given radius, counted anticlockwise from the
 * finish line (the start of the first bend). Negative ``s`` runs back along the home straight,
 * as for a 100 m start. */
export function pointAt(track: Track, radius: number, s: number): Point {
  const half = track.straight / 2;
  if (s < 0) return { x: half + s, y: radius };
  const bend = Math.PI * radius;
  const lap = 2 * track.straight + 2 * bend;
  let d = s % lap;
  if (d <= bend) {
    const angle = Math.PI / 2 - d / radius;
    return { x: half + radius * Math.cos(angle), y: radius * Math.sin(angle) };
  }
  d -= bend;
  if (d <= track.straight) return { x: half - d, y: -radius };
  d -= track.straight;
  if (d <= bend) {
    const angle = -Math.PI / 2 - d / radius;
    return { x: -half + radius * Math.cos(angle), y: radius * Math.sin(angle) };
  }
  d -= bend;
  return { x: -half + d, y: radius };
}

/** How far a point is from the middle of the nearest bend, or from the centre line on the
 * straights: the radius of the loop through it. */
export function radiusAt(track: Track, p: Point): number {
  const half = track.straight / 2;
  if (p.x > half) return Math.hypot(p.x - half, p.y);
  if (p.x < -half) return Math.hypot(p.x + half, p.y);
  return Math.abs(p.y);
}

/** The unit vector pointing out of the infield at ``s`` along the loop of the given radius. */
export function outward(track: Track, radius: number, s: number): Point {
  const p = pointAt(track, radius, s);
  const half = track.straight / 2;
  if (p.x > half) return normalise({ x: p.x - half, y: p.y });
  if (p.x < -half) return normalise({ x: p.x + half, y: p.y });
  return { x: 0, y: Math.sign(p.y) || 1 };
}

function normalise(v: Point): Point {
  const length = Math.hypot(v.x, v.y) || 1;
  return { x: v.x / length, y: v.y / length };
}

/** An SVG path for the whole loop at a radius. */
export function loopPath(track: Track, radius: number, scale: (p: Point) => Point): string {
  const half = track.straight / 2;
  const a = scale({ x: half, y: radius });
  const b = scale({ x: half, y: -radius });
  const c = scale({ x: -half, y: -radius });
  const d = scale({ x: -half, y: radius });
  // The radius as drawn, whichever way the drawing is turned.
  const [o, e] = [scale({ x: 0, y: 0 }), scale({ x: radius, y: 0 })];
  const r = Math.hypot(e.x - o.x, e.y - o.y);
  return `M${a.x},${a.y} A${r},${r} 0 0 0 ${b.x},${b.y} L${c.x},${c.y} A${r},${r} 0 0 0 ${d.x},${d.y} Z`;
}

// ---- Races on the track ---------------------------------------------------------------------

export interface Frame {
  /** Where the runner is. */
  p: Point;
  /** The unit vector across the lane, away from the infield. */
  n: Point;
}

export interface Course {
  track: Track;
  distance: number;
  /** Where the runner in ``lane`` is after running ``d`` metres, and which way is outward. Out
   * of lanes, ``free`` is how far out from lane 1 they are heading: 0 in lane 1, a lane width
   * more for each runner inside them (see pack.ts). */
  frame: (lane: number, d: number, free?: number) => Frame;
  /** Distance after which runners may leave their lanes, if they may: 0 from a waterfall start. */
  breakAt: number | null;
}

/** Races run on a straight: 60 m indoors, and the 100 m and sprint hurdles outdoors, started in
 * an extension of the home straight beyond the bend. They are drawn on a straight of their own
 * (see Straight.tsx), not round the oval. */
export const STRAIGHT_RACE = 110;

export function onStraight(distance: number): boolean {
  return distance <= STRAIGHT_RACE + 1e-6;
}

/** Where lane 1 starts a race of ``distance``, in metres along the loop from the finish line:
 * every race ends on the finish line, so a 1500 m starts 100 m past it, a mile 9.34 m short. */
export function startOf(track: Track, distance: number): number {
  const lap = lapLength(track, laneRadius(track, 1));
  return (lap - (distance % lap)) % lap;
}

/** Races from 1000 m start from a curved (waterfall) line, without lanes. */
export const WATERFALL = 1000;

/** How a race uses the track: in lanes all the way (outdoors to the 400 m, hurdles; the 200 m
 * indoors); in lanes to a break line, then free to cut in over the straight that follows (the
 * 800 m outdoors after one bend, the 400 m indoors after two); or, from 1000 m, from a
 * waterfall start without lanes, the ``field`` starters side by side across the track and
 * funnelling in over the first 60 m. Once free, runners head for their place across the track,
 * ``free``: lane 1 unless someone is in the way. */
export function course(track: Track, distance: number, field = 8): Course {
  const inLane = (lane: number, s: number): Frame => {
    const radius = laneRadius(track, lane);
    return { p: pointAt(track, radius, s), n: outward(track, radius, s) };
  };
  const r1 = laneRadius(track, 1);
  const lap1 = lapLength(track, r1);
  const s0 = startOf(track, distance);
  if (distance <= lap1 + 1e-6) {
    // Staggered so that every lane measures ``distance`` to the finish line.
    const start = (lane: number) =>
      distance > track.straight + 1e-6
        ? lapLength(track, laneRadius(track, lane)) - distance
        : -distance;
    return { track, distance, frame: (lane, d) => inLane(lane, start(lane) + d), breakAt: null };
  }

  // Off the inside, converging on a place across the track: from ``from`` metres out to ``to``.
  const converging = (s: number, from: number, to: number, progress: number): Frame => {
    const eased = progress * progress * (3 - 2 * progress);
    const offset = from + (to - from) * eased;
    const base = pointAt(track, r1, s);
    const n = outward(track, r1, s);
    return { p: { x: base.x + n.x * offset, y: base.y + n.y * offset }, n };
  };
  if (distance >= WATERFALL) {
    const width = lineRadius(track, track.lanes) - track.kerb - 0.6;
    const across = (position: number) => ((position - 1) / Math.max(field - 1, 1)) * width;
    return {
      track,
      distance,
      breakAt: 0,
      frame: (position, d, free = 0) => converging(s0 + d, across(position), free, Math.min(Math.max(d, 0) / 60, 1)),
    };
  }

  // In lanes to the break line, staggered so that every lane measures the same to it.
  const bends = track.kind === "indoor" ? 2 : 1;
  const breakAt = bends * Math.PI * r1 + (bends === 2 ? track.straight : 0);
  const start = (lane: number) => s0 + bends * Math.PI * (laneRadius(track, lane) - r1);
  return {
    track,
    distance,
    breakAt,
    frame: (lane, d, free = 0) => {
      if (d <= breakAt) return inLane(lane, start(lane) + d);
      const from = laneRadius(track, lane) - r1;
      return converging(start(1) + d, from, free, Math.min((d - breakAt) / track.straight, 1));
    },
  };
}

// ---- Motion from splits ---------------------------------------------------------------------

export interface Motion {
  /** Distance run at time ``t`` seconds after the gun, or null before or after it is known. */
  at: (t: number) => number | null;
  finished: boolean;
  /** When the last known point was reached. */
  end: number;
}

/** How runners in an event typically spread their time over its distance: the share of the
 * race (from leaving the blocks to the finish) used up on reaching each distance, ending at the
 * finish with a share of 1. */
export type RaceShape = { distance: number; share: number }[];

/** Distance over time through the known points (the gun, the reaction, each clean split, the
 * finish), passing exactly through every published time.
 *
 * With the event's ``shape`` (events up to 800 m), each known point is placed by how far through
 * a typical race its distance is, and a smooth curve drawn through them on that scale: between
 * splits the runner moves as a typical runner does, bent to their own race, and a runner with
 * only a finish time runs the typical race (see docs/replay-positions.md). Without one, the curve
 * is drawn through the points in metres.
 *
 * Either way, from the blocks to the first point the runner accelerates as sprinters do, their
 * speed rising towards a top speed with a time constant of about a second (Furusawa and Hill's
 * model), reaching it at the pace of the stretch that follows. With a shape that first point is
 * the shape's own first (10 m in a sprint), unless the runner was timed sooner. The curves are
 * monotone cubics, so the motion is smooth and never runs backwards. */
export function motion(points: { t: number; d: number }[], finished: boolean, shape?: RaceShape | null): Motion {
  const knots = [...points].sort((a, b) => a.t - b.t);
  const last = knots[knots.length - 1];
  const finish = shape?.[shape.length - 1]?.distance;
  if (shape && finish !== undefined && last && last.d > 0 && last.d <= finish + 1e-6) return shaped(knots, finished, shape);
  return inMetres(knots, finished);
}

/** Metres between samples of a shaped motion: close enough that straight lines between them
 * look like the curve. */
const SAMPLE = 0.25;

function shaped(knots: { t: number; d: number }[], finished: boolean, shape: RaceShape): Motion {
  const n = knots.length;
  const end = knots[n - 1]!.t;
  let blocks = 0;
  while (blocks + 1 < n && knots[blocks + 1]!.d <= knots[0]!.d) blocks++;
  const off = knots[blocks]!;
  const known = knots.slice(blocks + 1);
  // How far through a typical race each distance is, and when this runner got there.
  const typical = [{ t: 0, d: 0 }, ...shape.map((p) => ({ t: p.distance, d: p.share }))];
  const share = curveThrough(typical);
  const when = curveThrough([{ t: 0, d: off.t }, ...known.map((k) => ({ t: share(k.d), d: k.t }))]);
  const time = (d: number) => when(share(d));
  // The acceleration from the blocks, to the shape's first point or the runner's, if sooner.
  const reach = Math.min(shape[0]!.distance, known[0]!.d);
  const lastD = known[known.length - 1]!.d;
  const arrive = time(reach);
  const ahead = Math.min(reach + 1, lastD);
  const start = acceleration(arrive - off.t, reach, ahead > reach ? (ahead - reach) / (time(ahead) - arrive) : null);
  // Sampled once: the time at every distance, so where a runner is at a moment is a lookup.
  const ts: number[] = [off.t];
  const ds: number[] = [0];
  const step = (arrive - off.t) / Math.max(Math.ceil((arrive - off.t) / 0.02), 1);
  for (let t = off.t + step; t < arrive - 1e-9; t += step) {
    ts.push(t);
    ds.push(start.at(t - off.t));
  }
  const marks = new Set(known.map((k) => k.d));
  for (let d = reach; d < lastD; d += SAMPLE) marks.add(d);
  for (const d of [...marks].filter((d) => d >= reach).sort((a, b) => a - b)) {
    const t = d === reach ? arrive : time(d);
    if (t > ts[ts.length - 1]! && d > ds[ds.length - 1]!) {
      ts.push(t);
      ds.push(d);
    }
  }
  return {
    finished,
    end,
    at: (t) => {
      if (t < 0) return null;
      if (t <= off.t) return off.d;
      if (t >= end) return finished || t === end ? lastD : null;
      let [lo, hi] = [0, ts.length - 1];
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (ts[mid]! <= t) lo = mid;
        else hi = mid;
      }
      return ds[lo]! + ((ds[hi]! - ds[lo]!) * (t - ts[lo]!)) / (ts[hi]! - ts[lo]!);
    },
  };
}

/** A smooth curve through ``points`` (``t`` across, ``d`` up) that rises wherever they do. */
function curveThrough(points: { t: number; d: number }[]): (x: number) => number {
  const slopes = monotoneSlopes(points, null);
  const n = points.length;
  return (x) => {
    if (n === 1) return points[0]!.d;
    let i = 0;
    while (i < n - 2 && points[i + 1]!.t < x) i++;
    return hermite(points[i]!, points[i + 1]!, slopes[i]!, slopes[i + 1]!, x);
  };
}

function hermite(a: { t: number; d: number }, b: { t: number; d: number }, sa: number, sb: number, x: number): number {
  const h = b.t - a.t;
  const u = (x - a.t) / h;
  const h00 = 2 * u ** 3 - 3 * u ** 2 + 1;
  const h10 = u ** 3 - 2 * u ** 2 + u;
  const h01 = -2 * u ** 3 + 3 * u ** 2;
  const h11 = u ** 3 - u ** 2;
  return h00 * a.d + h10 * h * sa + h01 * b.d + h11 * h * sb;
}

function inMetres(points: { t: number; d: number }[], finished: boolean): Motion {
  const knots = [...points].sort((a, b) => a.t - b.t);
  const n = knots.length;
  const end = knots[n - 1]?.t ?? 0;
  // The runner leaves the blocks at the last point still at the start: the gun or their reaction.
  let blocks = 0;
  while (blocks + 1 < n && knots[blocks + 1]!.d <= knots[0]!.d) blocks++;
  const off = knots[blocks];
  const first = knots[blocks + 1];
  const next = knots[blocks + 2];
  const start =
    off && first
      ? acceleration(first.t - off.t, first.d - off.d, next ? (next.d - first.d) / (next.t - first.t) : null)
      : null;
  const slopes = monotoneSlopes(knots, start ? { index: blocks + 1, slope: start.speed } : null);
  return {
    finished,
    end,
    at: (t) => {
      if (n === 0 || t < 0) return null;
      if (t <= off!.t) return off!.d;
      if (t >= end) return finished || t === end ? knots[n - 1]!.d : null;
      if (start && t <= first!.t) return off!.d + start.at(t - off!.t);
      // The last knot at or before t (binary search: long races have a hundred knots).
      let [i, hi] = [blocks + 1, n - 2];
      while (i < hi) {
        const mid = (i + hi + 1) >> 1;
        if (knots[mid]!.t < t) i = mid;
        else hi = mid - 1;
      }
      const a = knots[i]!;
      const b = knots[i + 1]!;
      const h = b.t - a.t;
      const u = (t - a.t) / h;
      const h00 = 2 * u ** 3 - 3 * u ** 2 + 1;
      const h10 = u ** 3 - 2 * u ** 2 + u;
      const h01 = -2 * u ** 3 + 3 * u ** 2;
      const h11 = u ** 3 - u ** 2;
      return h00 * a.d + h10 * h * slopes[i]! + h01 * b.d + h11 * h * slopes[i + 1]!;
    },
  };
}

/** Each pulse trails the distance its runner covered in this many seconds. */
export const TAIL = 0.9;

export interface Pulse {
  /** The distances the pulse runs between: where the runner was ``TAIL`` seconds ago (at least
   * 2.2 m back, so a runner standing still is a short bar), and where they are now. */
  from: number;
  to: number;
  /** When the runner was where the pulse's head is: now, or when they stopped. */
  at: number;
  /** A runner who did not finish fades out after their last known point. */
  opacity: number;
}

/** A runner's pulse at time ``t``, or null when they are not on the track. */
export function pulseAt(moving: Motion, finished: boolean, t: number): Pulse | null {
  const stopped = !finished && t > moving.end;
  const opacity = stopped ? Math.max(0, 1 - (t - moving.end) / 1.5) : 1;
  const now = stopped ? moving.end : t;
  const d = moving.at(now);
  if (d === null || opacity === 0) return null;
  const back = moving.at(Math.max(now - TAIL, 0)) ?? 0;
  return { from: Math.min(back, d - 2.2), to: d, at: now, opacity };
}

/** Running ``distance`` in ``duration`` from standing, with speed ``v(t) = top·(1 − e^(−t/τ))``.
 * Given the speed at the end (the pace of the next stretch), τ is chosen to reach it, within
 * the range seen in elite sprinting; otherwise τ is a typical 1.2 s. */
function acceleration(duration: number, distance: number, arrival: number | null) {
  const average = distance / duration;
  let tau = 1.2;
  if (arrival !== null && arrival > average) {
    // The ratio of average to arrival speed fixes x = duration / τ: solve by bisection.
    const ratio = average / arrival;
    const g = (x: number) => (1 - (1 - Math.exp(-x)) / x) / (1 - Math.exp(-x));
    let [lo, hi] = [1e-3, 200];
    for (let k = 0; k < 60; k++) {
      const mid = (lo + hi) / 2;
      if (g(mid) < ratio) lo = mid;
      else hi = mid;
    }
    tau = Math.min(Math.max(duration / lo, 0.7), 1.8);
  }
  const top = distance / (duration - tau * (1 - Math.exp(-duration / tau)));
  return {
    at: (t: number) => top * (t - tau * (1 - Math.exp(-t / tau))),
    speed: top * (1 - Math.exp(-duration / tau)),
  };
}

/** Fritsch–Carlson slopes: a cubic through the knots that never runs backwards. A fixed slope
 * (the speed at the end of the acceleration) is kept, and its neighbour adjusted to suit. */
function monotoneSlopes(knots: { t: number; d: number }[], fixed: { index: number; slope: number } | null): number[] {
  const n = knots.length;
  if (n < 2) return knots.map(() => 0);
  const secant = knots.slice(1).map((k, i) => (k.d - knots[i]!.d) / (k.t - knots[i]!.t));
  const slopes = knots.map((_, i) => {
    if (i === 0) return secant[0]!;
    if (i === n - 1) return secant[n - 2]!;
    const [a, b] = [secant[i - 1]!, secant[i]!];
    return a * b <= 0 ? 0 : (a + b) / 2;
  });
  if (fixed) slopes[fixed.index] = fixed.slope;
  for (let i = 0; i < n - 1; i++) {
    const s = secant[i]!;
    if (s === 0) {
      if (fixed?.index !== i) slopes[i] = 0;
      if (fixed?.index !== i + 1) slopes[i + 1] = 0;
      continue;
    }
    const alpha = slopes[i]! / s;
    const beta = slopes[i + 1]! / s;
    if (alpha * alpha + beta * beta <= 9) continue;
    if (fixed?.index === i) {
      slopes[i + 1] = Math.sqrt(Math.max(9 - alpha * alpha, 0)) * s;
    } else if (fixed?.index === i + 1) {
      slopes[i] = Math.sqrt(Math.max(9 - beta * beta, 0)) * s;
    } else {
      const tau = 3 / Math.sqrt(alpha * alpha + beta * beta);
      slopes[i] = tau * alpha * s;
      slopes[i + 1] = tau * beta * s;
    }
  }
  return slopes;
}
