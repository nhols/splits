// The modelled runner: you, in the race at a time you choose (the ghost). Nothing here is data.
// You run as a runner whose only published time is a finish does: the event's typical race,
// scaled to your time (see docs/replay-positions.md), so the replay can show you moving
// plausibly; the replay draws you dashed and the tables never show you.

import type { EventOut } from "../data/types";
import { motion } from "./geometry";
import type { RaceOnTrack, Runner } from "./runners";

export const GHOST_ID = "ghost";

export interface Ghost {
  runner: Runner;
  /** The runs the event's typical race is the median of, or null where it has none (above
   * 800 m, or too few runs timed finely enough): then you run at an even pace. */
  basis: Basis | null;
}

export interface Basis {
  runs: number;
}

/** A time typed as seconds ("47.5") or minutes and seconds ("1:47.50"). */
export function parseTime(text: string): number | null {
  const match = /^\s*(?:(\d+):)?(\d+(?:\.\d+)?)\s*$/.exec(text);
  if (!match) return null;
  const seconds = Number(match[1] ?? 0) * 60 + Number(match[2]);
  return seconds > 0 ? seconds : null;
}

/** The lanes a ghost could run in: those no athlete used, else one outside them all. */
export function freeLanes(race: RaceOnTrack): number[] {
  const used = new Set(race.runners.filter((r) => !r.ghost).map((r) => r.lane));
  const lanes = Math.max(race.setting === "indoor" ? 6 : 8, ...used);
  const free = Array.from({ length: lanes }, (_, i) => i + 1).filter((lane) => !used.has(lane));
  return free.length ? free : [lanes + 1];
}

/** When the motion reaches ``distance`` (it never runs backwards, so bisect). */
function reach(at: (t: number) => number | null, distance: number, end: number): number {
  let [lo, hi] = [0, end];
  for (let k = 0; k < 50; k++) {
    const mid = (lo + hi) / 2;
    if ((at(mid) ?? 0) < distance) lo = mid;
    else hi = mid;
  }
  return hi;
}

/** You, finishing in ``target``, in ``lane``: leaving the blocks at the event's typical reaction
 * and running its typical race, with a time read off it at every timing point of this race, so
 * you can be compared stretch by stretch. */
export function makeGhost(race: RaceOnTrack, target: number, lane: number, event: EventOut | undefined): Ghost {
  const reaction = event?.reaction ?? 0;
  const shape = event?.shape?.points ?? null;
  const knots = [{ t: 0, d: 0 }, ...(reaction > 0 ? [{ t: reaction, d: 0 }] : []), { t: target, d: race.distance }];
  const moving = motion(knots, true, shape);
  const splits = new Map(race.checkpoints.map((c) => [c.distance, reach(moving.at, c.distance, target)]));
  return {
    runner: {
      id: GHOST_ID,
      athlete: "",
      name: "You",
      short: "You",
      lane,
      color: "var(--ink)",
      place: null,
      status: "finished",
      finish: target,
      reaction: reaction > 0 ? reaction : null,
      splits,
      knots,
      shape,
      timed: splits.size > 0,
      ghost: true,
      modelled: true,
    },
    basis: event?.shape ? { runs: event.shape.runs } : null,
  };
}
