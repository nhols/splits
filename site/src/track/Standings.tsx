// Who is where during a replay, by the published times: the standings beside the track.

import { useLayoutEffect, useRef, type CSSProperties, type RefObject } from "react";
import { gap, time } from "../data/format";
import type { Motion } from "./geometry";
import { stretchTime, type RaceOnTrack, type Runner, type Stretch } from "./runners";

export interface Standing {
  runner: Runner;
  finished: boolean;
  /** The place once across the line (unless you are in the race), else the position. */
  rank: number | null;
  /** Where the runner was last timed ("50m"), the time there and the gap to the fastest there;
   * once across the line, the finishing time and the gap to the winner. */
  where: string | null;
  value: string;
  behind: string | null;
  /** Whether the value is modelled rather than published (only ever before the finish). */
  modelled: boolean;
}

/** Who is where at time ``t``: finishers in finishing order, then the rest by the last timing
 * point they have passed and their time there (the order the splits give, not the interpolated
 * positions between them), then those out of the race (a pacemaker who has stepped off). The
 * timing points are everyone's: a runner not timed at one someone else was is compared there
 * by when their motion passed it, so a missing split does not drop them down the order. */
export function standings(race: RaceOnTrack, motions: Motion[], t: number): Standing[] {
  const runners = race.runners;
  const labels = new Map(race.checkpoints.map((c) => [c.distance, c.label]));
  const points = [...new Set(runners.flatMap((r) => [...r.splits.keys()]))].sort((a, b) => b - a);
  const passed = (runner: Runner) =>
    [...runner.splits].filter(([, when]) => when <= t).sort((a, b) => b[0] - a[0])[0] ?? null;
  const rows = runners.map((runner, i) => {
    const split = passed(runner);
    const d = motions[i]!.at(t) ?? -1;
    // The furthest timing point passed, and when: their split there, else when they ran past it.
    const point = points.find((p) => p <= d || p === split?.[0]);
    const at = point === undefined ? null : (runner.splits.get(point) ?? passedAt(motions[i]!, point, t));
    return {
      runner,
      finished: runner.finish !== null && t >= runner.finish,
      // Stopped short of the finish, and past the last point they were timed at.
      out: runner.finish === null && runner.knots.length > 0 && t > runner.knots[runner.knots.length - 1]!.t,
      split,
      mark: point === undefined || at === null ? null : ([point, at] as const),
      d,
    };
  });
  rows.sort((a, b) => {
    if (a.finished || b.finished) {
      return a.finished && b.finished ? a.runner.finish! - b.runner.finish! : Number(b.finished) - Number(a.finished);
    }
    if (a.out !== b.out) return Number(a.out) - Number(b.out);
    const [da, db] = [a.mark?.[0] ?? -1, b.mark?.[0] ?? -1];
    if (da !== db) return db - da;
    if (a.mark && b.mark && a.mark[1] !== b.mark[1]) return a.mark[1] - b.mark[1];
    return b.d - a.d;
  });
  // Gaps are to the fastest published time, when there is one.
  const measured = runners.filter((r) => !r.modelled);
  const best = new Map<number, number>();
  for (const runner of measured.length ? measured : runners) {
    for (const [distance, when] of runner.splits) {
      if (when <= t) best.set(distance, Math.min(best.get(distance) ?? Infinity, when));
    }
  }
  const winner = Math.min(...runners.map((r) => r.finish ?? Infinity));
  // With a ghost in the race, or in a race that was never run, places are the order across the
  // line.
  const hypothetical = race.virtual || runners.some((r) => r.ghost);
  return rows.map(({ runner, finished, out, split }, i) => {
    // An athlete's modelled position is a guess: they are placed only at the finish. Nobody out
    // of the race has a position.
    const rank = finished && !hypothetical ? runner.place : out || (runner.modelled && !runner.ghost) ? null : i + 1;
    const plain = { runner, finished, rank, where: null, behind: null, modelled: false };
    if (finished) {
      const behind = runner.finish! - winner;
      return { ...plain, value: time(runner.finish), behind: behind > 0.004 ? gap(behind) : null };
    }
    if (out) return { ...plain, value: runner.status.toUpperCase() };
    if (!split) {
      const reacted = runner.reaction !== null && t >= runner.reaction;
      return { ...plain, value: reacted ? `RT ${runner.reaction!.toFixed(3)}` : "" };
    }
    const fastest = best.get(split[0]);
    const behind = fastest === undefined ? 0 : split[1] - fastest;
    const digits = runner.digits?.get(split[0]) ?? 2;
    const shown = Math.abs(behind) >= 0.5 * 10 ** -digits;
    return {
      ...plain,
      where: labels.get(split[0]) ?? `${split[0]}m`,
      value: `${runner.modelled ? "≈" : ""}${time(split[1], digits)}`,
      behind: shown ? gap(behind, digits) : null,
      modelled: Boolean(runner.modelled),
    };
  });
}

