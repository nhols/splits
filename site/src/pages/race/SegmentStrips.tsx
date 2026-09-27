// Segment times: for each stretch between timing points, every athlete's time for it as a dot,
// the fastest labelled. Times, not speeds: the numbers athletes train to. Pointing at a stretch
// marks it on the track.

import { useState } from "react";
import { time } from "../../data/format";
import type { RaceData } from "../../data/types";
import { stretchKey } from "../../track/runners";
import { previousClean, raceDistance, type Row } from "./model";
import "../../components/charts/charts.css";

interface Strip {
  key: string;
  label: string;
  entries: { row: Row; value: number }[];
}

function strips(race: RaceData, rows: Row[]): Strip[] {
  const finishIndex = race.points.length - 1;
  const ends = race.points.map((_, index) => index).filter((index) => race.points[index]!.kind !== "start");
  const byLabel = new Map<string, Strip>();
  for (const index of ends) {
    for (const row of rows) {
      const cell = index === finishIndex ? null : row.cells.get(index);
      const end = index === finishIndex ? row.finish : cell && !cell.suspect ? cell.split.time.v : null;
      if (end === null || end === undefined) continue;
      const previous = previousClean(race, row, index);
      // Only segments between consecutive points: a skipped point would mix segment lengths.
      const expected = index === 0 ? null : index - 1;
      if (previous.index !== expected) continue;
      const from = previous.index === null ? "Start" : race.points[previous.index]!.label;
      const to = index === finishIndex ? `${raceDistance(race)}m` : race.points[index]!.label;
      const label = `${from}–${to}`;
      const key = stretchKey(previous.distance, index === finishIndex ? raceDistance(race) : race.points[index]!.distance);
      const strip = byLabel.get(label) ?? { key, label, entries: [] };
      strip.entries.push({ row, value: end - previous.time });
      byLabel.set(label, strip);
    }
  }
  return [...byLabel.values()].filter((s) => s.entries.length > 1);
}

export function SegmentStrips({
  race,
  rows,
  highlight,
  onHighlight,
  stretch,
  onStretch,
}: {
  race: RaceData;
  rows: Row[];
  highlight: string | null;
  onHighlight: (id: string | null) => void;
  stretch: string | null;
  onStretch: (key: string | null) => void;
}) {
  const all = strips(race, rows);
  const [hover, setHover] = useState<{ strip: number; entry: number } | null>(null);
  if (!all.length) return <p className="secondary">Not enough timing points to compare segments.</p>;
  return (
    <div className="strips" onPointerLeave={() => setHover(null)}>
      {all.map((strip, i) => {
        const values = strip.entries.map((e) => e.value);
        const lo = Math.min(...values);
        const hi = Math.max(...values);
        const span = Math.max(hi - lo, 0.05);
        const position = (v: number) => 4 + ((v - lo) / span) * 92;
        const fastest = strip.entries.reduce((a, b) => (b.value < a.value ? b : a));
        return (
          <div
            key={strip.key}
            className={`strip${stretch === strip.key ? " on" : ""}`}
            onPointerEnter={(event) => event.pointerType === "mouse" && onStretch(strip.key)}
            onPointerLeave={(event) => event.pointerType === "mouse" && onStretch(null)}
            onClick={() => onStretch(strip.key)}
          >
            <span className="strip-label">{strip.label}</span>
            <span className="strip-track">
              <span className="strip-axis" />
              {strip.entries.map((entry, j) => {
                const faded = highlight !== null && highlight !== entry.row.perf.id;
                return (
                  <span
                    key={entry.row.perf.id}
                    className={`strip-dot${faded ? " faded" : ""}${highlight === entry.row.perf.id ? " on" : ""}`}
                    style={{ left: `${position(entry.value)}%`, background: entry.row.color }}
                    onPointerEnter={() => {
                      setHover({ strip: i, entry: j });
                      onHighlight(entry.row.perf.id);
                    }}
                    onPointerLeave={() => onHighlight(null)}
                    title={`${entry.row.name}: ${time(entry.value)}`}
                  />
                );
              })}
              {hover?.strip === i && strip.entries[hover.entry] && (
                <span className="strip-tip" style={{ left: `${position(strip.entries[hover.entry]!.value)}%` }}>
                  <strong className="num">{time(strip.entries[hover.entry]!.value)}</strong> {strip.entries[hover.entry]!.row.short}
                </span>
              )}
            </span>
            <span className="strip-best">
              <strong className="num">{time(fastest.value)}</strong> <span className="muted">{fastest.row.short}</span>
            </span>
          </div>
        );
      })}
      <div className="strip strip-scale muted">
        <span />
        <span className="strip-scale-labels">
          <span>faster</span>
          <span>slower</span>
        </span>
        <span>fastest</span>
      </div>
    </div>
  );
}
