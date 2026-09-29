// Turning a race's data into runners for the track: each athlete's lane, and the known points
// (their reaction, each clean split, the finish) that their motion is drawn through.

import type { DisciplineOut, Index, RaceData, RacePerformance } from "../data/types";
import { printedDigits, roundName } from "../data/format";
import { seriesColor } from "../pages/race/model";
import { onStraight, WATERFALL } from "./geometry";

export interface Checkpoint {
  distance: number;
  label: string;
}

/** A stretch of the race between consecutive timing points (or the start, or the finish). */
export interface Stretch {
  key: string;
  from: number;
  to: number;
  label: string;
}

export function stretchKey(from: number, to: number): string {
  return `${from}-${to}`;
}

export interface Runner {
  id: string;
  athlete: string;
  name: string;
  short: string;
  lane: number;
  color: string;
  place: number | null;
  status: string;
  finish: number | null;
  /** Seconds from the gun to the athlete's reaction, where published. */
  reaction: number | null;
  /** Times at the checkpoints (clean splits only), by distance. */
  splits: Map<number, number>;
  /** The decimals each split was printed with, by distance, where not two. */
  digits?: Map<number, number>;
  knots: { t: number; d: number }[];
  /** Whether the runner's motion comes from measured splits, not just the finishing time. */
  timed: boolean;
  /** The reader's own runner (see model.ts). */
  ghost?: boolean;
  /** Whether the runner's motion comes from modelled splits, not published ones: the ghost,
   * and runners whose splits were not published (see model.ts). */
  modelled?: boolean;
  /** Whether ``lane`` is a stand-in: their lane was not published, so they run in one nobody
   * else did. */
  laneUnknown?: boolean;
}

export interface RaceOnTrack {
  distance: number;
  setting: string;
  /** The round, since heats are paced differently from finals. */
  round: string;
  /** Whether each runner is in the lane they ran in. A race on the straight whose lanes were
   * not published puts its runners in finishing order instead: there, lanes change nothing but
   * the picture. Round a bend, a runner whose lane was not published runs in one nobody else
   * did (see ``laneUnknown``), except from a waterfall start (1000 m and up), where there are no
   * lanes and ``lane`` is a position. */
  lanes: boolean;
  runners: Runner[];
  checkpoints: Checkpoint[];
  stretches: Stretch[];
  hurdles: number[];
  /** A race that was never run (runs compared side by side): places are the order across the
   * line, not the places the runs had in their own races. */
  virtual?: boolean;
}

type Names = Map<string, { name: string; family: string }>;
type Suspect = (performance: string, pointKey: string, format: string) => boolean;

export function raceOnTrack(race: RaceData, names: Names, discipline: DisciplineOut | undefined, suspect: Suspect): RaceOnTrack {
  const distance = race.points[race.points.length - 1]?.distance ?? discipline?.distance ?? 0;
  // Runners who are drawn: they finished, or have splits to run through.
  const drawn = (perf: RacePerformance) => perf.status === "finished" || perf.splits.length > 0;
  // From a waterfall start there are no lanes: runners take their finishing order across the
  // start line.
  const waterfall = distance >= WATERFALL;
  const lanes = !waterfall && (!onStraight(distance) || race.performances.filter(drawn).every((perf) => perf.lane));
  // Round a bend, runners whose lanes were not published take the lanes nobody used, in
  // finishing order.
  const used = new Set(race.performances.flatMap((perf) => (perf.lane ? [perf.lane.v] : [])));
  const spare = Array.from({ length: race.performances.length + used.size }, (_, k) => k + 1).filter((lane) => !used.has(lane));
  const runners: Runner[] = [];
  race.performances.forEach((perf, i) => {
    // In lanes, a runner has theirs (or a spare one if they ran); in finishing order, only those
    // who ran appear.
    if (lanes ? !perf.lane && !drawn(perf) : !drawn(perf)) return;
    const lane = !lanes ? runners.length + 1 : perf.lane ? perf.lane.v : spare.shift()!;
    const runner = runnerFrom(race, perf, distance, names, suspect, lane, seriesColor(i));
    runners.push(lanes && !perf.lane ? { ...runner, laneUnknown: true } : runner);
  });
  const checkpoints = timingPoints(race).map((p) => ({ distance: p.distance, label: p.label }));
  return {
    distance,
    setting: race.setting,
    round: race.round,
    lanes,
    runners,
    checkpoints,
    stretches: stretchesOf(checkpoints, distance),
    hurdles: hurdlesOf(discipline, race.sex),
  };
}

