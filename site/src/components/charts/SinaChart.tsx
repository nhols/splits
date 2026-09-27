// The spread of every run's time over each segment of a race: a violin per segment, its width
// the density of times, with every run a dot inside it (spread sideways by that density), a
// line over the middle half and a dot at the median. Pointing at a dot follows that run through every segment.

import { useMemo, useRef, useState } from "react";
import { useWidth } from "./useWidth";
import "./charts.css";

export interface SinaRun {
  id: string;
  /** The run's value in each column (null where not known). */
  values: (number | null)[];
  title: string;
  detail: string;
}

interface Props {
  columns: string[];
  /** Shorter labels for when the columns are too narrow for theirs (e.g. just "120m"). */
  shortColumns?: string[];
  runs: SinaRun[];
  format: (value: number) => string;
  yLabel: string;
  height?: number;
}

const MARGIN = { top: 14, right: 12, bottom: 34, left: 48 };

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

export function SinaChart({ columns, shortColumns, runs, format, yLabel, height = 360 }: Props) {
  const [root, width] = useWidth<HTMLDivElement>(800);
  const [hover, setHover] = useState<{ run: SinaRun; column: number } | null>(null);
  const [boxHover, setBoxHover] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);

  const stats = useMemo(() => columns.map((label, i) => summarise(label, i, runs)), [columns, runs]);
  // The first segment (the start, with the reaction and the acceleration, or the run to the
  // first hurdle) is often far slower than the rest: then it gets a scale of its own, set
  // apart, so it doesn't squash the others.
  // A scale covering the violins, whose outlines run a little past the extreme runs.
  const range = (from: number, to: number): [number, number] => {
    const values = stats.slice(from, to).flatMap((column) => (column ? [column.shape[0]!.value, column.shape[column.shape.length - 1]!.value] : []));
    const [lo, hi] = [Math.min(...values), Math.max(...values)];
    const pad = (hi - lo) * 0.02 || 0.5;
    return [lo - pad, hi + pad];
  };
  const first = columns.length > 2 ? range(0, 1) : null;
  const rest = columns.length > 2 ? range(1, columns.length) : null;
  const split = first !== null && rest !== null && (first[0] > rest[1] || first[1] < rest[0]);
  const whole = range(0, columns.length);
  const domainOf = (column: number): [number, number] => (split ? (column === 0 ? first! : rest!) : whole);

  const GAP = split ? 56 : 0;
  const plotWidth = Math.max(width - MARGIN.left - MARGIN.right - GAP, 100);
  const plotHeight = height - MARGIN.top - MARGIN.bottom;
  const band = plotWidth / columns.length;
  const half = Math.min(band * 0.4, 80);
  const cx = (column: number) => MARGIN.left + band * (column + 0.5) + (split && column > 0 ? GAP : 0);
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

  const dotX = (run: SinaRun, column: number) => cx(column) + (stats[column]?.offsets.get(run.id) ?? 0) * half;
  const radius = runs.length > 150 ? 2.2 : 3;

  // The run nearest the pointer, within its column.
  const onMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const rect = svg.current!.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const offset = px - MARGIN.left;
    const column = split && offset > band ? Math.floor((offset - GAP) / band) : Math.floor(offset / band);
    if (column < 0 || column >= columns.length) {
      setHover(null);
      setBoxHover(null);
      return;
    }
    let best: SinaRun | null = null;
    let distance = 9;
    for (const run of runs) {
      const v = run.values[column];
      if (v == null) continue;
      const d = Math.hypot(dotX(run, column) - px, y(v, column) - py);
      if (d < distance) [best, distance] = [run, d];
    }
    setHover(best ? { run: best, column } : null);
    setBoxHover(best ? null : column);
  };

  // Tick marks per panel: [first column, last column + 1, where the labels go].
  const panels: [number, number, number][] = split ? [[0, 1, MARGIN.left], [1, columns.length, MARGIN.left + band + GAP]] : [[0, columns.length, MARGIN.left]];
  const traced = hover?.run;
  const column = hover?.column ?? boxHover;
  const summary = column != null ? stats[column] : null;
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
        ) : summary ? (
          <>
            <strong>{columns[column!]}</strong>
            <span className="num">
              median <strong>{format(summary.median)}</strong>
            </span>
            <span className="num muted">
              middle half {format(summary.q1)}–{format(summary.q3)} · {summary.n} runs
            </span>
          </>
        ) : null}
      </div>
      <svg
        ref={svg}
        width={width}
        height={height}
        role="img"
        aria-label={`${yLabel} for each segment, every run`}
        onPointerMove={onMove}
        onPointerLeave={() => {
          setHover(null);
          setBoxHover(null);
        }}
      >
        {panels.map(([from, to, left]) =>
          niceTicks(...domainOf(from), from === 0 && split ? 4 : 5).map((tick) => (
            <g key={`${from}/${tick}`}>
              <line className="chart-grid" x1={left} x2={left + band * (to - from)} y1={y(tick, from)} y2={y(tick, from)} />
              <text className="chart-tick" x={left - 8} y={y(tick, from)} dy="0.32em" textAnchor="end">
                {format(tick)}
              </text>
            </g>
          )),
        )}
        {axisLabels.map(({ label, column }) => (
          <text key={column} className="chart-tick" x={cx(column)} y={MARGIN.top + plotHeight + 22} textAnchor="middle">
            {label}
          </text>
        ))}
        <g className={`sina-dots${traced ? " dimmed" : ""}`}>
          {runs.map((run) =>
            run.values.map((v, i) => (v == null ? null : <circle key={`${run.id}/${i}`} cx={dotX(run, i)} cy={y(v, i)} r={radius} />)),
          )}
        </g>
        {stats.map((s, i) =>
          s ? (
            <g key={s.label} className={`sina-violin${boxHover === i ? " on" : ""}`}>
              <path
                d={`M${s.shape.map((p) => `${cx(i) + p.width * half},${y(p.value, i)}`).join(" L")} L${[...s.shape]
                  .reverse()
                  .map((p) => `${cx(i) - p.width * half},${y(p.value, i)}`)
                  .join(" L")} Z`}
                className="sina-shape"
              />
              <line x1={cx(i)} x2={cx(i)} y1={y(s.q1, i)} y2={y(s.q3, i)} className="sina-iqr" />
              <circle cx={cx(i)} cy={y(s.median, i)} r={3.5} className="sina-median" />
            </g>
          ) : null,
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
            {traced.values.map((v, i) => (v == null ? null : <circle key={i} cx={dotX(traced, i)} cy={y(v, i)} r={radius + 1.8} />))}
          </g>
        )}
      </svg>
    </div>
  );
}
