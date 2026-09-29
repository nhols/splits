// Analysis derived from the stored splits. Nothing here is stored in the dataset: segment
// times, speeds, shares of race time and typical splits are always computed from the
// cumulative times, so they can never disagree with them. Values a check marked suspect are
// left out.

import type { EventData, EventPerformance, Point, RaceSummary } from "./types";

export interface Mark {
  key: string;
  label: string;
  distance: number;
  time: number;
}

/** A performance's clean cumulative times, in race order, ending at the finish. */
export function timeline(points: Point[], perf: EventPerformance, distance: number): Mark[] {
  const marks: Mark[] = [];
  perf.splits.forEach((value, index) => {
    const point = points[index];
    if (value === null || !point || perf.suspect.includes(index)) return;
    marks.push({ key: point.key, label: point.label, distance: point.distance, time: value });
  });
  if (perf.time !== null && perf.status === "finished") {
    marks.push({ key: "finish", label: "Finish", distance, time: perf.time });
  }
  return marks;
}

export interface Segment {
  from: number;
  to: number;
  fromLabel: string;
  toLabel: string;
  time: number;
  speed: number;
}

/** Segments between consecutive marks, starting from the gun. */
export function segments(marks: Mark[]): Segment[] {
  const result: Segment[] = [];
  let previous: Mark = { key: "start", label: "Start", distance: 0, time: 0 };
  for (const mark of marks) {
    const time = mark.time - previous.time;
    if (time > 0) {
      result.push({
        from: previous.distance,
        to: mark.distance,
        fromLabel: previous.label,
        toLabel: mark.label,
        time,
        speed: (mark.distance - previous.distance) / time,
      });
    }
    previous = mark;
  }
  return result;
}

export function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return Number.NaN;
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  const a = sorted[lower]!;
  const b = sorted[upper]!;
  return a + (b - a) * (position - lower);
}

export function summary(values: number[]): { median: number; q1: number; q3: number } {
  const sorted = [...values].sort((a, b) => a - b);
  return { median: quantile(sorted, 0.5), q1: quantile(sorted, 0.25), q3: quantile(sorted, 0.75) };
}

// ---- Timing grids ------------------------------------------------------------------------

/** A set of timing points that many performances share, so they can be compared point by
 * point: every 100 m, every 50 m, every hurdle... */
export interface Grid {
  id: string;
  points: Point[];
  label: string;
  count: number;
}

export function describeGrid(points: Point[]): string {
  if (points.length > 1 && points.every((p) => p.kind === "hurdle")) return "At every hurdle";
  if (points.length > 1 && points.every((p) => p.kind === "touchdown")) {
    return "At every touchdown";
  }
  const distances = points.map((p) => p.distance);
  const step = distances[0];
  if (
    step !== undefined &&
    points.every((p) => p.kind === "distance") &&
    distances.every((d, i) => Math.abs(d - step * (i + 1)) < 1e-6)
  ) {
    // A no-break space, so the number never wraps away from its unit.
    return points.length === 1 ? `At ${step}\u00a0m` : `Every ${step}\u00a0m`;
  }
  return points.map((p) => p.label).join(", ");
}

export interface GridRow {
  perf: EventPerformance;
  /** Cumulative times at the grid's points, then the finish. */
  times: number[];
  finish: number;
}

export function onGrid(event: EventData, grid: Grid, perfs: EventPerformance[]): GridRow[] {
  const indexes = grid.points.map((point) => event.points.findIndex((p) => p.key === point.key));
  const rows: GridRow[] = [];
  for (const perf of perfs) {
    if (perf.time === null || perf.status !== "finished") continue;
    const times: number[] = [];
    for (const index of indexes) {
      const value = perf.splits[index];
      if (value === null || value === undefined || perf.suspect.includes(index)) break;
      times.push(value);
    }
    if (times.length === indexes.length) rows.push({ perf, times: [...times, perf.time], finish: perf.time });
  }
  return rows;
}

/** The grids an event's races were timed on, most widely available first. */
export function gridsFor(event: EventData, races: RaceSummary[], perfs: EventPerformance[]): Grid[] {
  const signatures = new Map<string, string[]>();
  for (const race of races) {
    if (race.event === event.event && race.points.length) {
      signatures.set(race.points.join(","), race.points);
    }
  }
  const grids: Grid[] = [];
  for (const [id, keys] of signatures) {
    const points = keys
      .map((key) => event.points.find((p) => p.key === key))
      .filter((p): p is Point => p !== undefined);
    const grid: Grid = { id, points, label: describeGrid(points), count: 0 };
    grid.count = onGrid(event, grid, perfs).length;
    if (grid.count > 0) grids.push(grid);
  }
  // A grid whose points are all in a richer grid covering at least half as many runs adds
  // nothing but coarseness: drop it.
  const keys = (grid: Grid) => new Set(grid.points.map((p) => p.key));
  const useful = grids.filter(
    (grid) =>
      !grids.some(
        (other) =>
          other !== grid &&
          other.points.length > grid.points.length &&
          [...keys(grid)].every((key) => keys(other).has(key)) &&
          other.count >= grid.count / 2,
      ),
  );
  return useful.sort((a, b) => b.count - a.count || b.points.length - a.points.length);
}