/** One performance as a runner: in ``lane`` (or at that place on the start line), moving
 * through the gun, their reaction, each clean split and the finish. */
function runnerFrom(race: RaceData, perf: RacePerformance, distance: number, names: Names, suspect: Suspect, lane: number, color: string): Runner {
  const reaction = perf.reactionTime && perf.reactionTime.v > 0 ? perf.reactionTime.v : 0;
  const splits = new Map<number, number>();
  const digits = new Map<number, number>();
  for (const split of perf.splits) {
    const point = race.points[split.point]!;
    if (point.kind === "finish") continue;
    if (suspect(perf.id, point.key, race.documents[split.doc]!.format)) continue;
    splits.set(point.distance, split.time.v);
    const printed = printedDigits(race.sources[split.time.s]?.text);
    if (printed !== 2) digits.set(point.distance, printed);
  }
  const finished = perf.status === "finished" && perf.time !== null;
  const knots = [{ t: 0, d: 0 }];
  if (reaction > 0) knots.push({ t: reaction, d: 0 });
  for (const [d, t] of [...splits].sort((a, b) => a[0] - b[0])) {
    if (t > knots[knots.length - 1]!.t) knots.push({ t, d });
  }
  if (finished) knots.push({ t: perf.time!.v, d: distance });
  const athlete = names.get(perf.athlete);
  return {
    id: perf.id,
    athlete: perf.athlete,
    name: athlete?.name ?? `${perf.givenName} ${perf.familyName}`,
    short: athlete?.family ?? perf.familyName,
    lane,
    color,
    place: perf.place?.v ?? null,
    status: perf.status,
    finish: finished ? perf.time!.v : null,
    reaction: reaction > 0 ? reaction : null,
    splits,
    digits,
    knots,
    timed: splits.size > 0,
  };
}

/** The race's timing points short of the finish. */
function timingPoints(race: RaceData) {
  return race.points.filter((p) => p.kind !== "start" && p.kind !== "finish");
}

function stretchesOf(checkpoints: Checkpoint[], distance: number): Stretch[] {
  const marks = [{ distance: 0, label: "Start" }, ...checkpoints, { distance, label: `${distance}m` }];
  return marks.slice(1).map((mark, i) => ({
    key: stretchKey(marks[i]!.distance, mark.distance),
    from: marks[i]!.distance,
    to: mark.distance,
    label: `${marks[i]!.label}–${mark.label}`,
  }));
}

function hurdlesOf(discipline: DisciplineOut | undefined, sex: string): number[] {
  const barrier = discipline?.barriers[sex];
  return barrier ? Array.from({ length: barrier.count }, (_, k) => barrier.first + k * barrier.spacing) : [];
}

const namesOf = (index: Index): Names => new Map(index.athletes.map((a) => [a.id, { name: a.name, family: a.familyName }]));

/** Whether a split is suspect (see the checks): the replay leaves it out. */
function suspectIn(race: RaceData): Suspect {
  const suspect = new Set(race.flags.filter((f) => f.suspect && f.field === "time").map((f) => f.subject));
  return (perf, point, format) => suspect.has(`${perf}/${point}@${format}`);
}

/** The track view of a race, with names from the index and suspect splits left out. */
export function raceOnTrackFrom(race: RaceData, index: Index): RaceOnTrack {
  return raceOnTrack(race, namesOf(index), index.disciplines.find((d) => d.id === race.discipline), suspectIn(race));
}

/** Lanes for a race that was never run, fastest first: the middle lanes, as a final is seeded. */
const SEEDED = { outdoor: [4, 5, 3, 6, 7, 2, 8, 1], indoor: [4, 5, 3, 6, 2, 1] };

/** A race that was never run: performances of one event on the same kind of track, from any
 * races, side by side, each in a lane of its own (seeded by time, as for a final) and in the
 * colour given. The standings compare them only where every timed one was timed, and place
 * them in the order they cross the line. */
