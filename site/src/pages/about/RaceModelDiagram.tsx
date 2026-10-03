// Even pace against the typical race: pick an event and a time, and see how far along a runner
// who spreads the race evenly would be at each moment, beside one who runs it as runners in
// that event typically do. Faint lines mark a quarter, half and three quarters of the time
// and of the distance.

import { useMemo, useState } from "react";
import { useWidth } from "../../components/charts/useWidth";
import { eventName, time } from "../../data/format";
import { useIndex } from "../../data/load";
import type { EventOut } from "../../data/types";
import { motion, type Motion } from "../../track/geometry";
import { parseTime } from "../../track/model";

const QUARTERS = [0.25, 0.5, 0.75];

/** When ``m`` reached ``d`` (it never runs backwards, so bisect). */
function when(m: Motion, d: number): number {
  let [lo, hi] = [0, m.end];
  for (let k = 0; k < 50; k++) {
    const mid = (lo + hi) / 2;
    if ((m.at(mid) ?? 0) < d) lo = mid;
    else hi = mid;
  }
  return hi;
}

/** A typical run of ``event`` finishing in ``finish``: leaving the blocks at the typical
 * reaction (or the gun, from a standing start) and running the typical race. */
export function typicalRun(event: EventOut, finish: number): Motion {
  const shape = event.shape!.points;
  const distance = shape[shape.length - 1]!.distance;
  const reaction = event.reaction ?? 0;
  const knots = [{ t: 0, d: 0 }, ...(reaction > 0 ? [{ t: reaction, d: 0 }] : []), { t: finish, d: distance }];
  return motion(knots, true, shape);
}

/** A share of the race from leaving the blocks, as a share of the time from the gun. */
function fromGun(share: number, reaction: number, finish: number): number {
  return (reaction + share * (finish - reaction)) / finish;
}

const percent = (share: number) => `${(share * 100).toFixed(1)}%`;
const lowerFirst = (text: string) => text.charAt(0).toLowerCase() + text.slice(1);

