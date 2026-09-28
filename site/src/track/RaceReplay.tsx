// The race on the track: every runner a line pulse in their own lane, moving exactly as their
// published splits say, with the clock and the standings in the infield. Between splits the
// motion is interpolated; the splits themselves are exact. Pointing at a stretch of the track
// (or at a split in the table) marks it in every lane and shows everyone's time for it. Sprints
// are drawn on a straight of their own (Straight.tsx), everything else round the oval, which
// can be watched whole or followed: the view closes in on the runners and moves with them.

import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useSize, useWidth } from "../components/charts/useWidth";
import { time } from "../data/format";
import { frameShot, mixRects, shotRect, smoothShot, type Rect, type Shot } from "./camera";
import {
  course,
  indoorTrack,
  laneRadius,
  lapLength,
  startOf,
  lineRadius,
  loopPath,
  motion,
  onStraight,
  outdoorTrack,
  pulseAt,
  radiusAt,
  TAIL,
  type Course,
  type Frame,
  type Motion,
  type Point,
  type Track,
  WATERFALL,
} from "./geometry";
import { packing, type Packing } from "./pack";
import type { RaceOnTrack, Runner, Stretch } from "./runners";
import { Info, ModelExplainer, MotionExplainer } from "../components/Info";
import { FLASH, flashStyle, splitFlashes, Standings, standings, type Flash, type Standing } from "./Standings";
import { Straight } from "./Straight";
import "./track.css";

interface Props {
  race: RaceOnTrack;
  autoplay?: boolean;
  loop?: boolean;
  /** Just the track and the clock (the home page). */
  compact?: boolean;
  highlight?: string | null;
  onHighlight?: (id: string | null) => void;
  /** The stretch of the race to mark on the track (see ``Stretch.key``). */
  stretch?: string | null;
  onStretch?: (key: string | null) => void;
  /** More controls, after the playback ones. */
  controls?: ReactNode;
  /** What the modelled runners' splits rest on, for the explainer. */
  modelNotes?: string[];
  label: string;
}

const RATES = [0.25, 0.5, 1, 2];
/** Seconds a looping replay holds the finish before starting again. */
const HOLD = 2.5;
/** SVG units across the drawing of the oval. */
const WIDTH = 1000;
/** Following the race, runners more than this many metres behind the leader may leave the
 * view (in a race out of lanes; in lanes, the whole field is framed). */
const PACK = 45;
const NO_FLASHES = new Map<string, Flash>();

