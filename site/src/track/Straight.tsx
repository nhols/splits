// A race on the straight (60 m, 100 m, the sprint hurdles): the lanes side by side, the start on
// the left and the finish on the right, each runner's name at the start of their lane and their
// standing past the finish. On a phone held upright the straight runs down the screen instead,
// the start at the top, with the standings beside it. The straight is to scale along its
// length; the lanes are drawn wider than they are (three or four times), to be read.

import type { CSSProperties, ReactNode } from "react";
import { useHeight, useWidth } from "../components/charts/useWidth";
import { time } from "../data/format";
import { pulseAt, type Motion } from "./geometry";
import { ownSplits, type Checkpoint, type RaceOnTrack, type Stretch } from "./runners";
import { flashStyle, Standings, stretchTimes, StretchValue, type Flash, type Standing } from "./Standings";

/** Metres of track drawn before the start line (the blocks) and after the finish line. */
const BEFORE = 4;
const AFTER = 4;
/** Pixels between the distance labels under the track: on a narrow track, some are left out. */
const LABEL_GAP = 34;

interface Props {
  race: RaceOnTrack;
  motions: Motion[];
  t: number;
  /** The race clock: stopped when the last runner finishes. */
  clock: number;
  standing: Standing[];
  /** Runners who have just passed a split. */
  flashes: Map<string, Flash>;
  stretch: Stretch | null;
  highlight: string | null;
  onHighlight?: (id: string | null) => void;
  onStretch?: (key: string | null) => void;
  compact: boolean;
  label: string;
  /** The controls, after the straight (and before the standings, when they follow it). */
  after: ReactNode;
}

export function Straight({ down, ...props }: Props & { down: boolean }) {
  return down ? <StraightDown {...props} /> : <StraightAcross {...props} />;
}

/** Every lane of the track out to the widest used, empty ones too; without published lanes, one
 * for each runner. */
function lanesOf(race: RaceOnTrack): number[] {
  return Array.from({ length: Math.max(...race.runners.map((r) => r.lane), race.lanes ? 8 : 0) }, (_, i) => i + 1);
}

