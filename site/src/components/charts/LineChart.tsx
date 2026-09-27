// A multi-series line chart over race distance: hairline grid, 2px lines, a crosshair that
// snaps to the nearest timing point and lists every series there, direct end labels spread
// apart with leader lines, optional bands (a series' middle half), and suspect points drawn
// hollow and left off the line. Arrow keys move the crosshair.

import { scaleLinear } from "d3-scale";
import { area, curveLinear, curveMonotoneX, line } from "d3-shape";
import { useMemo, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { spreadLabels, useWidth } from "./useWidth";
import "./charts.css";

export interface Datum {
  x: number;
  y: number;
  suspect?: boolean;
  /** For steps: the segment the value covers. */
  x0?: number;
  x1?: number;
}

export interface Series {
  id: string;
  label: string;
  /** Short text for the end label; defaults to label. */
  endLabel?: string;
  color: string;
  data: Datum[];
}

export interface Band {
  id: string;
  color: string;
  data: { x: number; y0: number; y1: number }[];
}

export interface Tick {
  value: number;
  label: string;
}

interface Props {
  series: Series[];
  bands?: Band[];
  xDomain: [number, number];
  xTicks: Tick[];
  yFormat: (value: number) => string;
  yLabel: string;
  height?: number;
  yDomain?: [number, number];
  endLabels?: boolean;
  smooth?: boolean;
  /** Draw each datum as a flat step over [x0, x1], e.g. an average speed over a segment. */
  steps?: boolean;
  highlight?: string | null;
  onHighlight?: (id: string | null) => void;
  tooltipTitle: (x: number) => ReactNode;
  tooltipValue?: (series: Series, datum: Datum) => ReactNode;
}

const MARGIN = { top: 26, bottom: 34, left: 52 };

export function LineChart({
  series,
  bands = [],
  xDomain,
  xTicks,
  yFormat,
  yLabel,
  height = 320,
  yDomain,
  endLabels = true,
  smooth = false,
  steps = false,
  highlight = null,
  onHighlight,
  tooltipTitle,
  tooltipValue,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hoverX, setHoverX] = useState<number | null>(null);
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null);
  const right = endLabels ? Math.min(150, Math.max(90, width * 0.16)) : 20;

  const plotWidth = Math.max(width - MARGIN.left - right, 50);
  const plotHeight = height - MARGIN.top - MARGIN.bottom;

  const x = useMemo(
    () => scaleLinear().domain(xDomain).range([MARGIN.left, MARGIN.left + plotWidth]),
    [xDomain, plotWidth],
  );
  const y = useMemo(() => {
    const values = [
      ...series.flatMap((s) => s.data.filter((d) => !d.suspect).map((d) => d.y)),
      ...bands.flatMap((b) => b.data.flatMap((d) => [d.y0, d.y1])),
    ];
    const [lo, hi] = yDomain ?? [Math.min(...values), Math.max(...values)];
    const pad = (hi - lo) * 0.06 || 0.5;
    // Gaps start from zero, the leader: no padding below it.
    const scale = scaleLinear()
      .domain(yDomain ?? [lo >= 0 ? Math.max(lo - pad, 0) : lo - pad, hi + pad])
      .range([MARGIN.top + plotHeight, MARGIN.top]);
    return yDomain ? scale : scale.nice(5);
  }, [series, bands, yDomain, plotHeight]);

  const xs = useMemo(
    () => [...new Set(series.flatMap((s) => s.data.map((d) => d.x)))].sort((a, b) => a - b),
    [series],
  );

  const draw = line<Datum>()
    .x((d) => x(d.x))
    .y((d) => y(d.y))
    .curve(smooth ? curveMonotoneX : curveLinear);
  const drawBand = area<{ x: number; y0: number; y1: number }>()
    .x((d) => x(d.x))
    .y0((d) => y(d.y0))
    .y1((d) => y(d.y1))
    .curve(smooth ? curveMonotoneX : curveLinear);

  const ordered = highlight
    ? [...series.filter((s) => s.id !== highlight), ...series.filter((s) => s.id === highlight)]
    : series;

  const labelPositions = useMemo(() => {
    const wishes = series.flatMap((s) => {
      const last = [...s.data].reverse().find((d) => !d.suspect);
      return last ? [{ id: s.id, y: y(last.y) }] : [];
    });
    return spreadLabels(wishes, 14, MARGIN.top + 4, MARGIN.top + plotHeight);
  }, [series, y, plotHeight]);

  const move = (event: PointerEvent<SVGRectElement>) => {
    const bounds = event.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const px = event.clientX - bounds.left;
    let nearest: number | null = null;
    for (const value of xs) {
      if (nearest === null || Math.abs(x(value) - px) < Math.abs(x(nearest) - px)) nearest = value;
    }
    setHoverX(nearest);
    setPointer({ x: px, y: event.clientY - bounds.top });
  };

  const keyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!xs.length || (event.key !== "ArrowRight" && event.key !== "ArrowLeft")) return;
    event.preventDefault();
    const index = hoverX === null ? -1 : xs.indexOf(hoverX);
    const next = event.key === "ArrowRight" ? Math.min(index + 1, xs.length - 1) : Math.max(index - 1, 0);
    setHoverX(xs[next]!);
    setPointer({ x: x(xs[next]!), y: MARGIN.top + 20 });
  };

  const rows =
    hoverX === null
      ? []
      : series
          .map((s) => ({ s, d: s.data.find((d) => d.x === hoverX) }))
          .filter((row): row is { s: Series; d: Datum } => row.d !== undefined)
          .sort((a, b) => b.d.y - a.d.y);

  const yTicks = y.ticks(5);
  const clampY = (value: number) => Math.min(Math.max(value, MARGIN.top), MARGIN.top + plotHeight);

  return (
    <div
      ref={ref}
      className="chart"
      tabIndex={0}
      onKeyDown={keyboard}
      onBlur={() => setHoverX(null)}
      aria-label={`${yLabel} chart; use the arrow keys to read values at each timing point`}
    >
      <svg width={width} height={height} role="img" aria-hidden="true">
        {yTicks.map((tick) => (
          <g key={tick}>
            <line className="chart-grid" x1={MARGIN.left} x2={MARGIN.left + plotWidth} y1={y(tick)} y2={y(tick)} />
            <text className="chart-tick" x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
              {yFormat(tick)}
            </text>
          </g>
        ))}
        <text className="chart-axis-label" x={MARGIN.left - 8} y={10} textAnchor="start">
          {yLabel}
        </text>
        <line className="chart-baseline" x1={MARGIN.left} x2={MARGIN.left + plotWidth} y1={MARGIN.top + plotHeight} y2={MARGIN.top + plotHeight} />
        {thinTicks(xTicks, x, 34).map((tick) => (
          <text key={tick.value} className="chart-tick" x={x(tick.value)} y={MARGIN.top + plotHeight + 20} textAnchor="middle">
            {tick.label}
          </text>
        ))}

        {bands.map((band) => (
          <path
            key={band.id}
            d={drawBand(band.data) ?? ""}
            fill={band.color}
            opacity={highlight && highlight !== band.id ? 0.04 : 0.1}
          />
        ))}

        {ordered.map((s) => {
          const faded = highlight !== null && highlight !== s.id;
          const color = faded ? "var(--series-other)" : s.color;
          return (
            <g key={s.id} opacity={faded ? 0.55 : 1} onPointerEnter={() => onHighlight?.(s.id)} onPointerLeave={() => onHighlight?.(null)}>
              <path
                d={(steps ? stepPath(clean(s.data), x, y) : draw(clean(s.data))) ?? ""}
                fill="none"
                stroke={color}
                strokeWidth={highlight === s.id ? 2.5 : 2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {s.data
                .filter((d) => d.suspect)
                .map((d) => (
                  <circle key={`s${d.x}`} className="chart-suspect" cx={x(d.x)} cy={clampY(y(d.y))} r={4.5}>
                    <title>{`${s.label}: suspect value ${yFormat(d.y)}`}</title>
                  </circle>
                ))}
            </g>
          );
        })}

        {endLabels &&
          series.map((s) => {
            const last = [...s.data].reverse().find((d) => !d.suspect);
            const labelY = labelPositions.get(s.id);
            if (!last || labelY === undefined) return null;
            const faded = highlight !== null && highlight !== s.id;
            const x0 = x(last.x1 ?? last.x);
            const y0 = y(last.y);
            return (
              <g key={s.id} className="chart-end-label" opacity={faded ? 0.45 : 1} onPointerEnter={() => onHighlight?.(s.id)} onPointerLeave={() => onHighlight?.(null)}>
                <circle cx={x0} cy={y0} r={4} fill={faded ? "var(--series-other)" : s.color} className="chart-dot" />
                {Math.abs(labelY - y0) > 2 && (
                  <path className="chart-leader" d={`M${x0 + 6},${y0} L${x0 + 12},${labelY} L${x0 + 16},${labelY}`} />
                )}
                <text x={x0 + 18} y={labelY} dy="0.32em" className={highlight === s.id ? "chart-label strong" : "chart-label"}>
                  {fit(s.endLabel ?? s.label, right - 22)}
                  <title>{s.label}</title>
                </text>
              </g>
            );
          })}

        {hoverX !== null && (
          <g pointerEvents="none">
            <line className="chart-crosshair" x1={x(hoverX)} x2={x(hoverX)} y1={MARGIN.top} y2={MARGIN.top + plotHeight} />
            {rows.map(({ s, d }) => (
              <circle
                key={s.id}
                cx={x(d.x)}
                cy={clampY(y(d.y))}
                r={4}
                className={d.suspect ? "chart-suspect" : "chart-dot"}
                fill={d.suspect ? undefined : highlight && highlight !== s.id ? "var(--series-other)" : s.color}
              />
            ))}
          </g>
        )}
        <rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={plotWidth}
          height={plotHeight}
          fill="transparent"
          onPointerMove={move}
          onPointerLeave={() => {
            setHoverX(null);
            setPointer(null);
          }}
        />
      </svg>
      {hoverX !== null && pointer && rows.length > 0 && (
        <div
          className="chart-tooltip"
          style={{
            left: Math.min(Math.max(pointer.x + 16, 0), width - 250),
            top: Math.max(pointer.y - 12, 0),
            transform: pointer.x > width - 270 ? "translateX(-110%)" : undefined,
          }}
        >
          <div className="chart-tooltip-title">{tooltipTitle(hoverX)}</div>
          {rows.slice(0, 10).map(({ s, d }) => (
            <div key={s.id} className="chart-tooltip-row">
              <span className="chart-key" style={{ background: s.color }} />
              <span className="chart-tooltip-value num">{tooltipValue ? tooltipValue(s, d) : yFormat(d.y)}</span>
              <span className="chart-tooltip-label">
                {s.label}
                {d.suspect ? " · suspect" : ""}
              </span>
            </div>
          ))}
          {rows.length > 10 && <div className="chart-tooltip-more">+{rows.length - 10} more</div>}
        </div>
      )}
    </div>
  );
}

