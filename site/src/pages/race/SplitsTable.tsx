// The race's results with every split. Pointing at a split marks its stretch of the race on the
// track, and the athlete's lane.

import { useState } from "react";
import { Segmented, WarningIcon } from "../../components/ui";
import { printedDigits, time as formatTime } from "../../data/format";
import type { RaceData } from "../../data/types";
import { Link } from "../../router";
import { stretchKey } from "../../track/runners";
import { intermediatePoints, previousClean, raceDistance, type Row } from "./model";

type Mode = "time" | "segment";

interface Props {
  race: RaceData;
  rows: Row[];
  highlight: string | null;
  onHighlight: (id: string | null) => void;
  onStretch: (key: string | null) => void;
}

export function SplitsTable({ race, rows, highlight, onHighlight, onStretch }: Props) {
  const [mode, setMode] = useState<Mode>("time");
  const points = intermediatePoints(race);
  const distance = raceDistance(race);
  const hasLanes = rows.some((row) => row.perf.lane);
  const hasReactions = rows.some((row) => row.perf.reactionTime);
  // The stretch each column ends: from the previous timing point (or the start) to its own.
  const stretches = [...points.map(({ point }) => point.distance), distance].map((to, i, all) =>
    stretchKey(i === 0 ? 0 : all[i - 1]!, to),
  );
  // Times shown as printed: a time printed to the tenth keeps one decimal.
  const digits = (source: number) => printedDigits(race.sources[source]?.text);
  const pointAt = (column: number) => ({
    onPointerEnter: () => onStretch(stretches[column]!),
    onPointerLeave: () => onStretch(null),
  });

  const splitCell = (row: Row, index: number) => {
    const cell = row.cells.get(index);
    if (!cell) return <span className="muted">–</span>;
    if (mode === "time") {
      return (
        <span className={cell.suspect ? "suspect" : ""} title={cell.flags[0]?.message}>
          {cell.suspect && <WarningIcon title={cell.flags[0]?.message} />}{" "}
          {formatTime(cell.split.time.v, digits(cell.split.time.s))}
        </span>
      );
    }
    if (cell.suspect) return <span className="muted">·</span>;
    const previous = previousClean(race, row, index);
    const before = previous.index === null ? undefined : row.cells.get(previous.index);
    const places = Math.min(digits(cell.split.time.s), before ? digits(before.split.time.s) : 3);
    return formatTime(cell.split.time.v - previous.time, places);
  };

  const finishCell = (row: Row) => {
    const perf = row.perf;
    if (mode === "segment") {
      if (row.finish === null) return <span className="muted">–</span>;
      return formatTime(row.finish - previousClean(race, row, race.points.length - 1).time);
    }
    return <strong>{perf.time ? formatTime(perf.time.v, digits(perf.time.s)) : perf.status.toUpperCase()}</strong>;
  };

  return (
    <div className="stack" style={{ "--gap": "14px" } as React.CSSProperties}>
      {points.length > 0 && (
        <div className="toolbar">
          <Segmented
            label="Show"
            value={mode}
            onChange={setMode}
            options={[
              { value: "time", label: "Splits" },
              { value: "segment", label: "Segments" },
            ]}
          />
        </div>
      )}
      <div className="table-wrap">
        <table className="data splits-table">
          <thead>
            <tr>
              <th className="right">Pl</th>
              {hasLanes && <th className="right">Lane</th>}
              <th>Athlete</th>
              {hasReactions && (
                <th className="right" title="Reaction time">
                  RT
                </th>
              )}
              {points.map(({ point, index }, column) => (
                <th key={index} className="right" {...pointAt(column)}>
                  {point.label}
                </th>
              ))}
              <th className="right" {...pointAt(points.length)}>
                {mode === "time" ? "Result" : `${distance}m`}
              </th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.perf.id}
                className={highlight === row.perf.id ? "highlighted" : ""}
                onPointerEnter={() => onHighlight(row.perf.id)}
                onPointerLeave={() => onHighlight(null)}
              >
                <td className="right">{row.perf.place?.v ?? <span className="muted">{row.perf.status.toUpperCase()}</span>}</td>
                {hasLanes && <td className="right">{row.perf.lane?.v ?? <span className="muted">–</span>}</td>}
                <td>
                  <span className="athlete-cell">
                    <span className="swatch" style={{ background: row.color }} />
                    <Link to={`/athletes/${row.perf.athlete}`} className="link-plain">
                      {row.name}
                    </Link>
                    <span className="country">{row.perf.country?.v}</span>
                  </span>
                </td>
                {hasReactions && (
                  <td className="right muted" title={row.perf.reactionTime && row.perf.reactionTime.v < 0 ? "False start" : undefined}>
                    {row.perf.reactionTime ? row.perf.reactionTime.v.toFixed(3) : "–"}
                  </td>
                )}
                {points.map(({ index }, column) => (
                  <td key={index} className="right split-cell" {...pointAt(column)}>
                    {splitCell(row, index)}
                  </td>
                ))}
                <td className="right split-cell" {...pointAt(points.length)}>
                  {finishCell(row)}
                </td>
                <td>
                  <span className="row" style={{ "--gap": "4px" } as React.CSSProperties}>
                    {[...row.perf.records, ...row.perf.remarks].map((tag) => (
                      <span key={tag.s} className="tag">
                        {tag.v}
                      </span>
                    ))}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