/** The straight lying down: the start on the left, names and standings either side. */
function StraightAcross({ race, motions, t, clock, standing, flashes, stretch, highlight, onHighlight, onStretch, compact, label, after }: Props) {
  const { distance, runners } = race;
  const [track, trackWidth] = useWidth<HTMLDivElement>(900);
  const length = BEFORE + distance + AFTER;
  const x = (d: number) => `${((d + BEFORE) / length) * 100}%`;
  const across = (from: number, to: number) => `${((to - from) / length) * 100}%`;
  const lanes = lanesOf(race);
  const rows = lanes.length;
  const inLane = new Map(runners.map((runner, i) => [runner.lane, i]));
  const byRunner = new Map(standing.map((s) => [s.runner.id, s]));
  const times = stretchTimes(race, stretch);
  const row = (lane: number): CSSProperties => ({ top: `calc(${lane - 1} * 100% / ${rows})`, height: `calc(100% / ${rows})` });
  const point = (id: string | undefined) => ({
    onPointerEnter: () => id && onHighlight?.(id),
    onPointerLeave: () => onHighlight?.(null),
  });

  return (
    <>
      <div className={`straight${compact ? " compact" : ""}`} style={{ "--rows": rows } as CSSProperties}>
        <div className="straight-head">
          <div className="replay-clock num" aria-hidden="true">
            {time(clock)}
          </div>
          {!compact && <div className="standings-caption">{stretch?.label ?? ""}</div>}
        </div>
        <div className="straight-grid">
          <div ref={track} className="straight-track" role="img" aria-label={`${label}, at ${time(t)} seconds`} onClick={() => onStretch?.(null)}>
            {lanes.map((lane) => {
              const runner = runners[inLane.get(lane) ?? -1];
              const on = runner !== undefined && runner.id === highlight;
              return <div key={lane} className={`straight-lane${on ? " on" : ""}`} style={on ? ({ "--c": runner.color } as CSSProperties) : undefined} />;
            })}
            <div className="straight-marks">
              <span className="straight-mark start" style={{ left: x(0) }} />
              {race.checkpoints.map((cp) => (
                <span key={cp.distance} className="straight-mark" style={{ left: x(cp.distance) }} />
              ))}
              <span className="straight-mark finish" style={{ left: x(distance) }} />
              {race.hurdles.map((h) =>
                lanes.map((lane) => <span key={`${h}/${lane}`} className="straight-hurdle" style={{ left: x(h), ...row(lane) }} />),
              )}
              {runners.flatMap((runner) =>
                ownSplits(race, runner).map((d) => (
                  <span key={`${runner.id}/${d}`} className="straight-own" style={{ left: x(d), ...row(runner.lane) }} />
                )),
              )}
              {stretch && <span className="straight-stretch" style={{ left: x(stretch.from), width: across(stretch.from, stretch.to) }} />}
            </div>
            {runners.map((runner, i) => {
              const pulse = pulseAt(motions[i]!, runner.finish !== null, t);
              if (!pulse) return null;
              const faded = highlight !== null && highlight !== runner.id;
              return (
                <span
                  key={runner.id}
                  className={`straight-pulse${faded ? " faded" : ""}${runner.modelled ? " modelled" : ""}`}
                  style={{ left: x(pulse.from), width: across(pulse.from, pulse.to), opacity: pulse.opacity, "--c": runner.color, ...row(runner.lane) } as CSSProperties}
                />
              );
            })}
            {runners.map((runner) => {
              const flash = flashes.get(runner.id);
              if (!flash) return null;
              const faded = highlight !== null && highlight !== runner.id;
              return (
                <span key={runner.id} className={`straight-flash${faded ? " faded" : ""}`} style={{ left: x(flash.distance), ...row(runner.lane), ...flashStyle(runner.color, flash) }} />
              );
            })}
            {!compact &&
              onStretch &&
              race.stretches.map((s) => (
                <span
                  key={s.key}
                  className="straight-target"
                  style={{ left: x(s.from), width: across(s.from, s.to) }}
                  onPointerEnter={(event) => event.pointerType === "mouse" && onStretch(s.key)}
                  onPointerLeave={(event) => event.pointerType === "mouse" && onStretch(null)}
                  onClick={(event) => {
                    event.stopPropagation();
                    onStretch(s.key);
                  }}
                />
              ))}
          </div>
          {!compact &&
            lanes.map((lane) => {
              const runner = runners[inLane.get(lane) ?? -1];
              const s = runner ? byRunner.get(runner.id) : undefined;
              const on = runner !== undefined && runner.id === highlight ? " on" : "";
              const flash = runner && flashes.get(runner.id);
              const flashing = flash ? " flashing" : "";
              const lit = runner && flashStyle(runner.color, flash);
              // A position shows once the splits give one: before that, it would only be the result.
              const placed = s && (s.finished || s.where !== null);
              return [
                <div key={`n${lane}`} className={`straight-name${on}${flashing}`} style={{ gridRow: lane, ...lit }} {...point(runner?.id)}>
                  {race.lanes && <span className="straight-lane-number num">{lane}</span>}
                  {runner && (
                    <>
                      <span className="standings-swatch" style={{ background: runner.color }} />
                      <span className="straight-runner">{runner.short}</span>
                    </>
                  )}
                </div>,
                <div key={`s${lane}`} className={`straight-standing${on}${s?.finished ? " finished" : ""}${flashing}`} style={{ gridRow: lane, ...lit }} {...point(runner?.id)}>
                  {runner && s && (
                    <>
                      <span className="standings-rank num">{placed ? s.rank ?? "–" : ""}</span>
                      <span className={`straight-value num${s.modelled ? " modelled" : ""}`}>
                        {times ? (
                          <StretchValue runner={runner} times={times} />
                        ) : (
                          <>
                            {s.where && <span className="straight-where">{s.where} </span>}
                            <span className="straight-time">{s.value}</span>
                            {s.behind && <span className="straight-behind"> {s.behind}</span>}
                          </>
                        )}
                      </span>
                    </>
                  )}
                </div>,
              ];
            })}
          {!compact && (
            <div className="straight-scale" style={{ gridRow: rows + 1 }} aria-hidden="true">
              {spaced(race.checkpoints, distance, trackWidth / length).map((cp) => (
                <span key={cp.distance} style={{ left: x(cp.distance) }}>
                  {cp.label}
                </span>
              ))}
              <span className="finish" style={{ left: x(distance) }}>
                {distance}m
              </span>
            </div>
          )}
        </div>
      </div>
      {after}
    </>
  );
}

/** The straight on end, run from the top of the screen to the bottom: lane numbers over the
 * lanes, distances down the left and the standings on the right. */
