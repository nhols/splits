// One athlete: every race in the dataset, their segment times in each, and where they gain and
// lose time compared with elites who finished in the same time.

import { Suspense, useMemo, useState } from "react";
import { LineChart, type Series } from "../components/charts/LineChart";
import { Legend } from "../components/charts/Legend";
import { Card, Loading } from "../components/ui";
import { gridsFor, onGrid, plan, segments, type Grid, type GridRow } from "../data/analysis";
import { date, eventName, gap, roundName, time } from "../data/format";
import { useEvent, useIndex } from "../data/load";
import type { AthleteSummary, EventPerformance } from "../data/types";
import { Link, navigate } from "../router";
import { NotFound } from "./NotFound";
import "./pages.css";
import "./event.css";
import "./athlete.css";

export function AthletePage({ id }: { id: string }) {
  const index = useIndex();
  const athlete = index.athletes.find((a) => a.id === id);
  if (!athlete) return <NotFound />;
  const born = athlete.birthDate;
  return (
    <div className="page stack" style={{ "--gap": "24px" } as React.CSSProperties}>
      <header className="page-header">
        <nav className="breadcrumb">
          <Link to="/athletes">Athletes</Link>
        </nav>
        <h1>{athlete.name}</h1>
        <div className="row meta-row">
          <span className="country" style={{ fontSize: 14 }}>
            {athlete.country}
          </span>
          {born && <span>Born {born.length === 10 ? date(born) : born}</span>}
          <span>
            {athlete.races} race{athlete.races === 1 ? "" : "s"}
          </span>
        </div>
        {Object.keys(athlete.bests).length > 0 && (
          <div className="bests">
            {Object.entries(athlete.bests).map(([event, best]) => (
              <div key={event} className="best">
                <div className="muted">{eventName(index, event)}</div>
                <div className="best-value num">{time(best)}</div>
              </div>
            ))}
          </div>
        )}
      </header>
      {athlete.events.map((event) => (
        <Suspense key={event} fallback={<Loading />}>
          <AthleteEvent athlete={athlete} event={event} />
        </Suspense>
      ))}
    </div>
  );
}

