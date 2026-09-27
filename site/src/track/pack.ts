// Where runners run across the track once free of their lanes. Nothing in the data says; the
// splits give only how far along each runner is. So the replay places them as races are run:
// on the inside of lane 1, in single file, moving out only when someone is right in front of
// them (to go round) or alongside, and back in once clear of whoever is inside. A change of
// lane takes about half a second. The same race always packs the same way: the whole race is
// worked out once, forwards in time.

import type { Motion } from "./geometry";

/** Metres, centre to centre: a runner this close behind someone in the same lane has to go
 * round them (drafting runners sit about a metre back). */
const BLOCKED = 1.1;
/** Metres: how clear of someone ahead in the lane inside a runner must be to move in behind
 * them, and how far ahead of someone in it to move in in front of them. */
const ROOM = 1.7;
const CLEAR = 1.5;
/** Metres per second across the track. */
const SIDEWAYS = 2.5;
/** Lanes a pack spreads over at most. */
const WIDEST = 4;
/** Samples to work the race out on: every tenth of a second, or coarser for long races. */
const SAMPLES = 6000;

export interface Packing {
  /** How far out from lane 1 runner ``i`` is at time ``t``, in metres (0 in lane 1). */
  at: (i: number, t: number) => number;
}

/** Packs the runners whose ``motions`` are given, once they have run ``from`` metres (the break
 * line, or 0 from a waterfall start), until ``end``. */
export function packing(motions: Motion[], from: number, laneWidth: number, end: number): Packing {
  const step = Math.max(0.1, end / SAMPLES);
  const count = Math.ceil(end / step) + 1;
  const across = motions.map(() => new Float32Array(count));
  const lane: (number | null)[] = motions.map(() => null);
  const x = motions.map(() => 0);
  for (let k = 0; k < count; k++) {
    const t = k * step;
    // Everyone free and still running, from the front.
    const running: { i: number; d: number }[] = [];
    motions.forEach((motion, i) => {
      const d = motion.at(t);
      const stopped = d === null || (motion.finished && t >= motion.end);
      if (!stopped && d > from) running.push({ i, d });
    });
    running.sort((a, b) => b.d - a.d || (lane[a.i] ?? 0) - (lane[b.i] ?? 0));
    const placed: { d: number; lane: number }[] = [];
    // The nearest runner already placed in ``l`` who is level with ``d`` or ahead, how far ahead.
    const ahead = (l: number, d: number) =>
      Math.min(Infinity, ...placed.filter((p) => p.lane === l).map((p) => p.d - d));
    running.forEach(({ i, d }, rank) => {
      let l = lane[i] ?? null;
      if (l === null) {
        // Just free: the innermost lane with room, else the least crowded.
        l = innermost(0, d, ahead);
        x[i] = l * laneWidth;
      } else {
        // Those behind are not placed yet: where they were a moment ago.
        const behind = (m: number) => running.slice(rank + 1).some((o) => lane[o.i] === m && d - o.d < CLEAR);
        if (l > 0 && ahead(l - 1, d) > ROOM && !behind(l - 1)) l -= 1;
        else if (ahead(l, d) < BLOCKED) l = innermost(l + 1, d, ahead, l);
      }
      lane[i] = l;
      placed.push({ d, lane: l });
      const now = x[i]!;
      x[i] = now + Math.max(-SIDEWAYS * step, Math.min(SIDEWAYS * step, l * laneWidth - now));
    });
    motions.forEach((_, i) => {
      across[i]![k] = x[i]!;
    });
  }
  return {
    at: (i, t) => {
      const f = Math.min(Math.max(t / step, 0), count - 1);
      const k = Math.floor(f);
      const [a, b] = [across[i]![k]!, across[i]![Math.min(k + 1, count - 1)]!];
      return a + (b - a) * (f - k);
    },
  };
}

/** The innermost lane from ``first`` with nobody just ahead; if every lane is taken, the one
 * whose nearest runner ahead is furthest away (or ``stay``, if that is no better). */
function innermost(first: number, d: number, ahead: (lane: number, d: number) => number, stay?: number): number {
  let best = stay ?? first;
  let room = stay === undefined ? -Infinity : ahead(stay, d);
  for (let l = first; l < WIDEST; l++) {
    const gap = ahead(l, d);
    if (gap >= BLOCKED) return l;
    if (gap > room) [best, room] = [l, gap];
  }
  return best;
}