/** When ``motion`` reached ``distance``, at or before ``t`` (it never runs backwards). */
function passedAt(motion: Motion, distance: number, t: number): number {
  let [lo, hi] = [0, t];
  for (let k = 0; k < 40; k++) {
    const mid = (lo + hi) / 2;
    if ((motion.at(mid) ?? -1) >= distance) hi = mid;
    else lo = mid;
  }
  return hi;
}

/** Seconds (of the reader's time, whatever the playback speed) that passing a split flashes for. */
export const FLASH = 0.9;

/** A runner's latest split (or their finish) while it still flashes: where and when it was, and
 * how far through its flash the replay is (0 at the split, 1 when it is over). */
export interface Flash {
  distance: number;
  at: number;
  f: number;
}

/** Everyone still flashing at time ``t`` from passing a split, by runner, for flashes ``span``
 * seconds of race time long. Driven by the race clock alone, so the flash on the track and the
 * one in the standings are the same moment, playing, paused or scrubbed. */
export function splitFlashes(race: RaceOnTrack, t: number, span: number): Map<string, Flash> {
  const flashes = new Map<string, Flash>();
  if (span <= 0) return flashes;
  for (const runner of race.runners) {
    const marks = [...runner.splits];
    if (runner.finish !== null) marks.push([race.distance, runner.finish]);
    let latest: Flash | null = null;
    for (const [distance, at] of marks) {
      const age = t - at;
      if (age >= 0 && age < span && (!latest || at > latest.at)) latest = { distance, at, f: age / span };
    }
    if (latest) flashes.set(runner.id, latest);
  }
  return flashes;
}

/** The CSS a flashing row or mark is drawn with: the runner's colour, and how strong the flash
 * still is. */
export function flashStyle(color: string, flash: Flash | undefined): CSSProperties | undefined {
  if (!flash) return undefined;
  return { "--c": color, "--flash": (1 - flash.f).toFixed(3) } as CSSProperties;
}

export interface StretchTimes {
  times: Map<string, number | null>;
  fastest: number | null;
}

/** Everyone's time over a stretch of the race, and the fastest of them. */
export function stretchTimes(race: RaceOnTrack, stretch: Stretch | null): StretchTimes | null {
  if (!stretch) return null;
  // To the thousandth: differences of printed times carry floating-point noise.
  const rounded = (value: number | null) => (value === null ? null : Math.round(value * 1000) / 1000);
  const times = new Map(race.runners.map((r) => [r.id, rounded(stretchTime(r, stretch, race.distance))]));
  const known = [...times.values()].filter((v): v is number => v !== null);
  return { times, fastest: known.length ? Math.min(...known) : null };
}

/** A runner's time over the stretch being pointed at, the fastest in bold. */
export function StretchValue({ runner, times }: { runner: Runner; times: StretchTimes }) {
  const value = times.times.get(runner.id);
  if (value === null || value === undefined) return <>–</>;
  return <span className={value === times.fastest ? "best" : ""}>{time(value)}</span>;
}

/** The standings as a list, in the infield or under the track. Pointing at a stretch swaps each
 * value for the runner's time over it, without moving anything. With ``onFollow``, choosing a
 * runner follows them round the track. */