function AthleteEvent({ athlete, event: eventId }: { athlete: AthleteSummary; event: string }) {
  const index = useIndex();
  const event = useEvent(eventId);
  const races = useMemo(() => new Map(index.races.map((r) => [r.id, r])), [index]);
  const competitions = new Map(index.competitions.map((c) => [c.id, c]));
  const mine = event.performances
    .filter((p) => p.athlete === athlete.id)
    .sort((a, b) => (races.get(a.race)?.date ?? "").localeCompare(races.get(b.race)?.date ?? ""));
  const grid = gridsFor(event, index.races.filter((r) => r.event === eventId), event.performances)[0];
  const distance = index.disciplines.find((d) => d.id === event.discipline)?.distance ?? 0;
  const raceLabel = (perf: EventPerformance) => {
    const race = races.get(perf.race);
    const competition = competitions.get(race?.competition ?? "");
    return `${competition?.name.replace(/^World Athletics /, "") ?? ""} · ${race ? roundName(race.round, race.heat) : ""}`;
  };

  return (
    <section className="stack" style={{ "--gap": "20px" } as React.CSSProperties}>
      <h2 className="event-heading">{eventName(index, eventId)}</h2>
      {grid && (
        <Profiles
          athlete={athlete}
          mine={mine}
          grid={grid}
          distance={distance}
          event={event}
          label={raceLabel}
          settingOf={(perf) => races.get(perf.race)?.setting ?? ""}
        />
      )}
      <Card title="Races">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Date</th>
                <th>Race</th>
                <th className="right">Place</th>
                {event.points.map((p, i) =>
                  mine.some((perf) => perf.splits[i] !== null) ? (
                    <th key={p.key} className="right">
                      {p.label}
                    </th>
                  ) : null,
                )}
                <th className="right">Result</th>
              </tr>
            </thead>
            <tbody>
              {mine.map((perf) => (
                <tr key={perf.id} className="clickable" onClick={() => navigate(`/races/${perf.race}`)}>
                  <td className="secondary">{date(races.get(perf.race)?.date ?? "")}</td>
                  <td>{raceLabel(perf)}</td>
                  <td className="right">{perf.place ?? <span className="muted">–</span>}</td>
                  {event.points.map((p, i) =>
                    mine.some((other) => other.splits[i] !== null) ? (
                      <td key={p.key} className={`right${perf.suspect.includes(i) ? " suspect-cell" : ""}`}>
                        {perf.splits[i] !== null ? time(perf.splits[i]) : <span className="muted">–</span>}
                      </td>
                    ) : null,
                  )}
                  <td className="right">
                    <strong>{perf.time !== null ? time(perf.time) : perf.status.toUpperCase()}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </section>
  );
}

function Profiles({
  athlete,
  mine,
  grid,
  distance,
  event,
  label,
  settingOf,
}: {
  athlete: AthleteSummary;
  mine: EventPerformance[];
  grid: Grid;
  distance: number;
  event: Parameters<typeof onGrid>[0];
  label: (perf: EventPerformance) => string;
  settingOf: (perf: EventPerformance) => string;
}) {
  const rows = onGrid(event, grid, mine);
  const everyone = useMemo(() => onGrid(event, grid, event.performances), [event, grid]);
  const best = rows.reduce<GridRow | null>((b, r) => (!b || r.finish < b.finish ? r : b), null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  if (!rows.length || !best) return null;
  const chosen = rows.find((r) => r.perf.id === selected) ?? best;

  const series: Series[] = rows.map((row) => {
    const marks = row.times.map((t, i) => ({
      key: "",
      label: "",
      distance: i < grid.points.length ? grid.points[i]!.distance : distance,
      time: t,
    }));
    return {
      id: row.perf.id,
      label: `${label(row.perf)} · ${time(row.finish)}`,
      endLabel: time(row.finish),
      color: row === best ? "var(--series-1)" : "var(--series-other)",
      data: segments(marks).map((s) => ({ x: (s.from + s.to) / 2, x0: s.from, x1: s.to, y: s.time })),
    };
  });
  const ordered = [...series.filter((s) => s.id !== best.perf.id), ...series.filter((s) => s.id === best.perf.id)];
  const ticks = [...grid.points.map((p) => ({ value: p.distance, label: p.label })), { value: distance, label: `${distance}m` }];

  // Peers: other athletes' runs in the same setting (indoor and outdoor 400 m differ).
  const peers = everyone.filter(
    (r) => r.perf.athlete !== athlete.id && settingOf(r.perf) === settingOf(chosen.perf),
  );
  const typical = plan(peers, grid, distance, chosen.finish);
  const marks = chosen.times.map((t, i) => ({
    key: "",
    label: i < grid.points.length ? grid.points[i]!.label : "Finish",
    distance: i < grid.points.length ? grid.points[i]!.distance : distance,
    time: t,
  }));
  const actual = segments(marks);

  return (
    <div className="grid-2 align-start">
      <Card title="Segment times">
        <div className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
          {rows.length > 1 && (
            <Legend
              items={[
                { id: best.perf.id, label: `Fastest: ${label(best.perf)}`, color: "var(--series-1)" },
                { id: "others", label: "Other races", color: "var(--series-other)" },
              ]}
            />
          )}
          <LineChart
            series={ordered}
            steps
            xDomain={[0, distance]}
            xTicks={ticks}
            yFormat={(v) => v.toFixed(1)}
            yLabel="Seconds"
            endLabels={false}
            highlight={highlight}
            onHighlight={setHighlight}
            height={300}
            tooltipTitle={(x) => {
              const segment = ordered[0]?.data.find((d) => d.x === x);
              return segment ? `${segment.x0}–${segment.x1} m` : `${x} m`;
            }}
            tooltipValue={(_, d) => `${time(d.y)} s`}
          />
        </div>
      </Card>
      <Card
        title="Against the field"
        subtitle={`Against others who ran ${time(chosen.finish)}`}
        actions={
          rows.length > 1 ? (
            <select className="text-input" value={chosen.perf.id} onChange={(e) => setSelected(e.target.value)} aria-label="Race">
              {rows.map((r) => (
                <option key={r.perf.id} value={r.perf.id}>
                  {label(r.perf)} · {time(r.finish)}
                </option>
              ))}
            </select>
          ) : undefined
        }
      >
        {typical ? (
          <Diverging
            rows={actual.map((segment, i) => ({
              label: `${segment.fromLabel}–${segment.toLabel}`,
              difference: segment.time - typical.points[i]!.segment,
              actual: segment.time,
              typical: typical.points[i]!.segment,
            }))}
            note={`Compared with typical splits for ${time(chosen.finish)}, modelled from ${typical.runs.length} ${settingOf(chosen.perf)} runs.`}
          />
        ) : (
          <p className="secondary">Not enough comparable performances.</p>
        )}
      </Card>
    </div>
  );
}

/** Time gained (blue, left) or lost (red, right) per segment against a typical run. */
function Diverging({
  rows,
  note,
}: {
  rows: { label: string; difference: number; actual: number; typical: number }[];
  note: string;
}) {
  const extent = Math.max(0.15, ...rows.map((r) => Math.abs(r.difference)));
  return (
    <div className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
      <div className="diverging">
        <div className="diverging-axis muted">
          <span>Faster than typical</span>
          <span>Slower</span>
        </div>
        {rows.map((row) => {
          const width = (Math.abs(row.difference) / extent) * 50;
          const faster = row.difference < 0;
          return (
            <div key={row.label} className="diverging-row" title={`${time(row.actual)} against a typical ${time(row.typical)}`}>
              <span className="diverging-label">{row.label}</span>
              <span className="diverging-track">
                <span className="diverging-mid" />
                <span
                  className={`diverging-bar ${faster ? "faster" : "slower"}`}
                  style={faster ? { right: "50%", width: `${width}%` } : { left: "50%", width: `${width}%` }}
                />
              </span>
              <span className={`diverging-value num ${faster ? "faster" : "slower"}`}>{gap(row.difference)}</span>
            </div>
          );
        })}
      </div>
      <p className="muted" style={{ fontSize: 13 }}>
        {note}
      </p>
    </div>
  );
}