function StraightDown({ race, motions, t, clock, standing, flashes, stretch, highlight, onHighlight, onStretch, compact, label, after }: Props) {
  const { distance, runners } = race;
  const [track, trackHeight] = useHeight<HTMLDivElement>(480);
  const length = BEFORE + distance + AFTER;
  const y = (d: number) => `${((d + BEFORE) / length) * 100}%`;
  const along = (from: number, to: number) => `${((to - from) / length) * 100}%`;
  const lanes = lanesOf(race);
  const count = lanes.length;
  const inLane = new Map(runners.map((runner, i) => [runner.lane, i]));
  const column = (lane: number): CSSProperties => ({ left: `calc(${lane - 1} * 100% / ${count})`, width: `calc(100% / ${count})` });
  return (
    <>
      <div className={`straight down${compact ? " compact" : ""}`} style={{ "--lanes": count } as CSSProperties}>
        <div className="straight-head">
          <div className="replay-clock num" aria-hidden="true">
            {time(clock)}
          </div>
        </div>
        <div className="straight-down">
          {!compact && (
            <div className="straight-heads" aria-hidden="true">
              {lanes.map((lane) => {
                const runner = runners[inLane.get(lane) ?? -1];
                return (
                  <span key={lane} className={runner && runner.id === highlight ? "on" : ""}>
                    {race.lanes && <span className="straight-lane-number num">{lane}</span>}
                    {runner && <span className="standings-swatch" style={{ background: runner.color }} />}
                  </span>
                );
              })}
            </div>
          )}
          {!compact && (
            <div className="straight-scale" aria-hidden="true">
              {spaced(race.checkpoints, distance, trackHeight / length, 22).map((cp) => (
                <span key={cp.distance} style={{ top: y(cp.distance) }}>
                  {cp.label}
                </span>
              ))}
              <span className="finish" style={{ top: y(distance) }}>
                {distance}m
              </span>
            </div>
          )}
          <div ref={track} className="straight-track" role="img" aria-label={`${label}, at ${time(t)} seconds`} onClick={() => onStretch?.(null)}>
            {lanes.map((lane) => {
              const runner = runners[inLane.get(lane) ?? -1];
              const on = runner !== undefined && runner.id === highlight;
              return <div key={lane} className={`straight-lane${on ? " on" : ""}`} style={on ? ({ "--c": runner.color } as CSSProperties) : undefined} />;
            })}
            <div className="straight-marks">
              <span className="straight-mark start" style={{ top: y(0) }} />
              {race.checkpoints.map((cp) => (
                <span key={cp.distance} className="straight-mark" style={{ top: y(cp.distance) }} />
              ))}
              <span className="straight-mark finish" style={{ top: y(distance) }} />
              {race.hurdles.map((h) =>
                lanes.map((lane) => <span key={`${h}/${lane}`} className="straight-hurdle" style={{ top: y(h), ...column(lane) }} />),
              )}
              {runners.flatMap((runner) =>
                ownSplits(race, runner).map((d) => (
                  <span key={`${runner.id}/${d}`} className="straight-own" style={{ top: y(d), ...column(runner.lane) }} />
                )),
              )}
              {stretch && <span className="straight-stretch" style={{ top: y(stretch.from), height: along(stretch.from, stretch.to) }} />}
            </div>
            {runners.map((runner, i) => {
              const pulse = pulseAt(motions[i]!, runner.finish !== null, t);
              if (!pulse) return null;
              const faded = highlight !== null && highlight !== runner.id;
              return (
                <span
                  key={runner.id}
                  className={`straight-pulse${faded ? " faded" : ""}${runner.modelled ? " modelled" : ""}`}
                  style={{ top: y(pulse.from), height: along(pulse.from, pulse.to), opacity: pulse.opacity, "--c": runner.color, ...column(runner.lane) } as CSSProperties}
                />
              );
            })}
            {runners.map((runner) => {
              const flash = flashes.get(runner.id);
              if (!flash) return null;
              const faded = highlight !== null && highlight !== runner.id;
              return (
                <span key={runner.id} className={`straight-flash${faded ? " faded" : ""}`} style={{ top: y(flash.distance), ...column(runner.lane), ...flashStyle(runner.color, flash) }} />
              );
            })}
            {!compact &&
              onStretch &&
              race.stretches.map((s) => (
                <span
                  key={s.key}
                  className="straight-target"
                  style={{ top: y(s.from), height: along(s.from, s.to) }}
                  onClick={(event) => {
                    event.stopPropagation();
                    onStretch(s.key);
                  }}
                />
              ))}
          </div>
          {!compact && (
            <div className="straight-side standings-stacked">
              <Standings rows={standing} race={race} stretch={stretch} highlight={highlight} onHighlight={onHighlight} flashes={flashes} />
            </div>
          )}
        </div>
      </div>
      {after}
    </>
  );
}

/** The checkpoints to label, at least ``gap`` pixels apart and clear of the finish. */
function spaced(checkpoints: Checkpoint[], distance: number, perMetre: number, gap = LABEL_GAP): Checkpoint[] {
  const shown: Checkpoint[] = [];
  let last = -Infinity;
  for (const checkpoint of checkpoints) {
    const clear = (checkpoint.distance - last) * perMetre >= gap && (distance - checkpoint.distance) * perMetre >= gap;
    if (clear) {
      shown.push(checkpoint);
      last = checkpoint.distance;
    }
  }
  return shown;
}