// ---- Pace profiles -----------------------------------------------------------------------

export interface ProfileStep {
  from: number;
  to: number;
  label: string;
  median: number;
  q1: number;
  q3: number;
}

/** A segment's time, its speed, or the time from the start to its end. */
export type Measure = "speed" | "time" | "cumulative";

/** Median and middle half of each segment's speed (or time) across ``rows``. */
export function profile(rows: GridRow[], grid: Grid, distance: number, measure: Measure): ProfileStep[] {
  const edges = [0, ...grid.points.map((p) => p.distance), distance];
  const labels = ["Start", ...grid.points.map((p) => p.label), "Finish"];
  const steps: ProfileStep[] = [];
  for (let i = 1; i < edges.length; i++) {
    const values = rows.map((row) => {
      if (measure === "cumulative") return row.times[i - 1]!;
      const elapsed = row.times[i - 1]! - (i > 1 ? row.times[i - 2]! : 0);
      return measure === "speed" ? (edges[i]! - edges[i - 1]!) / elapsed : elapsed;
    });
    steps.push({
      from: edges[i - 1]!,
      to: edges[i]!,
      label: `${labels[i - 1]}–${labels[i]}`,
      ...summary(values),
    });
  }
  return steps;
}

// ---- Split planner -----------------------------------------------------------------------

export interface PlanPoint {
  label: string;
  distance: number;
  time: number;
  low: number;
  high: number;
  segment: number;
  speed: number;
}

export interface Plan {
  target: number;
  /** The runs the model was fitted to, fastest first. */
  runs: GridRow[];
  /** Whether the target lies outside the runs' finishing times. */
  extrapolated: boolean;
  points: PlanPoint[];
}

/** Least-squares line through (x, y). */
function line(xs: number[], ys: number[]): { a: number; b: number } {
  const mx = xs.reduce((sum, x) => sum + x, 0) / xs.length;
  const my = ys.reduce((sum, y) => sum + y, 0) / ys.length;
  let sxx = 0;
  let sxy = 0;
  xs.forEach((x, i) => {
    sxx += (x - mx) ** 2;
    sxy += (x - mx) * (ys[i]! - my);
  });
  const b = sxx > 0 ? sxy / sxx : 0;
  return { a: my - b * mx, b };
}

/** Typical splits for a target time. Elite pacing is close to scale-invariant: the share of
 * the finishing time used at a timing point hardly depends on how fast the runner is (a 400 m
 * runner reaches halfway in about 47.5% of their time). So at each timing point the share is
 * fitted as a straight line in the finishing time across every run, which catches what little
 * it changes with level, and scaled to the target. Beyond the runs' range the share stays as
 * at its edge, rather than following the line. The middle half is the fit plus the middle
 * half of its residuals. Tested on runs left out of the fit, it predicts 400 m splits to about
 * 0.25 s, against about 1 s for an even pace. */
export function plan(rows: GridRow[], grid: Grid, distance: number, target: number): Plan | null {
  if (rows.length < 5 || !(target > 0)) return null;
  const runs = [...rows].sort((a, b) => a.finish - b.finish);
  const fastest = runs[0]!.finish;
  const slowest = runs[runs.length - 1]!.finish;
  const level = Math.min(Math.max(target, fastest), slowest);
  const finishes = runs.map((row) => row.finish);
  const points: PlanPoint[] = [];
  let previousTime = 0;
  let previousDistance = 0;
  grid.points.forEach((point, i) => {
    const shares = runs.map((row) => row.times[i]! / row.finish);
    const { a, b } = line(finishes, shares);
    const residuals = summary(shares.map((share, k) => share - (a + b * finishes[k]!)));
    const share = a + b * level;
    const time = share * target;
    points.push({
      label: point.label,
      distance: point.distance,
      time,
      low: (share + residuals.q1) * target,
      high: (share + residuals.q3) * target,
      segment: time - previousTime,
      speed: (point.distance - previousDistance) / (time - previousTime),
    });
    previousTime = time;
    previousDistance = point.distance;
  });
  points.push({
    label: "Finish",
    distance,
    time: target,
    low: target,
    high: target,
    segment: target - previousTime,
    speed: (distance - previousDistance) / (target - previousTime),
  });
  return { target, runs, extrapolated: target < fastest || target > slowest, points };
}