export function RaceReplay({
  race,
  autoplay = false,
  loop = false,
  compact = false,
  highlight = null,
  onHighlight,
  stretch = null,
  onStretch,
  controls,
  modelNotes = [],
  label,
}: Props) {
  const straight = onStraight(race.distance);
  // Out of lanes (a waterfall start), ``lane`` is a place on the start line, not a lane.
  const maxLane = race.lanes ? Math.max(0, ...race.runners.map((r) => r.lane)) : 0;
  const track = useMemo(
    () => (race.setting === "indoor" ? indoorTrack(Math.max(6, maxLane)) : outdoorTrack(Math.max(8, maxLane))),
    [race.setting, maxLane],
  );
  // On a phone held upright, the oval stands on end to fill the screen, and sprints run down it.
  const phone = useUpright();
  const upright = phone && !straight;
  const frame = useMemo(() => ovalFrame(track, compact, upright), [track, compact, upright]);
  const motions = useMemo(() => race.runners.map((r) => motion(r.knots, r.finish !== null)), [race.runners]);
  const lastFinish = Math.max(1, ...race.runners.map((r) => r.finish ?? r.knots[r.knots.length - 1]?.t ?? 0));
  const end = lastFinish + 1.2;

  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [following, setFollowing] = useFollowing();
  // The runner the view follows, if one was chosen (else it follows the leaders).
  const [chosen, setChosen] = useState<string | null>(null);
  const followed = race.runners.some((r) => r.id === chosen) ? chosen : null;
  const follow = (id: string | null) => {
    setChosen(id);
    if (id !== null) setFollowing(true);
  };
  const animation = useRef<number | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  // Play: advance the clock with the display's frames.
  useEffect(() => {
    if (!playing) return;
    let last: number | null = null;
    const step = (now: number) => {
      const elapsed = last === null ? 0 : (now - last) / 1000;
      last = now;
      setT((current) => {
        const next = current + elapsed * rate;
        if (next < end) return next;
        if (loop) return next < end + HOLD ? next : 0;
        setPlaying(false);
        return end;
      });
      animation.current = requestAnimationFrame(step);
    };
    animation.current = requestAnimationFrame(step);
    return () => {
      if (animation.current !== null) cancelAnimationFrame(animation.current);
    };
  }, [playing, rate, end, loop]);

  // Autoplay once the replay is on screen (unless the reader prefers less motion), and pause it
  // when it scrolls away. A looping replay picks up again whenever it comes back into view.
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        if (entry.isIntersecting && autoplay && !reduced && (loop || !started.current)) {
          started.current = true;
          setPlaying(true);
        }
        if (!entry.isIntersecting) setPlaying(false);
      },
      { threshold: 0.35 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [autoplay, loop]);

  const standing = standings(race, motions, t);
  const athletes = race.runners.filter((r) => !r.ghost);
  const modelled = race.runners.some((r) => r.modelled);
  // Nobody's splits were published: everyone is modelled (or runs at an even pace).
  const unmeasured = athletes.length > 0 && athletes.every((r) => r.modelled || !r.timed);
  const active = race.stretches.find((s) => s.key === stretch) ?? null;
  // Passing a split flashes on the track and in the standings at once (not on the home page,
  // where the splits are not marked).
  const flashes = compact ? NO_FLASHES : splitFlashes(race, t, FLASH * rate);

  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    // Typing a time to race is not a command.
    if (event.target instanceof HTMLInputElement && event.target.type !== "range") return;
    if (event.key === "f" && !straight && !compact) {
      setFollowing(!following);
    } else if (event.key === " ") {
      event.preventDefault();
      if (t >= end) setT(0);
      setPlaying(!playing);
    } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      setPlaying(false);
      setT((current) => Math.min(Math.max(current + (event.key === "ArrowRight" ? 0.1 : -0.1), 0), end));
    }
  };

  const bar = !compact && (
    <>
      <div className="replay-controls">
        <button
          type="button"
          className="replay-play"
          onClick={() => {
            if (t >= end) setT(0);
            setPlaying(!playing);
          }}
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
              <rect x="3" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
              <rect x="9.5" y="2" width="3.5" height="12" rx="1" fill="currentColor" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
              <path d="M4 2.5v11l9.5-5.5z" fill="currentColor" />
            </svg>
          )}
        </button>
        <input
          type="range"
          className="replay-scrub"
          min={0}
          max={end}
          step={0.01}
          value={Math.min(t, end)}
          onChange={(event) => {
            setPlaying(false);
            setT(Number(event.target.value));
          }}
          aria-label="Race time"
        />
        <div className="segmented replay-rates" role="radiogroup" aria-label="Playback speed">
          {RATES.map((value) => (
            <button key={value} type="button" role="radio" aria-checked={rate === value} className={rate === value ? "on" : ""} onClick={() => setRate(value)}>
              {value < 1 ? `${value === 0.25 ? "¼" : "½"}×` : `${value}×`}
            </button>
          ))}
        </div>
        {!straight && (
          <button
            type="button"
            className={`button replay-follow${following ? " on" : ""}`}
            aria-pressed={following}
            onClick={() => setFollowing(!following)}
            title="Follow the runners (F)"
          >
            <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
              <path d="M1.5 5V2.5a1 1 0 0 1 1-1H5M11 1.5h2.5a1 1 0 0 1 1 1V5M14.5 11v2.5a1 1 0 0 1-1 1H11M5 14.5H2.5a1 1 0 0 1-1-1V11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
              <circle cx="8" cy="8" r="2.4" fill="currentColor" />
            </svg>
            Follow
          </button>
        )}
        {controls}
        <Info label="How the replay works">
          <MotionExplainer />
          <ModelExplainer basis={modelNotes.map((note) => <span key={note}>{note}</span>)} />
        </Info>
      </div>
      {(unmeasured || modelled || (!race.lanes && race.distance < WATERFALL)) && (
        <p className="muted replay-note">
          {[
            unmeasured && "No splits were published for this race: the runners follow modelled splits.",
            modelled && !unmeasured && "Dashed runners are modelled, not measured.",
            !race.lanes && race.distance < WATERFALL && "Lanes weren't published, so runners are shown in finishing order.",
          ]
            .filter(Boolean)
            .join(" ")}
        </p>
      )}
    </>
  );

  const stage = { race, motions, t, clock: Math.min(t, lastFinish), standing, flashes, stretch: active, highlight, onHighlight, onStretch, compact, label };
  const camera = { end, following: following && !compact, followed, onFollow: follow };
  // As wide as the page, but never so tall that the controls drop out of the window.
  const fit = upright
    ? `max(260px, calc((100svh - ${compact ? 330 : 200}px) * ${(WIDTH / frame.height).toFixed(3)}))`
    : `max(480px, calc((100vh - ${compact ? 220 : 330}px) * ${(WIDTH / frame.height).toFixed(3)}))`;
  return (
    <div
      ref={root}
      className={`replay${compact ? " compact" : ""}`}
      style={straight ? undefined : { maxWidth: fit }}
      tabIndex={0}
      onKeyDown={onKey}
      aria-label={`${label}. Space plays or pauses; the arrow keys step through the race${straight ? "" : "; F follows the runners"}.`}
    >
      {straight ? (
        <Straight {...stage} down={phone} after={bar} />
      ) : (
        <Oval {...stage} {...camera} track={track} frame={frame} after={bar} />
      )}
    </div>
  );
}