export function RaceModelDiagram() {
  const index = useIndex();
  const events = useMemo(() => index.events.filter((e) => e.shape), [index]);
  const [eventId, setEventId] = useState("400m-men");
  const event = events.find((e) => e.id === eventId) ?? events[0]!;
  const shape = event.shape!;
  const [text, setText] = useState(() => shape.median.toFixed(2));
  const typed = parseTime(text);
  const finish = typed && typed > 0 ? typed : shape.median;
  const distance = shape.points[shape.points.length - 1]!.distance;
  const run = useMemo(() => typicalRun(event, finish), [event, finish]);
  const reaction = event.reaction ?? 0;

  const [box, width] = useWidth<HTMLDivElement>(640);
  const h = Math.min(340, Math.max(240, width * 0.55));
  const m = { left: 48, right: 48, top: 14, bottom: 40 };
  const x = (t: number) => m.left + (t / finish) * (width - m.left - m.right);
  const y = (d: number) => h - m.bottom - (d / distance) * (h - m.top - m.bottom);
  const curve = Array.from({ length: 241 }, (_, i) => (i / 240) * finish)
    .map((t) => `${x(t).toFixed(1)},${y(run.at(t) ?? 0).toFixed(1)}`)
    .join(" ");
  // Where the typical runner passes a quarter, half and three quarters of the distance.
  const marks = QUARTERS.map((q) => ({ q, t: when(run, q * distance) }));
  // Below, the same race as metres ahead of (or behind) a runner at even pace, which shows the
  // shape that distance against time flattens.
  const ahead = Array.from({ length: 241 }, (_, i) => (i / 240) * finish).map((t) => ({ t, gap: (run.at(t) ?? 0) - (distance * t) / finish }));
  const reach = Math.max(1, ...ahead.map((p) => Math.abs(p.gap)));
  const span = reach <= 2 ? Math.ceil(reach * 2) / 2 : Math.ceil(reach);
  const gh = 130;
  const gy = (gap: number) => m.top + ((span - gap) / (2 * span)) * (gh - m.top - 26);
  const gapLine = ahead.map((p) => `${x(p.t).toFixed(1)},${gy(p.gap).toFixed(1)}`).join(" ");

  // The point nearest halfway, where the faster and slower halves of the runs are compared.
  const halfway = shape.points
    .slice(0, -1)
    .reduce((best, p) => (Math.abs(p.distance - distance / 2) < Math.abs(best.distance - distance / 2) ? p : best));

  return (
    <figure className="about-figure">
      <div className="about-controls">
        <label className="select">
          <span className="visually-hidden">Event</span>
          <select
            value={event.id}
            onChange={(e) => {
              const next = events.find((ev) => ev.id === e.target.value)!;
              setEventId(next.id);
              setText(next.shape!.median.toFixed(2));
            }}
          >
            {events.map((e) => (
              <option key={e.id} value={e.id}>
                {eventName(index, e.id)}
              </option>
            ))}
          </select>
        </label>
        <label className="planner-input">
          <span>Time</span>
          <input
            className="text-input num"
            inputMode="decimal"
            value={text}
            onChange={(e) => setText(e.target.value)}
            aria-label="Finishing time, in seconds or minutes and seconds"
          />
        </label>
        <span className="about-legend">
          <span>
            <span className="about-key even" /> Even pace
          </span>
          <span>
            <span className="about-key typical" /> Typical race
          </span>
        </span>
      </div>
      <div ref={box} className="about-track">
        <svg width={width} height={h} role="img" aria-label={`Distance against time for a ${time(finish)} ${eventName(index, event.id)}: even pace and the typical race`}>
          {QUARTERS.map((q) => (
            <g key={q}>
              <line x1={x(q * finish)} x2={x(q * finish)} y1={m.top} y2={h - m.bottom} className="about-grid" />
              <line x1={m.left} x2={width - m.right} y1={y(q * distance)} y2={y(q * distance)} className="about-grid" />
            </g>
          ))}
          <line x1={m.left} x2={width - m.right} y1={h - m.bottom} y2={h - m.bottom} className="about-axis" />
          <line x1={m.left} x2={m.left} y1={m.top} y2={h - m.bottom} className="about-axis" />
          {[0, ...QUARTERS, 1].map((q) => (
            <g key={q}>
              <text x={x(q * finish)} y={h - m.bottom + 15} className="about-tick" textAnchor="middle">
                {q === 0 ? "0" : time(q * finish)}
              </text>
              <text x={m.left - 6} y={y(q * distance) + 4} className="about-tick" textAnchor="end">
                {Math.round(q * distance)}m
              </text>
              <text x={width - m.right + 6} y={y(q * distance) + 4} className="about-tick">
                {q * 100}%
              </text>
            </g>
          ))}
          <text x={(m.left + width - m.right) / 2} y={h - 4} className="about-tick" textAnchor="middle">
            Seconds from the gun
          </text>
          <line x1={x(0)} y1={y(0)} x2={x(finish)} y2={y(distance)} className="about-even" />
          <polyline points={curve} className="about-curve" />
          {marks.map(({ q, t }) => (
            <g key={q}>
              <circle cx={x(t)} cy={y(q * distance)} r={3.5} className="about-kept you" />
              <text x={x(t) - 6} y={y(q * distance) - 7} className="about-label strong" fontSize={11.5} textAnchor="end">
                {time(t)}
              </text>
            </g>
          ))}
        </svg>
        <svg width={width} height={gh} role="img" aria-label="Metres ahead of or behind a runner at even pace">
          {QUARTERS.map((q) => (
            <line key={q} x1={x(q * finish)} x2={x(q * finish)} y1={m.top} y2={gh - 26} className="about-grid" />
          ))}
          <line x1={m.left} x2={width - m.right} y1={gy(0)} y2={gy(0)} className="about-even" />
          {[span, -span].map((v) => (
            <text key={v} x={m.left - 6} y={gy(v) + 4} className="about-tick" textAnchor="end">
              {v > 0 ? "+" : "−"}
              {Math.abs(v)}m
            </text>
          ))}
          <polyline points={gapLine} className="about-curve" />
          <text x={(m.left + width - m.right) / 2} y={gh - 6} className="about-tick" textAnchor="middle">
            Metres ahead of (+) or behind (−) even pace
          </text>
        </svg>
      </div>
      <figcaption>
        In a {time(finish)} {lowerFirst(eventName(index, event.id))}, a typical runner passes{" "}
        {marks.map(({ q, t }, i) => (
          <span key={q}>
            {i > 0 ? (i === marks.length - 1 ? " and " : ", ") : ""}
            {Math.round(q * distance)}m at {time(t)} s ({percent(t / finish)} of the time)
          </span>
        ))}
        ; at even pace it would be 25%, 50% and 75%. Of the {shape.runs} timed runs the typical race is drawn from, the
        faster half (under {time(shape.median)} s) reached {halfway.distance}m at{" "}
        {percent(fromGun(halfway.faster, reaction, finish))} of their race, the slower half at{" "}
        {percent(fromGun(halfway.slower, reaction, finish))}.
      </figcaption>
    </figure>
  );
}