export function comparisonOnTrack(picks: { race: RaceData; performance: string; color: string }[], index: Index): RaceOnTrack {
  const first = picks[0]!.race;
  const discipline = index.disciplines.find((d) => d.id === first.discipline);
  const distance = first.points[first.points.length - 1]?.distance ?? discipline?.distance ?? 0;
  const waterfall = distance >= WATERFALL;
  const names = namesOf(index);
  const built = picks.map(({ race, performance, color }) => {
    const perf = race.performances.find((p) => p.id === performance)!;
    return { race, runner: runnerFrom(race, perf, distance, names, suspectIn(race), 0, color) };
  });
  const seeds = SEEDED[first.setting === "indoor" ? "indoor" : "outdoor"];
  const fastest = [...built].sort((a, b) => (a.runner.finish ?? Infinity) - (b.runner.finish ?? Infinity));
  const lane = new Map(fastest.map(({ runner }, rank) => [runner.id, waterfall ? rank + 1 : seeds[rank] ?? rank + 1]));
  // The points every timed run was timed at (runs without splits run on modelled ones).
  const timed = built.filter(({ runner }) => runner.timed);
  const checkpoints = timingPoints(timed[0]?.race ?? first)
    .filter((p) => timed.every(({ race }) => timingPoints(race).some((q) => q.distance === p.distance)))
    .map((p) => ({ distance: p.distance, label: p.label }));
  const shared = new Set(checkpoints.map((c) => c.distance));
  const only = <T,>(values: Map<number, T>) => new Map([...values].filter(([d]) => shared.has(d)));
  const short = shortNames(
    built.map(({ race, runner }) => ({
      id: runner.id,
      athlete: runner.athlete,
      family: runner.short,
      competition: race.competition,
      date: race.date.v,
      round: race.round,
      heat: race.heat,
    })),
  );
  const runners = built.map(({ runner }) => ({
    ...runner,
    lane: lane.get(runner.id)!,
    short: short.get(runner.id)!,
    splits: only(runner.splits),
    digits: runner.digits && only(runner.digits),
  }));
  return {
    distance,
    setting: first.setting,
    round: "final",
    lanes: !waterfall,
    virtual: true,
    runners,
    checkpoints,
    stretches: stretchesOf(checkpoints, distance),
    hurdles: hurdlesOf(discipline, first.sex),
  };
}

/** A run, as much of it as telling one athlete's runs apart needs. */
export interface RunTag {
  id: string;
  athlete: string;
  family: string;
  competition: string;
  date: string;
  round: string;
  heat: number | null;
}

/** Family names, told apart where one athlete runs more than once by the year, else the place,
 * else both, else the round: "Hudson-Smith Paris", "Hudson-Smith London". The place is the one
 * the meeting is known by, from its ID ("og-2024-paris"), not the stadium's town. */
export function shortNames(runs: RunTag[]): Map<string, string> {
  const place = (run: RunTag) =>
    run.competition
      .split("-")
      .slice(2)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  const year = (run: RunTag) => `’${run.date.slice(2, 4)}`;
  const tags = [
    year,
    place,
    (run: RunTag) => `${place(run)} ${year(run)}`,
    (run: RunTag) => `${place(run)} ${roundName(run.round, run.heat)}`,
    (run: RunTag) => `${place(run)} ${year(run)} ${roundName(run.round, run.heat)}`,
  ];
  const names = new Map<string, string>();
  for (const run of runs) {
    const same = runs.filter((r) => r.athlete === run.athlete);
    if (same.length === 1) {
      names.set(run.id, run.family);
      continue;
    }
    const tag = tags.find((t) => new Set(same.map(t)).size === same.length) ?? tags[tags.length - 1]!;
    names.set(run.id, `${run.family} ${tag(run)}`);
  }
  return names;
}

/** A runner's time for a stretch, where both of its ends were timed. */
export function stretchTime(runner: Runner, stretch: Stretch, distance: number): number | null {
  const at = (d: number) => (d === 0 ? 0 : d === distance ? runner.finish : runner.splits.get(d) ?? null);
  const [a, b] = [at(stretch.from), at(stretch.to)];
  return a === null || b === null ? null : b - a;
}