interface OvalFrame {
  /** From track metres to SVG units. */
  toSvg: (p: Point) => Point;
  /** SVG units per metre. */
  scale: number;
  /** SVG units down the drawing. */
  height: number;
  /** The largest rectangle inside the kerb (reaching into the bends), as fractions of the
   * drawing: the room for the clock and the standings. */
  infield: { left: number; top: number; width: number; height: number };
}

/** The drawing of the oval: lying down, the home straight along the bottom and the finish at
 * its right-hand end; or ``upright``, turned a quarter so that the home straight runs up the
 * right-hand side, the finish at its top (runners still go anticlockwise). */
function ovalFrame(track: Track, compact: boolean, upright: boolean): OvalFrame {
  const outer = lineRadius(track, track.lanes);
  const pad = compact ? 3 : 9;
  const along = track.straight / 2 + outer + pad;
  const across = outer + pad;
  const [halfWidth, halfHeight] = upright ? [across, along] : [along, across];
  const unit = WIDTH / (2 * halfWidth);
  const drawn = 2 * halfHeight * unit;
  const toSvg = (p: Point): Point => {
    const q = upright ? { x: p.y, y: -p.x } : p;
    return { x: (q.x + halfWidth) * unit, y: (q.y + halfHeight) * unit };
  };
  // Of the rectangles a metre inside the kerb, the one with the most room: half as long as
  // the straight plus s, where 2s² + (straight / 2)·s = r² (area's derivative at zero).
  const r = track.kerb - 1;
  const half = track.straight / 2;
  const s = (-half + Math.sqrt(half * half + 8 * r * r)) / 4;
  const a = toSvg({ x: -(half + s), y: -Math.sqrt(r * r - s * s) });
  const b = toSvg({ x: half + s, y: Math.sqrt(r * r - s * s) });
  const [left, top] = [Math.min(a.x, b.x), Math.min(a.y, b.y)];
  return {
    scale: unit,
    height: drawn,
    toSvg,
    infield: { left: left / WIDTH, top: top / drawn, width: Math.abs(b.x - a.x) / WIDTH, height: Math.abs(b.y - a.y) / drawn },
  };
}

const UPRIGHT = "(max-width: 600px) and (orientation: portrait)";

/** Whether the screen is a phone held upright. */
function useUpright(): boolean {
  const [upright, setUpright] = useState(() => window.matchMedia(UPRIGHT).matches);
  useEffect(() => {
    const query = window.matchMedia(UPRIGHT);
    const change = () => setUpright(query.matches);
    query.addEventListener("change", change);
    return () => query.removeEventListener("change", change);
  }, []);
  return upright;
}

/** Whether replays follow the runners, remembered in this browser. */
function useFollowing(): [boolean, (on: boolean) => void] {
  const [following, setFollowing] = useState(() => {
    try {
      return localStorage.getItem("replay-view") === "follow";
    } catch {
      return false;
    }
  });
  const set = (on: boolean) => {
    setFollowing(on);
    try {
      localStorage.setItem("replay-view", on ? "follow" : "track");
    } catch {
      // Not remembered: private browsing, or storage blocked.
    }
  };
  return [following, set];
}

/** 1 while ``on``, 0 while not, easing from one to the other over ``ms`` (at once for readers
 * who prefer less motion). */
