// A scatter chart: one dot per performance. At most three coloured groups (the palette's
// all-pairs limit); hovering finds the nearest dot, so small dots are easy to read.

import { Delaunay } from "d3-delaunay";
import { scaleLinear } from "d3-scale";
import { useMemo, useState, type ReactNode } from "react";
import { useWidth } from "./useWidth";
import "./charts.css";

export interface Dot {
  id: string;
  x: number;
  y: number;
  group: string;
}

export interface Group {
  id: string;
  label: string;
  color: string;
}

interface Props {
  dots: Dot[];
  groups: Group[];
  xLabel: string;
  yLabel: string;
  xFormat: (value: number) => string;
  yFormat: (value: number) => string;
  height?: number;
  highlight?: Set<string>;
  reference?: { y: number; label: string };
  tooltip: (dot: Dot) => ReactNode;
  onSelect?: (dot: Dot) => void;
}

const MARGIN = { top: 26, right: 20, bottom: 44, left: 48 };

export function ScatterChart({
  dots,
  groups,
  xLabel,
  yLabel,
  xFormat,
  yFormat,
  height = 360,
  highlight,
  reference,
  tooltip,
  onSelect,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<Dot | null>(null);
  const plotWidth = Math.max(width - MARGIN.left - MARGIN.right, 50);
  const plotHeight = height - MARGIN.top - MARGIN.bottom;

  const x = useMemo(() => {
    const values = dots.map((d) => d.x);
    return scaleLinear()
      .domain([Math.min(...values), Math.max(...values)])
      .range([MARGIN.left, MARGIN.left + plotWidth])
      .nice(6);
  }, [dots, plotWidth]);
  const y = useMemo(() => {
    const values = dots.map((d) => d.y).concat(reference ? [reference.y] : []);
    return scaleLinear()
      .domain([Math.min(...values), Math.max(...values)])
      .range([MARGIN.top + plotHeight, MARGIN.top])
      .nice(6);
  }, [dots, plotHeight, reference]);

  const delaunay = useMemo(
    () => Delaunay.from(dots, (d) => x(d.x), (d) => y(d.y)),
    [dots, x, y],
  );
  const colors = new Map(groups.map((g) => [g.id, g.color]));
  const emphasised = (dot: Dot) => !highlight || highlight.size === 0 || highlight.has(dot.id);
  const ordered = [...dots].sort((a, b) => Number(emphasised(a)) - Number(emphasised(b)));

  return (
    <div ref={ref} className="chart">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`${yLabel} against ${xLabel}`}
        onPointerMove={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          const index = delaunay.find(event.clientX - bounds.left, event.clientY - bounds.top);
          const dot = dots[index];
          if (!dot) return setHover(null);
          const distance = Math.hypot(x(dot.x) - (event.clientX - bounds.left), y(dot.y) - (event.clientY - bounds.top));
          setHover(distance < 40 ? dot : null);
        }}
        onPointerLeave={() => setHover(null)}
        onClick={() => hover && onSelect?.(hover)}
        style={{ cursor: hover && onSelect ? "pointer" : undefined }}
      >
        {y.ticks(6).map((tick) => (
          <g key={`y${tick}`}>
            <line className="chart-grid" x1={MARGIN.left} x2={MARGIN.left + plotWidth} y1={y(tick)} y2={y(tick)} />
            <text className="chart-tick" x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
              {yFormat(tick)}
            </text>
          </g>
        ))}
        {x.ticks(7).map((tick) => (
          <text key={`x${tick}`} className="chart-tick" x={x(tick)} y={MARGIN.top + plotHeight + 20} textAnchor="middle">
            {xFormat(tick)}
          </text>
        ))}
        <line className="chart-baseline" x1={MARGIN.left} x2={MARGIN.left + plotWidth} y1={MARGIN.top + plotHeight} y2={MARGIN.top + plotHeight} />
        <text className="chart-axis-label" x={MARGIN.left + plotWidth / 2} y={height - 6} textAnchor="middle">
          {xLabel}
        </text>
        <text className="chart-axis-label" x={MARGIN.left - 8} y={10} textAnchor="start">
          {yLabel}
        </text>
        {reference && (
          <g>
            <line className="chart-reference" x1={MARGIN.left} x2={MARGIN.left + plotWidth} y1={y(reference.y)} y2={y(reference.y)} />
            <text className="chart-tick" x={MARGIN.left + plotWidth - 4} y={y(reference.y) - 6} textAnchor="end">
              {reference.label}
            </text>
          </g>
        )}
        {ordered.map((dot) => (
          <circle
            key={dot.id}
            cx={x(dot.x)}
            cy={y(dot.y)}
            r={emphasised(dot) && highlight?.size ? 5.5 : 4}
            className="chart-dot"
            fill={emphasised(dot) ? (colors.get(dot.group) ?? "var(--series-other)") : "var(--series-other)"}
            opacity={emphasised(dot) ? 0.9 : 0.35}
          />
        ))}
        {hover && (
          <circle cx={x(hover.x)} cy={y(hover.y)} r={8} className="chart-hover-ring" pointerEvents="none" />
        )}
      </svg>
      {hover && (
        <div
          className="chart-tooltip"
          style={{
            left: Math.min(x(hover.x) + 14, width - 240),
            top: Math.max(y(hover.y) - 20, 0),
            transform: x(hover.x) > width - 260 ? "translateX(-110%)" : undefined,
          }}
        >
          {tooltip(hover)}
        </div>
      )}
    </div>
  );
}
