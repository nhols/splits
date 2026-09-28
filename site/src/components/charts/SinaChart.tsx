// The spread of every run's time over each segment of a race: a violin per segment, its width
// the density of times, with every run a dot inside it (spread sideways by that density), a
// line over the middle half and a dot at the median. Pointing at a dot follows that run through every segment.
// Runs in two groups (men and women) share each violin: one half each, in the group's colour.
// Values that grow along the race can give each column a scale of its own.

import { useEffect, useMemo, useRef, useState } from "react";
import { useWidth } from "./useWidth";
import "./charts.css";

export interface SinaRun {
  id: string;
  /** The run's value in each column (null where not known). */
  values: (number | null)[];
  title: string;
  detail: string;
  /** The group the run belongs to, if the chart has groups. */
  group?: string;
}

export interface SinaGroup {
  id: string;
  label: string;
  color: string;
}

interface Props {
  columns: string[];
  /** Shorter labels for when the columns are too narrow for theirs (e.g. just "120m"). */
  shortColumns?: string[];
  runs: SinaRun[];
  /** The groups to draw, each in its colour; two share each violin, a half each. */
  groups?: SinaGroup[];
  format: (value: number) => string;
  yLabel: string;
  height?: number;
  /** Give every column a scale of its own, each fitted to its runs and the same height: for
   * values that grow along the race (times from the gun), which one scale would squash. */
  independent?: boolean;
}

const MARGIN = { top: 14, right: 12, bottom: 34, left: 48 };
/** With a scale per column, the room each column keeps at its left for its tick labels. */
const GUTTER = 40;

function quantile(sorted: number[], q: number): number {
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  return sorted[lower]! + (sorted[upper]! - sorted[lower]!) * (position - lower);
}

/** A number in [-1, 1) from a run and column, stable between renders. */
function jitter(id: string, column: number): number {
  let hash = 2166136261 ^ column;
  for (let i = 0; i < id.length; i++) hash = Math.imul(hash ^ id.charCodeAt(i), 16777619);
  return ((hash >>> 0) / 2 ** 32) * 2 - 1;
}

interface Column {
  label: string;
  n: number;
  q1: number;
  median: number;
  q3: number;
  /** Each run's sideways offset, as a fraction of the column's half-width. */
  offsets: Map<string, number>;
  /** The violin's outline: density (scaled so the densest point is 1) along the values. */
  shape: { value: number; width: number }[];
}

function summarise(label: string, index: number, runs: SinaRun[]): Column | null {
  const values = runs.map((run) => [run.id, run.values[index]] as const).filter((v): v is readonly [string, number] => v[1] != null);
  if (values.length === 0) return null;
  const sorted = values.map(([, v]) => v).sort((a, b) => a - b);
  const q1 = quantile(sorted, 0.25);
  const q3 = quantile(sorted, 0.75);
  // Density by a Gaussian kernel (Silverman's bandwidth), scaled so the densest point is 1.
  const sd = Math.sqrt(sorted.reduce((sum, v) => sum + (v - sorted[sorted.length >> 1]!) ** 2, 0) / sorted.length);
  const bandwidth = Math.max(0.9 * Math.min(sd, (q3 - q1) / 1.34 || sd) * sorted.length ** -0.2, 1e-3);
  const density = (x: number) => sorted.reduce((sum, v) => sum + Math.exp(-0.5 * ((x - v) / bandwidth) ** 2), 0);
  const densities = new Map(values.map(([id, v]) => [id, density(v)]));
  const peak = Math.max(...densities.values());
  const offsets = new Map(values.map(([id]) => [id, jitter(id, index) * (densities.get(id)! / peak)]));
  // The outline runs a little past the extreme runs, where the density tails off.
  const [from, to] = [sorted[0]! - bandwidth, sorted[sorted.length - 1]! + bandwidth];
  const shape = Array.from({ length: 48 }, (_, k) => {
    const value = from + ((to - from) * k) / 47;
    return { value, width: density(value) / peak };
  });
  return {
    label,
    n: sorted.length,
    q1,
    median: quantile(sorted, 0.5),
    q3,
    offsets,
    shape,
  };
}

