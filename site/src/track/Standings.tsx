// Who is where during a replay, by the published times: the standings beside the track.

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
 * positions between them), then those out of the race (a pacemaker who has stepped off). */
export function standings(race: RaceOnTrack, motions: Motion[], t: number): Standing[] {
  const runners = race.runners;
  const labels = new Map(race.checkpoints.map((c) => [c.distance, c.label]));
  const passed = (runner: Runner) =>
    [...runner.splits].filter(([, when]) => when <= t).sort((a, b) => b[0] - a[0])[0] ?? null;
  const rows = runners.map((runner, i) => ({
    runner,
    finished: runner.finish !== null && t >= runner.finish,
    // Stopped short of the finish, and past the last point they were timed at.
    out: runner.finish === null && runner.knots.length > 0 && t > runner.knots[runner.knots.length - 1]!.t,
    split: passed(runner),
    d: motions[i]!.at(t) ?? -1,
  }));
  rows.sort((a, b) => {
    if (a.finished || b.finished) {
      return a.finished && b.finished ? a.runner.finish! - b.runner.finish! : Number(b.finished) - Number(a.finished);
    }
    if (a.out !== b.out) return Number(a.out) - Number(b.out);
    const [da, db] = [a.split?.[0] ?? -1, b.split?.[0] ?? -1];
    if (da !== db) return db - da;
    if (a.split && b.split && a.split[1] !== b.split[1]) return a.split[1] - b.split[1];
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
}: {
  rows: Standing[];
  race: RaceOnTrack;
  stretch: Stretch | null;
  highlight: string | null;
  onHighlight?: (id: string | null) => void;
  /** The runner being followed, if any. */
  followed?: string | null;
  onFollow?: (id: string) => void;
}) {
  const times = stretchTimes(race, stretch);
  return (
    <div className="standings-block">
      <div className="standings-caption">{stretch ? stretch.label : " "}</div>
      <ol className="standings" aria-label="Standings">
        {rows.map((row) => {
          const content = (
            <>
              <span className="standings-rank num">{row.rank ?? "–"}</span>
              <span className="standings-swatch" style={{ background: row.runner.color }} />
              <span className="standings-name">
                {row.runner.short}
                {race.lanes && <span className="standings-lane"> {row.runner.lane}</span>}
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
          return (
            <li
              key={id}
              className={[highlight === id ? "on" : "", followed === id ? "followed" : "", row.runner.ghost ? "ghost" : ""].join(" ").trim()}
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
