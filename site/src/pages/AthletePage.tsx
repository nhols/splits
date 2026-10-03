// One athlete: every race in the dataset, their segment times in each, and where they gain and
// lose time compared with elites who finished in the same time.

import { Suspense, useEffect, useMemo, useState } from "react";
import { LineChart, type Series } from "../components/charts/LineChart";
import { Legend } from "../components/charts/Legend";
import { Info, ModelExplainer } from "../components/Info";
import { Card, Loading } from "../components/ui";
import { gridsFor, onGrid, plan, segments, type Grid, type GridRow } from "../data/analysis";
import { athleteAt, athletePath, date, eventName, gap, roundName, time } from "../data/format";
import { useEvent, useIndex } from "../data/load";
import type { AthleteSummary, EventPerformance } from "../data/types";
import { Link, navigate } from "../router";
import { NotFound } from "./NotFound";
import "./pages.css";
import "./event.css";
import "./athlete.css";

export function AthletePage({ id }: { id: string }) {
  const index = useIndex();
  const athlete = athleteAt(index, id);
  if (!athlete) return <NotFound />;
  // The athlete's own address, with their number and current name.
  const path = athletePath(athlete);
  if (`/athletes/${id}` !== path) return <Redirect to={path} />;
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
          {athlete.worldAthleticsUrl && (
            <a href={athlete.worldAthleticsUrl} target="_blank" rel="noreferrer" className="pill-link">
              World Athletics profile
            </a>
          )}
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

function Redirect({ to }: { to: string }) {
  useEffect(() => navigate(to, { replace: true }), [to]);
  return null;
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
          finalOf={(perf) => races.get(perf.race)?.round === "final"}
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
  finalOf,
}: {
  athlete: AthleteSummary;
  mine: EventPerformance[];
  grid: Grid;
  distance: number;
  event: Parameters<typeof onGrid>[0];
  label: (perf: EventPerformance) => string;
  settingOf: (perf: EventPerformance) => string;
  finalOf: (perf: EventPerformance) => boolean;
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

  // Peers: other athletes' runs in the same setting (indoor and outdoor 400 m differ), and the
  // same kind of round when there are enough (heats are eased off at the end; finals are not).
  const peers = everyone.filter(
    (r) => r.perf.athlete !== athlete.id && settingOf(r.perf) === settingOf(chosen.perf),
  );
  const sameRound = peers.filter((r) => finalOf(r.perf) === finalOf(chosen.perf));
  const basis = sameRound.length >= 20 ? sameRound : peers;
  const typical = plan(basis, grid, distance, chosen.finish);
  const marks = chosen.times.map((t, i) => ({
    key: "",
    label: i < grid.points.length ? grid.points[i]!.label : "Finish",
    distance: i < grid.points.length ? grid.points[i]!.distance : distance,
    time: t,
  }));
  const actual = segments(marks);
  const runs = typical
    ? `${typical.runs.length} runs by other athletes in ${settingOf(chosen.perf)} ${basis === sameRound ? (finalOf(chosen.perf) ? "finals" : "heats") : "races"}`
    : "";

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
        title="Pacing against the field"
        subtitle="Where the time went, stretch by stretch"
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
            target={time(chosen.finish)}
            rows={actual.map((segment, i) => ({
              label: `${segment.fromLabel}–${segment.toLabel}`,
              toLabel: segment.toLabel,
              difference: segment.time - typical.points[i]!.segment,
              actual: segment.time,
              typical: typical.points[i]!.segment,
            }))}
            note={`Typical splits for ${time(chosen.finish)} modelled from ${runs}${typical.extrapolated ? ", extrapolated" : ""}.`}
          />
        ) : (
          <p className="secondary">Not enough comparable performances.</p>
        )}
      </Card>
    </div>
  );
}

/** Where the time went: each stretch's time against the typical time for the same finish. The
 * finishing times are equal, so the differences add up to zero: time lost on one stretch is
 * made up on others. */
function Diverging({
  target,
  rows,
  note,
}: {
  target: string;
  rows: { label: string; toLabel: string; difference: number; actual: number; typical: number }[];
  note: string;
}) {
  const extent = Math.max(0.15, ...rows.map((r) => Math.abs(r.difference)));
  return (
    <div className="stack" style={{ "--gap": "14px" } as React.CSSProperties}>
      <p className="diverging-summary">{summarise(rows, target)}</p>
      <div className="diverging">
        <div className="diverging-row diverging-head muted">
          <span />
          <span className="diverging-axis">
            <span>← Quicker</span>
            <span>Slower →</span>
          </span>
          <span className="diverging-num">Ran</span>
          <span className="diverging-num">Typical</span>
          <span className="diverging-num">Diff</span>
        </div>
        {rows.map((row) => {
          const width = (Math.abs(row.difference) / extent) * 50;
          const faster = row.difference < 0;
          return (
            <div key={row.label} className="diverging-row">
              <span className="diverging-label">{row.label}</span>
              <span className="diverging-track">
                <span className="diverging-mid" />
                <span
                  className={`diverging-bar ${faster ? "faster" : "slower"}`}
                  style={faster ? { right: "50%", width: `${width}%` } : { left: "50%", width: `${width}%` }}
                />
              </span>
              <span className="diverging-num num secondary">{time(row.actual)}</span>
              <span className="diverging-num num muted">{time(row.typical)}</span>
              <span className="diverging-num diverging-value num">{gap(row.difference)}</span>
            </div>
          );
        })}
      </div>
      <p className="muted" style={{ fontSize: 13 }}>
        {note}{" "}
        <Info label="How to read this chart">
          <strong>Pacing against the field</strong>
          <span>
            Each row is one stretch of the race, between timing points. The bar is the time this
            athlete took over it minus the time a typical runner finishing in the same time takes:
            to the left (blue) they were quicker there, to the right (red) slower.
          </span>
          <span>
            Because both finish in the same time, the differences add up to zero. The chart says
            nothing about whether the race was good, only how the time was spent: a red start and
            a blue finish means a more even race than usual, going out easier and closing
            stronger; the reverse, a harder start and a bigger fade.
          </span>
          <span>
            Differences of a few hundredths are within what timing and ordinary variation allow;
            look at the pattern across the race rather than any single stretch.
          </span>
          <ModelExplainer />
        </Info>
      </p>
    </div>
  );
}

/** One line on the shape of the race: how far behind or ahead of a typical run the athlete
 * got, and where. */
function summarise(rows: { toLabel: string; difference: number }[], target: string): string {
  let running = 0;
  let peak = { gap: 0, at: "" };
  for (const row of rows.slice(0, -1)) {
    running += row.difference;
    if (Math.abs(running) > Math.abs(peak.gap)) peak = { gap: running, at: row.toLabel };
  }
  if (Math.abs(peak.gap) < 0.05) return `Paced almost exactly like a typical ${target}.`;
  const by = Math.abs(peak.gap).toFixed(2);
  return peak.gap > 0
    ? `${by}s behind a typical ${target} at ${peak.at}, made up over the rest of the race.`
    : `${by}s ahead of a typical ${target} at ${peak.at}, given back over the rest of the race.`;
}
