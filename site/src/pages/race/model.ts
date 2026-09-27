// The race page's view of a race: one row per athlete with clean splits, colours in finishing
// order, and the derived gaps and speeds the charts show.

import type { FlagOut, Point, RaceData, RacePerformance, RaceSplit } from "../../data/types";

export interface Cell {
  split: RaceSplit;
  id: string;
  suspect: boolean;
  flags: FlagOut[];
}

export interface Row {
  perf: RacePerformance;
  name: string;
  short: string;
  color: string;
  /** Splits by point index, from the document with the most of them. */
  cells: Map<number, Cell>;
  finish: number | null;
}

export function seriesColor(index: number): string {
  return index < 8 ? `var(--series-${index + 1})` : "var(--series-other)";
}

export function flagsBySubject(race: RaceData): Map<string, FlagOut[]> {
  const map = new Map<string, FlagOut[]>();
  for (const flag of race.flags) {
    const list = map.get(flag.subject) ?? [];
    list.push(flag);
    map.set(flag.subject, list);
  }
  return map;
}

export function rows(race: RaceData, names: Map<string, { name: string; family: string }>): Row[] {
  const flags = flagsBySubject(race);
  return race.performances.map((perf, i) => {
    const byDoc = new Map<number, RaceSplit[]>();
    for (const split of perf.splits) {
      byDoc.set(split.doc, [...(byDoc.get(split.doc) ?? []), split]);
    }
    const primary = [...byDoc.values()].sort((a, b) => b.length - a.length)[0] ?? [];
    const cells = new Map<number, Cell>();
    for (const split of primary) {
      const point = race.points[split.point]!;
      if (point.kind === "finish") continue;
      const id = `${perf.id}/${point.key}@${race.documents[split.doc]!.format}`;
      const splitFlags = flags.get(id) ?? [];
      cells.set(split.point, {
        split,
        id,
        suspect: splitFlags.some((f) => f.suspect && f.field === "time"),
        flags: splitFlags,
      });
    }
    const athlete = names.get(perf.athlete);
    return {
      perf,
      name: athlete?.name ?? `${perf.givenName} ${perf.familyName}`,
      short: athlete?.family ?? perf.familyName,
      color: seriesColor(i),
      cells,
      finish: perf.status === "finished" && perf.time ? perf.time.v : null,
    };
  });
}

export function intermediatePoints(race: RaceData): { index: number; point: Point }[] {
  return race.points
    .map((point, index) => ({ index, point }))
    .filter(({ point }) => point.kind !== "finish");
}

export function raceDistance(race: RaceData): number {
  return race.points[race.points.length - 1]?.distance ?? 0;
}

/** The fastest clean time at each point, and at the finish. */
export function leaders(race: RaceData, all: Row[]): Map<number, number> {
  const best = new Map<number, number>();
  for (const row of all) {
    for (const [index, cell] of row.cells) {
      if (cell.suspect) continue;
      const current = best.get(index);
      if (current === undefined || cell.split.time.v < current) best.set(index, cell.split.time.v);
    }
  }
  const finishes = all.map((row) => row.finish).filter((f): f is number => f !== null);
  if (finishes.length) best.set(race.points.length - 1, Math.min(...finishes));
  return best;
}

export interface Previous {
  index: number | null;
  time: number;
  distance: number;
}

/** The clean timing point before ``index`` for ``row`` (the gun if none). */
export function previousClean(race: RaceData, row: Row, index: number): Previous {
  for (let i = index - 1; i >= 0; i--) {
    const cell = row.cells.get(i);
    if (cell && !cell.suspect) return { index: i, time: cell.split.time.v, distance: race.points[i]!.distance };
  }
  return { index: null, time: 0, distance: 0 };
}