function useEased(on: boolean, ms = 700): number {
  const [value, setValue] = useState(on ? 1 : 0);
  const current = useRef(value);
  current.current = value;
  useEffect(() => {
    const target = on ? 1 : 0;
    const from = current.current;
    if (from === target) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setValue(target);
      return;
    }
    const started = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const f = Math.min((now - started) / (ms * Math.abs(target - from)), 1);
      setValue(from + (target - from) * f);
      if (f < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [on, ms]);
  return value;
}

const smoothstep = (f: number) => f * f * (3 - 2 * f);

/** How far out from the line its lane is measured along a runner is drawn: the middle of the
 * lane (0.3 m out from the kerb in lane 1, and out of lanes; 0.2 m from the inner line in
 * the others). */
function centreOffset(track: Track, race: RaceOnTrack, runner: Runner): number {
  return track.laneWidth / 2 - (race.lanes && runner.lane !== 1 ? 0.2 : 0.3);
}

/** The race round the oval, the clock and (when they fit) the standings in the infield.
 * Following the runners, the view closes in on them and moves with them, the clock in one
 * corner, the whole track in miniature in another, and the standings below. */
function Oval({
  race,
  track,
  frame,
  motions,
  t,
  end,
  clock,
  standing,
  flashes,
  stretch: active,
  highlight,
  onHighlight,
  onStretch,
  compact,
  label,
  after,
  following,
  followed,
  onFollow,
}: {
  race: RaceOnTrack;
  track: Track;
  frame: OvalFrame;
  motions: Motion[];
  t: number;
  /** When the replay ends. */
  end: number;
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
  /** The controls, between the track and any standings that go below it. */
  after: ReactNode;
  /** Whether the view follows the runners, rather than showing the whole track. */
  following: boolean;
  /** The runner the view follows, if one was chosen; else it follows the leaders. */
  followed: string | null;
  onFollow: (id: string | null) => void;
}) {
  const path = useMemo(() => course(track, race.distance, race.runners.length), [track, race.distance, race.runners.length]);
  // Out of lanes, where everyone is across the track, worked out once for the whole race.
  const packed = useMemo(
    () => (path.breakAt === null ? null : packing(motions, path.breakAt, track.laneWidth, end)),
    [path, motions, track, end],
  );
  // Over more than a lap, stretches overlap on the track: they are shaded, not pointed at, there.
  const lap = lapLength(track, laneRadius(track, 1));
  const laps = race.distance > lap + 1;
  const [stage, stageWidth] = useWidth<HTMLDivElement>(900);
  const { toSvg, scale, height, infield } = frame;
  const zoom = smoothstep(useEased(following));

  // Where runner ``i`` is on the drawing at time ``at`` and which way they are running, while
  // they are on the track.
  const place = (i: number, at: number) => {
    const runner = race.runners[i]!;
    const pulse = pulseAt(motions[i]!, runner.finish !== null, at);
    if (!pulse || pulse.opacity < 1) return null;
    const free = packed?.at(i, pulse.at) ?? 0;
    const offset = centreOffset(track, race, runner);
    const on = (d: number) => {
      const f = path.frame(runner.lane, d, free);
      return toSvg({ x: f.p.x + f.n.x * offset, y: f.p.y + f.n.y * offset });
    };
    const [head, next] = [on(pulse.to), on(pulse.to + 1)];
    const length = Math.hypot(next.x - head.x, next.y - head.y) || 1;
    return { i, d: pulse.to, head, heading: { x: (next.x - head.x) / length, y: (next.y - head.y) / length } };
  };
  const whole: Rect = { x: 0, y: 0, w: WIDTH, h: height };
  // The shot at a moment: the runner followed, or the leaders and everyone close behind them.
  const shot = (at: number): Shot | null => {
    const placed = race.runners.map((_, i) => place(i, at)).filter((p) => p !== null);
    if (!placed.length) return null;
    const one = placed.filter((p) => race.runners[p.i]!.id === followed);
    const lead = Math.max(...placed.map((p) => p.d));
    const framed = one.length ? one : race.lanes ? placed : placed.filter((p) => p.d >= lead - PACK);
    // Room ahead along the way the runners framed are heading on average: not the leader's way,
    // which on a bend in lanes swings with every change of leader and shakes the view.
    const sum = framed.reduce((a, p) => ({ x: a.x + p.heading.x, y: a.y + p.heading.y }), { x: 0, y: 0 });
    const length = Math.hypot(sum.x, sum.y) || 1;
    return frameShot(
      framed.map((p) => p.head),
      { x: sum.x / length, y: sum.y / length },
      scale,
      WIDTH / height,
    );
  };
  const target = zoom > 0 ? smoothShot(shot, t, end) : null;
  const view = target ? mixRects(whole, shotRect(target, WIDTH, height), zoom) : whole;
  // SVG units per screen pixel: labels and pulses keep their size on screen at any zoom. The
  // track itself is redrawn only when the zoom has changed by a few per cent.
  const px = view.w / Math.max(stageWidth, 1);
  const pxTrack = 1.04 ** Math.round(Math.log(px) / Math.log(1.04));

  const lanes = useMemo(() => [...new Set(race.runners.map((r) => r.lane))].sort((a, b) => a - b), [race.runners]);
  const along = useMemo(() => alongLane(track, path, toSvg), [track, path, toSvg]);
  const highlighted = race.runners.find((r) => r.id === highlight);
  // The standings go in the infield (under the controls while the view follows the runners
  // and the infield is out of sight): in as many columns as fit, scrolling only when even those
  // are too few. Where the infield is narrow, each runner's time goes under their name.
  const inside = !compact && !following;
  const narrow = infield.width * stageWidth < 320;
  const [room, roomSize] = useSize<HTMLDivElement>();
  const [head, headSize] = useSize<HTMLDivElement>();
  const [rowHeight, columnWidth] = narrow ? [44, 180] : [25, 300];
  // Below the clock: the rows a column holds (under the caption), and the columns that fit.
  const perColumn = Math.max(1, Math.floor((roomSize.height - headSize.height - 24) / rowHeight));
  const fit = Math.max(1, Math.floor((roomSize.width + 24) / (columnWidth + 24)));
  const columns = Math.min(fit, Math.ceil(race.runners.length / perColumn));
  // Draw the runner being pointed at last, over the others.
  const order = race.runners.map((_, i) => i).sort((a, b) => Number(race.runners[a]!.id === highlight) - Number(race.runners[b]!.id === highlight));
  const followedRunner = race.runners.find((r) => r.id === followed);

  const table = (
    <Standings
      rows={standing}
      race={race}
      stretch={active}
      highlight={highlight}
      onHighlight={onHighlight}
      followed={following ? followed : null}
      onFollow={compact ? undefined : (id) => onFollow(id === followed && following ? null : id)}
      columns={inside ? columns : 1}
      flashes={flashes}
    />
  );
  return (
    <>
      <div className={`replay-stage${zoom > 0 ? " following" : ""}${height > WIDTH ? " upright" : ""}`} ref={stage}>
        <svg
          viewBox={`${view.x.toFixed(2)} ${view.y.toFixed(2)} ${view.w.toFixed(2)} ${view.h.toFixed(2)}`}
          className="replay-track"
          role="img"
          aria-label={`${label}, at ${time(t)} seconds`}
          onClick={() => onStretch?.(null)}
        >
          <StaticTrack track={track} path={path} lanes={lanes} race={race} toSvg={toSvg} scale={scale} px={pxTrack} compact={compact} />
          {highlighted && (
            <polyline
              points={along(highlighted.lane, 0, race.distance)}
              className="track-lane-tint"
              stroke={highlighted.color}
              strokeWidth={scale * track.laneWidth * 0.9}
            />
          )}
          {active &&
            (race.lanes ? (
              lanes.map((lane) => (
                <polyline key={lane} points={along(lane, active.from, active.to)} className="track-stretch" strokeWidth={scale * track.laneWidth} />
              ))
            ) : (
              <polyline points={acrossBand(track, path, toSvg, active.from, active.to)} className="track-stretch" strokeWidth={scale * track.laneWidth * track.lanes} />
            ))}
          {order.map((i) => (
            <RunnerPulse
              key={race.runners[i]!.id}
              runner={race.runners[i]!}
              index={i}
              motion={motions[i]!}
              packed={packed}
              t={t}
              path={path}
              toSvg={toSvg}
              offset={centreOffset(track, race, race.runners[i]!)}
              width={Math.max(scale * track.laneWidth * 0.86, 2.4 * px)}
              px={px}
              faded={highlight !== null && highlight !== race.runners[i]!.id}
            />
          ))}
          {/* Over the trails, which have just crossed the mark. */}
          {race.runners.map((runner, i) => {
            const flash = flashes.get(runner.id);
            if (!flash) return null;
            const f = path.frame(runner.lane, flash.distance, packed?.at(i, flash.at) ?? 0);
            return (
              <SplitMark
                key={runner.id}
                color={runner.color}
                flash={flash}
                across={laneSegment(track, f, runner.lane, toSvg)}
                px={px}
                faded={highlight !== null && highlight !== runner.id}
              />
            );
          })}
          {!compact && onStretch && !laps && (
            <StretchTargets stretches={race.stretches} lanes={lanes} along={along} width={scale * track.laneWidth} onStretch={onStretch} />
          )}
        </svg>
        {zoom < 1 && (
          <div
            ref={room}
            className="replay-infield"
            style={{
              left: `${infield.left * 100}%`,
              top: `${infield.top * 100}%`,
              width: `${infield.width * 100}%`,
              height: `${infield.height * 100}%`,
              opacity: 1 - zoom,
            }}
          >
            <div ref={head} className="replay-infield-head">
              <div className="replay-clock num" aria-hidden="true">
                {time(clock)}
              </div>
              {laps && <LapsToGo motions={motions} t={t} distance={race.distance} lap={lap} />}
            </div>
            {inside && (
              <div className={`replay-standings${narrow ? " standings-stacked" : ""}`} style={{ "--columns": columns } as React.CSSProperties}>
                {table}
              </div>
            )}
          </div>
        )}
        {zoom > 0 && (
          <>
            <div className="replay-hud" style={{ opacity: zoom }}>
              <div className="replay-hud-clock" aria-hidden="true">
                <span className="num">{time(clock)}</span>
                {laps && <LapsToGo motions={motions} t={t} distance={race.distance} lap={lap} />}
              </div>
              {followedRunner && (
                <button type="button" className="replay-hud-chip" onClick={() => onFollow(null)} title="Follow the leaders instead">
                  <span className="standings-swatch" style={{ background: followedRunner.color }} />
                  {followedRunner.short}
                  <span aria-hidden="true">×</span>
                  <span className="visually-hidden">: stop following</span>
                </button>
              )}
            </div>
            <Minimap
              track={track}
              frame={frame}
              view={view}
              dots={race.runners.flatMap((runner, i) => {
                const p = place(i, t);
                return p ? [{ id: runner.id, color: runner.color, at: p.head, ghost: Boolean(runner.ghost) }] : [];
              })}
              opacity={zoom}
            />
          </>
        )}
      </div>
      {after}
      {!compact && !inside && <div className="replay-below">{table}</div>}
    </>
  );
}

/** The whole track in miniature, with every runner as a dot and the part in view outlined. */
function Minimap({
  track,
  frame,
  view,
  dots,
  opacity,
}: {
  track: Track;
  frame: OvalFrame;
  view: Rect;
  dots: { id: string; color: string; at: Point; ghost: boolean }[];
  opacity: number;
}) {
  const outline = useMemo(
    () => ({ outer: loopPath(track, lineRadius(track, track.lanes), frame.toSvg), inner: loopPath(track, track.kerb, frame.toSvg) }),
    [track, frame],
  );
  return (
    <svg className="replay-minimap" viewBox={`0 0 ${WIDTH} ${frame.height}`} style={{ opacity }} aria-hidden="true">
      <path d={outline.outer} className="minimap-track" />
      <path d={outline.inner} className="minimap-infield" />
      {dots.map((dot) => (
        <circle key={dot.id} cx={dot.at.x} cy={dot.at.y} r={16} fill={dot.ghost ? "var(--ink)" : dot.color} />
      ))}
      <rect x={view.x} y={view.y} width={view.w} height={view.h} rx={10} className="minimap-view" />
    </svg>
  );
}

function StaticTrack({
  track,
  path,
  lanes,
  race,
  toSvg,
  scale,
  px,
  compact,
}: {
  track: Track;
  path: Course;
  lanes: number[];
  race: RaceOnTrack;
  toSvg: (p: Point) => Point;
  scale: number;
  px: number;
  compact: boolean;
}) {
  return useMemo(() => {
    const across = (lane: number, d: number) => laneSegment(track, path.frame(lane, d), lane, toSvg);
    const outer = lineRadius(track, track.lanes);
    // Across the whole track, kerb to outside line, where runners are free of their lanes.
    const acrossTrack = ({ p, n }: Frame) => {
      const r = radiusAt(track, p);
      const a = toSvg({ x: p.x - n.x * (r - track.kerb), y: p.y - n.y * (r - track.kerb) });
      const b = toSvg({ x: p.x + n.x * (outer - r), y: p.y + n.y * (outer - r) });
      return { x1: a.x, y1: a.y, x2: b.x, y2: b.y };
    };
    const outermost = Math.max(...lanes, 1);
    const font = 11 * px;
    const lap = lapLength(track, laneRadius(track, 1));
    const laps = race.distance > lap + 1;
    // Labels sit a few pixels outside the track, level with their mark.
    const labelAt = ({ p, n }: Frame) => {
      const beyond = outer - radiusAt(track, p) + (5 * px + font / 2) / scale;
      return toSvg({ x: p.x + n.x * beyond, y: p.y + n.y * beyond });
    };
    const laneOnScreen = (track.laneWidth * scale) / px;
    const finish = [toSvg({ x: track.straight / 2, y: track.kerb }), toSvg({ x: track.straight / 2, y: lineRadius(track, track.lanes) })];
    return (
      <g>
        <path d={loopPath(track, lineRadius(track, track.lanes), toSvg)} className="track-surface" />
        <path d={loopPath(track, track.kerb, toSvg)} className="track-infield" />
        {Array.from({ length: track.lanes }, (_, k) => (
          <path key={k} d={loopPath(track, lineRadius(track, k + 1), toSvg)} className="track-line" />
        ))}
        <path d={loopPath(track, track.kerb, toSvg)} className="track-kerb" />
        <line x1={finish[0]!.x} y1={finish[0]!.y} x2={finish[1]!.x} y2={finish[1]!.y} className="track-finish" />
        {race.lanes ? (
          lanes.map((lane) => <line key={`s${lane}`} {...across(lane, 0)} className="track-start" />)
        ) : (
          <line {...acrossTrack(path.frame(1, 0))} className="track-start" />
        )}
        {race.hurdles.map((h) => lanes.map((lane) => <line key={`h${h}-${lane}`} {...across(lane, h)} className="track-hurdle" />))}
        {!compact &&
          laps &&
          // Over several laps, checkpoints fall on the same few places: marked once, unlabelled.
          [...new Map(race.checkpoints.map((cp) => [Math.round((startOf(track, race.distance) + cp.distance) % lap), cp])).values()].map(
            (cp) => <line key={`c${cp.distance}`} {...acrossTrack(path.frame(1, cp.distance))} className="track-checkpoint" />,
          )}
        {!compact &&
          !laps &&
          race.checkpoints.map((cp) => {
            // Past the break line there are no lanes: one mark across the track.
            const free = path.breakAt !== null && cp.distance > path.breakAt;
            const mark = path.frame(free ? 1 : outermost, cp.distance);
            const label = labelAt(mark);
            return (
              <g key={`c${cp.distance}`}>
                {free ? (
                  <line {...acrossTrack(mark)} className="track-checkpoint" />
                ) : (
                  lanes.map((lane) => <line key={lane} {...across(lane, cp.distance)} className="track-checkpoint" />)
                )}
                <text x={label.x} y={label.y} className="track-label" textAnchor="middle" dy="0.35em" fontSize={font}>
                  {cp.label}
                </text>
              </g>
            );
          })}
        {race.lanes &&
          path.breakAt !== null &&
          lanes.map((lane) => <line key={`b${lane}`} {...across(lane, path.breakAt!)} className="track-break" />)}
        {!compact &&
          race.lanes &&
          laneOnScreen >= 8 &&
          lanes.map((lane) => {
            const start = path.frame(lane, 0);
            // Just behind the start line, where a runner sets up.
            const behind = path.frame(lane, -2.2);
            const at = toSvg({
              x: behind.p.x + start.n.x * (track.laneWidth / 2 - 0.25),
              y: behind.p.y + start.n.y * (track.laneWidth / 2 - 0.25),
            });
            return (
              <text
                key={`n${lane}`}
                x={at.x}
                y={at.y}
                className="track-lane-number"
                textAnchor="middle"
                dy="0.35em"
                fontSize={Math.min(scale * track.laneWidth * 0.72, 11 * px)}
              >
                {lane}
              </text>
            );
          })}
      </g>
    );
  }, [track, path, lanes, race, toSvg, scale, px, compact]);
}

/** The lap board: laps left for the leader, until they are on the last one. */
function LapsToGo({ motions, t, distance, lap }: { motions: Motion[]; t: number; distance: number; lap: number }) {
  const leader = Math.max(0, ...motions.map((m) => m.at(t) ?? 0));
  if (leader >= distance) return null;
  // A start just short of the line (the mile's 9.34 m) is not a lap of its own.
  const whole = distance % lap < lap / 10 ? Math.floor(distance / lap) : Infinity;
  const left = Math.min(Math.ceil((distance - leader) / lap - 1e-9), whole);
  return <div className="replay-laps num">{left <= 1 ? "Last lap" : `${left} laps to go`}</div>;
}

/** A band across the whole track between two distances of a race run out of lanes. */
function acrossBand(track: Track, path: Course, toSvg: (p: Point) => Point, from: number, to: number, step = 3): string {
  const steps = Math.max(2, Math.ceil((to - from) / step));
  const middle = (track.laneWidth * track.lanes) / 2 - 0.3;
  return Array.from({ length: steps + 1 }, (_, k) => {
    const { p, n } = path.frame(1, from + ((to - from) * k) / steps);
    const at = toSvg({ x: p.x + n.x * middle, y: p.y + n.y * middle });
    return `${at.x.toFixed(1)},${at.y.toFixed(1)}`;
  }).join(" ");
}

/** A line across a lane at a runner's frame, from the lane's inner line to its outer one. */
function laneSegment(track: Track, frame: Frame, lane: number, toSvg: (p: Point) => Point) {
  const inside = lane === 1 ? 0.3 : 0.2;
  const a = toSvg({ x: frame.p.x - frame.n.x * inside, y: frame.p.y - frame.n.y * inside });
  const b = toSvg({
    x: frame.p.x + frame.n.x * (track.laneWidth - inside),
    y: frame.p.y + frame.n.y * (track.laneWidth - inside),
  });
  return { x1: a.x, y1: a.y, x2: b.x, y2: b.y };
}

/** Points along the middle of a lane between two distances of the race, as an SVG polyline. */
function alongLane(track: Track, path: Course, toSvg: (p: Point) => Point) {
  return (lane: number, from: number, to: number, step = 1.5): string => {
    const steps = Math.max(2, Math.ceil((to - from) / step));
    const offset = track.laneWidth / 2 - 0.25;
    return Array.from({ length: steps + 1 }, (_, k) => {
      const f = path.frame(lane, from + ((to - from) * k) / steps);
      const p = toSvg({ x: f.p.x + f.n.x * offset, y: f.p.y + f.n.y * offset });
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    }).join(" ");
  };
}

/** Invisible targets over every stretch of every lane, for pointing at a part of the race. */
function StretchTargets({
  stretches,
  lanes,
  along,
  width,
  onStretch,
}: {
  stretches: Stretch[];
  lanes: number[];
  along: (lane: number, from: number, to: number) => string;
  width: number;
  onStretch: (key: string | null) => void;
}) {
  return useMemo(
    () => (
      <g className="track-targets">
        {stretches.map((s) =>
          lanes.map((lane) => (
            <polyline
              key={`${s.key}/${lane}`}
              points={along(lane, s.from, s.to)}
              strokeWidth={width}
              onPointerEnter={(event) => event.pointerType === "mouse" && onStretch(s.key)}
              onPointerLeave={(event) => event.pointerType === "mouse" && onStretch(null)}
              onClick={(event) => {
                event.stopPropagation();
                onStretch(s.key);
              }}
            />
          )),
        )}
      </g>
    ),
    [stretches, lanes, along, width, onStretch],
  );
}

/** Passing a split: the mark across the runner's lane (and only their lane) lights up in their
 * colour, with a soft glow along the lane either side, and fades as their row in the standings
 * does. */
function SplitMark({
  color,
  flash,
  across,
  px,
  faded,
}: {
  color: string;
  flash: Flash;
  /** The mark across the lane at the split. */
  across: { x1: number; y1: number; x2: number; y2: number };
  px: number;
  faded: boolean;
}) {
  return (
    <g className={`split-flash${faded ? " faded" : ""}`} style={flashStyle(color, flash)}>
      <line {...across} className="split-glow" strokeWidth={(4 + 10 * (1 - flash.f)) * px} />
      <line {...across} className="split-mark" strokeWidth={3 * px} />
    </g>
  );
}

/** A runner as a pulse of light along their lane: solid at the front, where they are now, and
 * fading back over the ground they covered in the last moment, so faster runners draw longer
 * trails. A runner standing still (in the blocks, or past the line) is a short solid bar. */
function RunnerPulse({
  runner,
  index,
  motion: moving,
  packed,
  t,
  path,
  toSvg,
  offset,
  width,
  px,
  faded,
}: {
  runner: Runner;
  /** The runner's place in the race's list of runners, for their place across the track. */
  index: number;
  motion: Motion;
  packed: Packing | null;
  t: number;
  path: Course;
  toSvg: (p: Point) => Point;
  /** How far out from the line their lane is measured along the runner is drawn. */
  offset: number;
  width: number;
  px: number;
  faded: boolean;
}) {
  const gradient = `pulse-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const pulse = pulseAt(moving, runner.finish !== null, t);
  if (!pulse) return null;
  const { from, to: d, at, opacity: fade } = pulse;
  // Out of lanes, the runner's place across the track, from a moment ago (at the tail) to now.
  const [was, is] = packed ? [packed.at(index, Math.max(at - TAIL, 0)), packed.at(index, at)] : [0, 0];
  const centre = (k: number) => {
    const f = path.frame(runner.lane, from + ((d - from) * k) / 10, was + ((is - was) * k) / 10);
    return toSvg({ x: f.p.x + f.n.x * offset, y: f.p.y + f.n.y * offset });
  };
  const points = Array.from({ length: 11 }, (_, k) => centre(k));
  const [tail, head] = [points[0]!, points[points.length - 1]!];
  return (
    <g className={`runner${faded ? " faded" : ""}${runner.ghost ? " ghost" : ""}`} opacity={fade}>
      <defs>
        {/* Along the chord from tail to head: on a trail this short, as good as along the arc. */}
        <linearGradient id={gradient} gradientUnits="userSpaceOnUse" x1={tail.x} y1={tail.y} x2={head.x} y2={head.y}>
          <stop offset="0" style={{ stopColor: runner.color, stopOpacity: 0 }} />
          <stop offset="0.6" style={{ stopColor: runner.color, stopOpacity: 0.4 }} />
          <stop offset="1" style={{ stopColor: runner.color, stopOpacity: 1 }} />
        </linearGradient>
      </defs>
      <polyline
        points={points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
        stroke={`url(#${gradient})`}
        strokeWidth={width}
        strokeDasharray={runner.modelled ? `${4 * px} ${2.5 * px}` : undefined}
        className="runner-pulse"
      />
      {runner.ghost && (
        <text x={head.x} y={head.y - 9 * px} className="runner-tag" textAnchor="middle" fontSize={11 * px}>
          You
        </text>
      )}
    </g>
  );
}