function niceTicks(lo: number, hi: number, count = 5): number[] {
  const raw = (hi - lo) / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? raw;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) ticks.push(Number(v.toFixed(10)));
  return ticks;
}

const ONE: SinaGroup[] = [{ id: "", label: "", color: "var(--series-1)" }];

export function SinaChart({ columns, shortColumns, runs, groups: given, format, yLabel, height = 360, independent = false }: Props) {
  const [root, width] = useWidth<HTMLDivElement>(800);
  const [hover, setHover] = useState<{ run: SinaRun; column: number } | null>(null);
  const [boxHover, setBoxHover] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const picked = hover !== null || boxHover !== null;

  // What a tap picked stays picked until a tap elsewhere on the page lets it go.
  useEffect(() => {
    if (!picked) return;
    const onDown = (event: PointerEvent) => {
      if (svg.current?.contains(event.target as Node)) return;
      cancelAnimationFrame(frame.current);
      setHover(null);
      setBoxHover(null);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [picked]);

  const groups = given?.length ? given : ONE;
  const groupOf = (run: SinaRun) => Math.max(0, groups.findIndex((g) => g.id === (run.group ?? "")));
  // Each column's summary for each group.
  const stats = useMemo(
    () => columns.map((label, i) => groups.map((_, g) => summarise(label, i, runs.filter((run) => groupOf(run) === g)))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [columns, runs, groups],
  );
  // With two groups the first takes the left half of each violin, the second the right.
  const halves = groups.length === 2;
  const sideOf = (g: number) => (halves ? (g === 0 ? -1 : 1) : 0);
  // The first segment (the start, with the reaction and the acceleration, or the run to the
  // first hurdle) is often far slower than the rest: then it gets a scale of its own, set
  // apart, so it doesn't squash the others.
  // A scale covering the violins, whose outlines run a little past the extreme runs.
  const range = (from: number, to: number): [number, number] => {
    const values = stats
      .slice(from, to)
      .flat()
      .flatMap((column) => (column ? [column.shape[0]!.value, column.shape[column.shape.length - 1]!.value] : []));
    const [lo, hi] = [Math.min(...values), Math.max(...values)];
    const pad = (hi - lo) * 0.02 || 0.5;
    return [lo - pad, hi + pad];
  };
  const first = columns.length > 2 && !independent ? range(0, 1) : null;
  const rest = columns.length > 2 && !independent ? range(1, columns.length) : null;
  const split = first !== null && rest !== null && (first[0] > rest[1] || first[1] < rest[0]);
  const whole = range(0, columns.length);
  const own = independent ? columns.map((_, i) => range(i, i + 1)) : [];
  const domainOf = (column: number): [number, number] =>
    independent ? own[column]! : split ? (column === 0 ? first! : rest!) : whole;

  // Each column's own tick labels sit in a gutter at its left, inside its band; on a phone the
  // columns are too narrow for them, and a tap reads the values instead.
  const left = independent ? 8 : MARGIN.left;
  const GAP = split ? 56 : 0;
  const plotWidth = Math.max(width - left - MARGIN.right - GAP, 100);
  const plotHeight = height - MARGIN.top - MARGIN.bottom;
  const band = plotWidth / columns.length;
  const gutter = independent && band >= 2.5 * GUTTER ? GUTTER : 0;
  const half = Math.min((band - gutter) * 0.4, 80);
  const cx = (column: number) => left + band * column + gutter + (band - gutter) / 2 + (split && column > 0 ? GAP : 0);
  const y = (v: number, column: number) => {
    const domain = domainOf(column);
    const f = (v - domain[0]) / (domain[1] - domain[0]);
    return MARGIN.top + (1 - f) * plotHeight;
  };
  // Labels under the columns: in full if they fit, else short, and only every so many when
  // even those would touch (always the last).
  const textWidth = (labels: string[]) => Math.max(...labels.map((label) => label.length * 6.6)) + 12;
  const fits = textWidth(columns) <= band;
  const shown = fits || !shortColumns ? columns : shortColumns;
  const every = fits ? 1 : Math.ceil(textWidth(shown) / band);
  const axisLabels = shown
    .map((label, column) => ({ label, column }))
    .filter(({ column }) => (columns.length - 1 - column) % every === 0);

  const dotX = (run: SinaRun, column: number) => {
    const g = groupOf(run);
    const offset = stats[column]?.[g]?.offsets.get(run.id) ?? 0;
    return cx(column) + (halves ? sideOf(g) * Math.abs(offset) : offset) * half;
  };
  const radius = runs.length > 150 ? 2.2 : 3;

  // Every dot's place, by column, worked out once per layout rather than on every move.
  const placed = useMemo(
    () =>
      columns.map((_, i) =>
        runs.flatMap((run) => {
          const v = run.values[i];
          return v == null ? [] : [{ run, x: dotX(run, i), y: y(v, i), color: groups[groupOf(run)]!.color }];
        }),
      ),
    // Everything else the positions depend on follows from these.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stats, runs, width, height],
  );
  // The dots don't change as the pointer moves, so they are drawn once, not on every move.
  const dots = useMemo(
    () =>
      placed.map((column, i) =>
        column.map(({ run, x, y, color }) => <circle key={`${run.id}/${i}`} cx={x} cy={y} r={radius} fill={color} />),
      ),
    [placed, radius],
  );

  // The run nearest the pointer, within its column; at most once a frame. A finger is blunter
  // than a mouse, so it reaches further for a dot.
  const frame = useRef(0);
  const pick = (event: React.PointerEvent<SVGSVGElement>) => {
    const { clientX, clientY } = event;
    const reach = event.pointerType === "mouse" ? 9 : 24;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const rect = svg.current!.getBoundingClientRect();
      const px = clientX - rect.left;
      const py = clientY - rect.top;
      const offset = px - left;
      const column = split && offset > band ? Math.floor((offset - GAP) / band) : Math.floor(offset / band);
      if (column < 0 || column >= columns.length) {
        setHover(null);
        setBoxHover(null);
        return;
      }
      let best: SinaRun | null = null;
      let distance = reach;
      for (const dot of placed[column]!) {
        const d = Math.hypot(dot.x - px, dot.y - py);
        if (d < distance) [best, distance] = [dot.run, d];
      }
      // Only a change of run or column redraws.
      setHover((now) => (best ? (now?.run === best && now.column === column ? now : { run: best, column }) : null));
      setBoxHover(best ? null : column);
    });
  };

  // Tick marks per panel: [first column, last column + 1, where the labels go, where the grid ends].
  const panels: [number, number, number, number][] = independent
    ? columns.map((_, i) => [i, i + 1, left + band * i + gutter, left + band * (i + 1) - 6])
    : split
      ? [[0, 1, left, left + band], [1, columns.length, left + band + GAP, left + band * columns.length + GAP]]
      : [[0, columns.length, left, left + band * columns.length]];
  const traced = hover?.run;
  const column = hover?.column ?? boxHover;
  const summaries = column != null ? groups.map((group, g) => ({ group, s: stats[column]?.[g] })).filter((x) => x.s) : [];
  return (
    <div className="chart sina" ref={root}>
      {/* What is pointed at, above the plot so it never covers it. */}
      <div className="sina-caption" aria-live="polite">
        {traced && column != null ? (
          <>
            <strong>{traced.title}</strong>
            <span className="num">
              {columns[column]} <strong>{format(traced.values[column]!)}</strong>
            </span>
            <span className="muted">{traced.detail}</span>
          </>
        ) : summaries.length ? (
          <>
            <strong>{columns[column!]}</strong>
            {summaries.map(({ group, s }) => (
              <span key={group.id} className="sina-caption-group">
                {group.label && (
                  <span className="sina-caption-key">
                    <span className="legend-swatch-dot" style={{ background: group.color }} />
                    {group.label}
                  </span>
                )}
                <span className="num">
                  median <strong>{format(s!.median)}</strong>
                </span>
                <span className="num muted">
                  middle half {format(s!.q1)}–{format(s!.q3)} · {s!.n} runs
                </span>
              </span>
            ))}
          </>
        ) : null}
      </div>
      <svg
        ref={svg}
        width={width}
        height={height}
        role="img"
        aria-label={`${yLabel} for each segment, every run`}
        // A mouse traces what it hovers. A touch has no hover: a tap picks a run (or a column's
        // summary) and it stays picked when the finger lifts, until the next tap; sliding a
        // finger sideways scrubs, while up and down still scrolls the page.
        onPointerMove={(event) => {
          if (event.pointerType === "mouse" || event.buttons) pick(event);
        }}
        onPointerDown={(event) => {
          if (event.pointerType !== "mouse") pick(event);
        }}
        onPointerLeave={(event) => {
          if (event.pointerType !== "mouse") return;
          cancelAnimationFrame(frame.current);
          setHover(null);
          setBoxHover(null);
        }}
        // A long press would otherwise open the browser's menu or start selecting text.
        onContextMenu={(event) => event.preventDefault()}
      >
        {panels.map(([from, , start, end]) =>
          niceTicks(...domainOf(from), independent || (from === 0 && split) ? 4 : 5).map((tick) => (
            <g key={`${from}/${tick}`}>
              <line className="chart-grid" x1={start} x2={end} y1={y(tick, from)} y2={y(tick, from)} />
              {(!independent || gutter > 0) && (
                <text className="chart-tick" x={start - 6} y={y(tick, from)} dy="0.32em" textAnchor="end">
                  {format(tick)}
                </text>
              )}
            </g>
          )),
        )}
        {axisLabels.map(({ label, column }) => (
          <text key={column} className="chart-tick" x={cx(column)} y={MARGIN.top + plotHeight + 22} textAnchor="middle">
            {label}
          </text>
        ))}
        <g className={`sina-dots${traced ? " dimmed" : ""}`}>{dots}</g>
        {stats.map((column, i) =>
          column.map((s, g) => {
            if (!s) return null;
            const side = sideOf(g);
            // A whole violin, or with two groups the half on this group's side of the centre.
            const outline = s.shape.map((p) => `${cx(i) + (side || 1) * p.width * half},${y(p.value, i)}`);
            const back = side
              ? [`${cx(i)},${y(s.shape[s.shape.length - 1]!.value, i)}`, `${cx(i)},${y(s.shape[0]!.value, i)}`]
              : [...s.shape].reverse().map((p) => `${cx(i) - p.width * half},${y(p.value, i)}`);
            const x = cx(i) + side * 5;
            return (
              <g
                key={`${s.label}/${g}`}
                className={`sina-violin${boxHover === i ? " on" : ""}`}
                style={{ "--sina": groups[g]!.color } as React.CSSProperties}
              >
                <path d={`M${[...outline, ...back].join(" L")} Z`} className="sina-shape" />
                <line x1={x} x2={x} y1={y(s.q1, i)} y2={y(s.q3, i)} className="sina-iqr" />
                <circle cx={x} cy={y(s.median, i)} r={3.5} className="sina-median" />
              </g>
            );
          }),
        )}
        {traced && (
          <g className="sina-trace">
            <polyline
              points={traced.values
                .map((v, i) => (v == null || (split && i === 0) ? null : `${dotX(traced, i)},${y(v, i)}`))
                .filter(Boolean)
                .join(" ")}
            />
            {split && traced.values[0] != null && traced.values[1] != null && (
              <line
                className="sina-break"
                x1={dotX(traced, 0)}
                y1={y(traced.values[0], 0)}
                x2={dotX(traced, 1)}
                y2={y(traced.values[1], 1)}
              />
            )}
            {traced.values.map((v, i) =>
              v == null ? null : (
                <circle key={i} cx={dotX(traced, i)} cy={y(v, i)} r={radius + 1.8} style={given?.length ? { fill: groups[groupOf(traced)]!.color } : undefined} />
              ),
            )}
          </g>
        )}
      </svg>
    </div>
  );
}