/** Shorten a label to fit ``width`` pixels (at the 12px label size), ending in an ellipsis. */
function fit(label: string, width: number): string {
  const chars = Math.floor(width / 6.6);
  return label.length <= chars ? label : `${label.slice(0, Math.max(chars - 1, 1)).trimEnd()}…`;
}

/** The values a line is drawn through: suspect ones are shown separately, not joined. */
function clean(data: Datum[]): Datum[] {
  return data.filter((d) => !d.suspect);
}

/** Flat steps over each datum's segment, joined where segments meet. */
function stepPath(data: Datum[], x: (v: number) => number, y: (v: number) => number): string {
  let path = "";
  let previousEnd: number | null = null;
  for (const d of data) {
    const from = d.x0 ?? d.x;
    const to = d.x1 ?? d.x;
    path += previousEnd === from ? `L${x(from)},${y(d.y)}` : `M${x(from)},${y(d.y)}`;
    path += `L${x(to)},${y(d.y)}`;
    previousEnd = to;
  }
  return path;
}

/** Drop tick labels that would collide, always keeping the last. */
function thinTicks(ticks: Tick[], x: (v: number) => number, minGap: number): Tick[] {
  const kept: Tick[] = [];
  for (const tick of ticks) {
    const previous = kept[kept.length - 1];
    if (!previous || x(tick.value) - x(previous.value) >= minGap) kept.push(tick);
  }
  const last = ticks[ticks.length - 1];
  if (last && kept[kept.length - 1] !== last) {
    if (kept.length > 1 && x(last.value) - x(kept[kept.length - 1]!.value) < minGap) kept.pop();
    kept.push(last);
  }
  return kept;
}