export function Standings({
  rows,
  race,
  stretch,
  highlight,
  onHighlight,
  followed = null,
  onFollow,
  columns = 1,
  flashes,
}: {
  rows: Standing[];
  race: RaceOnTrack;
  stretch: Stretch | null;
  highlight: string | null;
  onHighlight?: (id: string | null) => void;
  /** The runner being followed, if any. */
  followed?: string | null;
  onFollow?: (id: string) => void;
  /** Columns to lay the runners out in, down each in turn. */
  columns?: number;
  /** Runners who have just passed a split, whose rows flash as they do on the track. */
  flashes?: Map<string, Flash>;
}) {
  const times = stretchTimes(race, stretch);
  const list = useRef<HTMLOListElement>(null);
  useSlide(list);
  const grid: CSSProperties | undefined =
    columns > 1
      ? { display: "grid", gridAutoFlow: "column", gridTemplateRows: `repeat(${Math.ceil(rows.length / columns)}, auto)`, columnGap: 24 }
      : undefined;
  return (
    <div className="standings-block">
      <div className="standings-caption">{stretch ? stretch.label : " "}</div>
      <ol ref={list} className="standings" aria-label="Standings" style={grid}>
        {rows.map((row) => {
          const content = (
            <>
              <span className="standings-rank num">{row.rank ?? "–"}</span>
              <span className="standings-swatch" style={{ background: row.runner.color }} />
              <span className="standings-name">
                {row.runner.short}
                {race.lanes &&
                  (row.runner.laneUnknown ? (
                    <span className="standings-lane" title="Lane not published">
                      {" "}?
                    </span>
                  ) : (
                    <span className="standings-lane"> {row.runner.lane}</span>
                  ))}
              </span>
              <span className={`standings-value num${row.modelled ? " modelled" : ""}`}>
                {times ? (
                  <StretchValue runner={row.runner} times={times} />
                ) : (
                  [row.where, row.value, row.behind].filter(Boolean).join(" ")
                )}
              </span>
            </>
          );
          const id = row.runner.id;
          const flash = flashes?.get(id);
          return (
            <li
              key={id}
              data-id={id}
              className={[highlight === id ? "on" : "", followed === id ? "followed" : "", row.runner.ghost ? "ghost" : "", flash ? "flashing" : ""].join(" ").trim()}
              style={flashStyle(row.runner.color, flash)}
              onPointerEnter={() => onHighlight?.(id)}
              onPointerLeave={() => onHighlight?.(null)}
            >
              {onFollow ? (
                <button
                  type="button"
                  className="standings-row"
                  aria-pressed={followed === id}
                  title={followed === id ? "Follow the leaders instead" : `Follow ${row.runner.name}`}
                  onClick={() => onFollow(id)}
                >
                  {content}
                </button>
              ) : (
                <div className="standings-row">{content}</div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** Milliseconds a row takes to slide to its new place. */
const SLIDE = 450;

/** Rows that change places slide there, from wherever they were (part way through a slide
 * already, if the order changed again), rather than jumping (at once for readers who prefer
 * less motion). */
function useSlide(list: RefObject<HTMLOListElement | null>) {
  const last = useRef(new Map<string, { x: number; y: number }>());
  useLayoutEffect(() => {
    const element = list.current;
    if (!element) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const next = new Map<string, { x: number; y: number }>();
    for (const row of Array.from(element.children) as HTMLElement[]) {
      const id = row.dataset.id;
      if (!id) continue;
      const at = { x: row.offsetLeft, y: row.offsetTop };
      next.set(id, at);
      const was = last.current.get(id);
      if (still || !was || (was.x === at.x && was.y === at.y)) continue;
      // Where the row shows now: its old place, moved by any slide still under way.
      const moving = getComputedStyle(row).transform;
      const shift = moving === "none" ? null : new DOMMatrix(moving);
      const [dx, dy] = [was.x - at.x + (shift?.e ?? 0), was.y - at.y + (shift?.f ?? 0)];
      for (const animation of row.getAnimations()) animation.cancel();
      row.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], {
        duration: SLIDE,
        easing: "cubic-bezier(0.2, 0.8, 0.2, 1)",
      });
    }
    last.current = next;
  });
}
