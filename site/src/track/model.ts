// Modelled runners: you, in the race at a time you choose (the ghost), and athletes whose
// splits were not published. Nothing here is data. Each runs the typical splits for their
// finishing time in this event (see ``plan`` in data/analysis.ts), so the replay can show them
// moving plausibly; the replay draws them dashed and the tables never show them.

import { gridsFor, onGrid, plan, type Plan } from "../data/analysis";
import type { EventData, RaceSummary } from "../data/types";
import { motion } from "./geometry";
import type { RaceOnTrack, Runner } from "./runners";

export const GHOST_ID = "ghost";

export interface Ghost {
  runner: Runner;
  /** The runs its splits were modelled on, or null if there were too few (then it runs at an
   * even effort). */
  basis: Basis | null;
}

export interface Basis {
  runs: number;
  fastest: number;
  slowest: number;
  extrapolated: boolean;
  /** The timing points modelled, e.g. "every 100 m". */
  every: string;
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

/** Typical splits for ``target`` in this race's event, from runs in the same setting (indoor
 * and outdoor 400 m are run differently) and the same kind of round when there are enough
 * (heats are eased off at the end; finals are not), on the race's own timing points if enough
 * runs share them, else on the most widely timed ones. */
export function typical(race: RaceOnTrack, target: number, event: EventData, races: RaceSummary[]): { plan: Plan; basis: Basis } | null {
  const info = new Map(races.map((r) => [r.id, r]));
  const perfs = event.performances.filter((p) => info.get(p.race)?.setting === race.setting);
  const grids = gridsFor(
    event,
    races.filter((r) => r.event === event.event && r.setting === race.setting),
    perfs,
  );
  const own = grids.find((g) => g.points.map((p) => p.distance).join() === race.checkpoints.map((c) => c.distance).join());
  const grid = own && own.count >= 30 ? own : grids[0];
  if (!grid) return null;
  const rows = onGrid(event, grid, perfs);
  const final = (id: string) => info.get(id)?.round === "final";
  const sameRound = rows.filter((row) => final(row.perf.race) === (race.round === "final"));
  const typicalPlan = plan(sameRound.length >= 20 ? sameRound : rows, grid, race.distance, target);
  if (!typicalPlan) return null;
  return {
    plan: typicalPlan,
    basis: {
      runs: typicalPlan.runs.length,
      fastest: typicalPlan.runs[0]!.finish,
      slowest: typicalPlan.runs[typicalPlan.runs.length - 1]!.finish,
      extrapolated: typicalPlan.extrapolated,
      every: grid.label.toLowerCase(),
    },
  };
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

/** A runner's path through the modelled splits: the gun, their reaction, each typical split
 * and the finish; and a time at every timing point of this race, read off that path, so the
 * runner can be compared stretch by stretch even where the model's points are coarser. */
function modelledPath(race: RaceOnTrack, finish: number, reaction: number, typicalPlan: Plan | null) {
  const splits = new Map<number, number>(
    (typicalPlan?.points ?? []).filter((p) => p.distance < race.distance).map((p) => [p.distance, p.time]),
  );
  const knots = [{ t: 0, d: 0 }, { t: reaction, d: 0 }];
  for (const [d, t] of [...splits].sort((a, b) => a[0] - b[0])) {
    if (t > knots[knots.length - 1]!.t) knots.push({ t, d });
  }
  knots.push({ t: finish, d: race.distance });
  const moving = motion(knots, true);
  for (const { distance } of race.checkpoints) {
    if (!splits.has(distance)) splits.set(distance, reach(moving.at, distance, finish));
  }
  return { splits, knots };
}

function medianReaction(race: RaceOnTrack): number {
  const reactions = race.runners
    .map((r) => r.reaction)
    .filter((r): r is number => r !== null)
    .sort((a, b) => a - b);
  return reactions.length ? reactions[Math.floor(reactions.length / 2)]! : 0.15;
}

export function makeGhost(race: RaceOnTrack, target: number, lane: number, event: EventData, races: RaceSummary[]): Ghost {
  const model = typical(race, target, event, races);
  const reaction = medianReaction(race);
  const { splits, knots } = modelledPath(race, target, reaction, model?.plan ?? null);
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
      reaction,
      splits,
      knots,
      timed: splits.size > 0,
      ghost: true,
      modelled: true,
    },
    basis: model?.basis ?? null,
  };
}

/** The race with every finisher who has no published splits given the typical splits for
 * their time, in their own event (``eventOf``: men and women race each other in comparisons).
 * Their split times are kept off the standings (see Standings.tsx): the order they imply
 * between the finish times is a guess. */
export function withModelledRunners(
  race: RaceOnTrack,
  eventOf: (runner: Runner) => EventData,
  races: RaceSummary[],
): { race: RaceOnTrack; basis: Basis | null } {
  let basis: Basis | null = null;
  const runners = race.runners.map((runner) => {
    if (runner.timed || runner.finish === null) return runner;
    const model = typical(race, runner.finish, eventOf(runner), races);
    if (!model) return runner;
    basis ??= model.basis;
    const { splits, knots } = modelledPath(race, runner.finish, runner.reaction ?? medianReaction(race), model.plan);
    return { ...runner, splits, knots, timed: true, modelled: true };
  });
  return { race: { ...race, runners }, basis };
}

/** Whether a race has finishers whose splits were not published, to model. */
export function needsModel(race: RaceOnTrack): boolean {
  return race.runners.some((runner) => !runner.timed && runner.finish !== null);
}
