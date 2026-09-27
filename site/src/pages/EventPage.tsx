// An event across every race: how elites distribute their effort, what splits a target time
// takes, and every performance. Filters at the top scope everything below them.

import { useMemo, useState } from "react";
import {
  gridsFor,
  onGrid,
  plan as makePlan,
  profile,
  summary,
  type Grid,
  type GridRow,
  type Measure,
} from "../data/analysis";
import { Legend } from "../components/charts/Legend";
import { ScatterChart } from "../components/charts/ScatterChart";
import { SinaChart, type SinaRun } from "../components/charts/SinaChart";
import { Info, ModelExplainer } from "../components/Info";
import { Card, Segmented, Select, Stat } from "../components/ui";
import { count, date, eventName, gap, roundGroup, roundName, speed, time } from "../data/format";
import { useEvent, useIndex } from "../data/load";
import type { EventData, EventPerformance, Index, RaceSummary } from "../data/types";
import { Link, navigate, useParam } from "../router";
import "./pages.css";
import "./event.css";

export function EventPage({ event: eventId }: { event: string }) {
  const index = useIndex();
  const event = useEvent(eventId);
  const [setting, setSetting] = useParam("setting");
  const [round, setRound] = useParam("round");
  const [competition, setCompetition] = useParam("competition");
  const races = useMemo(() => new Map(index.races.map((r) => [r.id, r])), [index]);
  const eventRaces = index.races.filter((r) => r.event === eventId);
  const settings = [...new Set(eventRaces.map((r) => r.setting))];
  const competitions = [...new Set(eventRaces.map((r) => r.competition))]
    .map((id) => index.competitions.find((c) => c.id === id)!)
    .sort((a, b) => b.startDate.localeCompare(a.startDate));

  const perfs = useMemo(
    () =>
      event.performances.filter((perf) => {
        const race = races.get(perf.race);
        if (!race) return false;
        if (setting && race.setting !== setting) return false;
        if (round && roundGroup(race.round) !== round) return false;
        if (competition && race.competition !== competition) return false;
        return true;
      }),
    [event, races, setting, round, competition],
  );
  const scopedRaces = eventRaces.filter(
    (r) =>
      (!setting || r.setting === setting) &&
      (!round || roundGroup(r.round) === round) &&
      (!competition || r.competition === competition),
  );
  const grids = useMemo(() => gridsFor(event, scopedRaces, perfs), [event, scopedRaces, perfs]);
  const [gridId, setGridId] = useParam("grid");
  const grid = grids.find((g) => g.id === gridId) ?? grids[0];
  const distance = index.disciplines.find((d) => d.id === event.discipline)?.distance ?? 0;
  const finishers = perfs.filter((p) => p.time !== null && p.status === "finished");
  const fastest = finishers.reduce<EventPerformance | null>(
    (best, p) => (!best || p.time! < best.time! ? p : best),
    null,
  );
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));

  return (
    <div className="page stack" style={{ "--gap": "24px" } as React.CSSProperties}>
      <header className="page-header">
        <nav className="breadcrumb">
          <Link to="/events">Events</Link>
        </nav>
        <h1>{eventName(index, eventId)}</h1>
      </header>

      <div className="filter-bar" role="group" aria-label="Filters">
        {settings.length > 1 && (
          <Segmented
            label="Setting"
            value={setting ?? ""}
            onChange={(v) => setSetting(v || null)}
            options={[
              { value: "", label: "Both" },
              ...settings.map((s) => ({ value: s, label: s === "indoor" ? "Indoor" : "Outdoor" })),
            ]}
          />
        )}
        <Segmented
          label="Round"
          value={round ?? ""}
          onChange={(v) => setRound(v || null)}
          options={[
            { value: "", label: "All rounds" },
            { value: "Heats", label: "Heats" },
            { value: "Semi-finals", label: "Semi-finals" },
            { value: "Finals", label: "Finals" },
          ]}
        />
        <Select
          label="Competition"
          value={competition ?? ""}
          onChange={(v) => setCompetition(v || null)}
          options={[
            { value: "", label: "All competitions" },
            ...competitions.map((c) => ({ value: c.id, label: c.name })),
          ]}
        />
      </div>

      <div className="kpis">
        <Stat label="Performances" value={count(perfs.length)} detail={`${count(finishers.length)} finished`} />
        <Stat
          label="Median finish"
          value={finishers.length ? time(summary(finishers.map((p) => p.time!)).median) : "–"}
        />
        <Stat
          label="Fastest"
          value={fastest ? time(fastest.time) : "–"}
          detail={fastest ? athletes.get(fastest.athlete)?.name : undefined}
        />
        <Stat label="With splits" value={grid ? count(grid.count) : "0"} detail={grid?.label} />
      </div>

      {grid && grids.length > 1 && (
        <div className="toolbar">
          <span className="toolbar-label">Timing points</span>
          <Segmented
            label="Timing points"
            value={grid.id}
            onChange={(v) => setGridId(v)}
            options={grids.map((g) => ({ value: g.id, label: `${g.label} (${g.count})` }))}
          />
        </div>
      )}

      {grid ? (
        <Analysis event={event} grid={grid} perfs={perfs} distance={distance} index={index} races={races} />
      ) : (
        <Card title="No splits">
          <p className="secondary">No race in this selection was timed at intermediate points.</p>
        </Card>
      )}

      <Card title="Every performance">
        <PerformanceTable event={event} grid={grid} perfs={perfs} races={races} index={index} />
      </Card>
    </div>
  );
}

interface AnalysisProps {
  event: EventData;
  grid: Grid;
  perfs: EventPerformance[];
  distance: number;
  index: Index;
  races: Map<string, RaceSummary>;
}

function Analysis({ event, grid, perfs, distance, index, races }: AnalysisProps) {
  const rows = useMemo(() => onGrid(event, grid, perfs), [event, grid, perfs]);
  return (
    <>
      <PaceProfile rows={rows} grid={grid} distance={distance} index={index} races={races} />
      <div className="grid-2 align-start">
        <Planner rows={rows} grid={grid} distance={distance} index={index} races={races} />
        <Distribution rows={rows} grid={grid} distance={distance} index={index} races={races} />
      </div>
    </>
  );
}

/** Each segment's time (or speed) for every run: the spread per segment, and any run through
 * the race when pointed at. */
function PaceProfile({ rows, grid, distance, index, races }: PanelProps) {
  const [measure, setMeasure] = useState<Measure>("time");
  const [showTable, setShowTable] = useState(false);
  const format = measure === "speed" ? (v: number) => v.toFixed(1) : (v: number) => v.toFixed(2);
  const edges = [0, ...grid.points.map((p) => p.distance), distance];
  const labels = ["0m", ...grid.points.map((p) => p.label), `${distance}m`];
  // "100–200m", "H1–H2": the unit once.
  const columns = labels.slice(1).map((label, i) => {
    const from = labels[i]!;
    return /^\d+m$/.test(from) && /^\d+m$/.test(label) ? `${from.slice(0, -1)}–${label}` : `${from === "0m" ? "Start" : from}–${label}`;
  });
  const athletes = useMemo(() => new Map(index.athletes.map((a) => [a.id, a.name])), [index]);
  const runs: SinaRun[] = useMemo(
    () =>
      rows.map((row) => {
        const race = races.get(row.perf.race);
        return {
          id: row.perf.id,
          values: edges.slice(1).map((to, i) => {
            const elapsed = row.times[i]! - (i > 0 ? row.times[i - 1]! : 0);
            return measure === "speed" ? (to - edges[i]!) / elapsed : elapsed;
          }),
          title: `${athletes.get(row.perf.athlete) ?? row.perf.athlete} · ${time(row.finish)}`,
          detail: race ? `${index.competitions.find((c) => c.id === race.competition)?.name ?? ""} · ${roundName(race.round, race.heat)}` : "",
        };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, measure, athletes, races, index],
  );
  const steps = profile(rows, grid, distance, measure);
  const spread = (i: number) => {
    const sorted = runs.map((r) => r.values[i]!).sort((a, b) => a - b);
    const at = (q: number) => sorted[Math.min(sorted.length - 1, Math.round((sorted.length - 1) * q))]!;
    return `${format(at(0.05))}–${format(at(0.95))}`;
  };
  return (
    <Card
      title={measure === "speed" ? "Segment speeds (m/s)" : "Segment times (s)"}
      actions={
        <>
          <Segmented
            label="Measure"
            value={measure}
            onChange={setMeasure}
            options={[
              { value: "time", label: "Segment times" },
              { value: "speed", label: "Speed" },
            ]}
          />
          <button type="button" className="button ghost" onClick={() => setShowTable(!showTable)}>
            {showTable ? "Show chart" : "Show table"}
          </button>
        </>
      }
    >
      {showTable ? (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Segment</th>
                <th className="right">Median</th>
                <th className="right">Middle half</th>
                <th className="right">5–95%</th>
                <th className="right">Runs</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((step, i) => (
                <tr key={step.label}>
                  <td>{columns[i]}</td>
                  <td className="right">
                    <strong>{format(step.median)}</strong>
                  </td>
                  <td className="right muted">
                    {format(step.q1)}–{format(step.q3)}
                  </td>
                  <td className="right muted">{spread(i)}</td>
                  <td className="right muted">{runs.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <SinaChart
          columns={columns}
          shortColumns={labels.slice(1)}
          runs={runs}
          format={format}
          yLabel={measure === "speed" ? "Metres per second" : "Seconds"}
        />
      )}
    </Card>
  );
}

interface PanelProps {
  rows: GridRow[];
  grid: Grid;
  distance: number;
  index: Index;
  races: Map<string, RaceSummary>;
}

function Planner({ rows, grid, distance, races }: PanelProps) {
  const finals = rows.filter((r) => races.get(r.perf.race)?.round === "final");
  const suggested = summary((finals.length >= 5 ? finals : rows).map((r) => r.finish)).median;
  const [input, setInput] = useState(() => (Number.isFinite(suggested) ? suggested.toFixed(2) : ""));
  const target = Number.parseFloat(input);
  const result = makePlan(rows, grid, distance, target);
  const lo = result?.runs[0]?.finish;
  const hi = result?.runs[result.runs.length - 1]?.finish;
  return (
    <Card
      title="Split planner"
    >
      <div className="stack" style={{ "--gap": "16px" } as React.CSSProperties}>
        <label className="planner-input">
          <span>Target time</span>
          <input
            className="text-input num"
            inputMode="decimal"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            aria-describedby="planner-note"
          />
          <span className="muted">seconds</span>
        </label>
        {result ? (
          <>
            <table className="data planner">
              <thead>
                <tr>
                  <th>Point</th>
                  <th className="right">Split</th>
                  <th className="right">Middle half</th>
                  <th className="right">Segment</th>
                  <th className="right muted">m/s</th>
                </tr>
              </thead>
              <tbody>
                {result.points.map((p) => (
                  <tr key={p.label}>
                    <td>{p.label}</td>
                    <td className="right">
                      <strong>{time(p.time)}</strong>
                    </td>
                    <td className="right muted">{p.label === "Finish" ? "" : `${time(p.low)}–${time(p.high)}`}</td>
                    <td className="right">{time(p.segment)}</td>
                    <td className="right muted">{speed(p.speed)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted" id="planner-note" style={{ fontSize: 13 }}>
              Modelled from {result.runs.length} runs ({time(lo)}–{time(hi)})
              {result.extrapolated ? ", extrapolated" : ""}.{" "}
              <Info label="How splits are modelled">
                <ModelExplainer />
              </Info>
            </p>
          </>
        ) : (
          <p className="secondary">Enter a time in seconds.</p>
        )}
      </div>
    </Card>
  );
}

function Distribution({ rows, grid, distance, index, races }: PanelProps) {
  const half = grid.points.findIndex((p) => Math.abs(p.distance - distance / 2) < 1e-6);
  const [athlete] = useParam("athlete");
  const group = (row: GridRow) => roundGroup(races.get(row.perf.race)?.round ?? "");
  if (half < 0) {
    const first = grid.points[0]!;
    const dots = rows.map((row) => ({ id: row.perf.id, x: row.finish, y: row.times[0]!, group: group(row) }));
    return (
      <Card title={`${first.label} against finish`}>
        <DotChart dots={dots} rows={rows} races={races} index={index} xLabel="Finishing time (s)" yLabel={`${first.label} split (s)`} highlight={athlete} />
      </Card>
    );
  }
  const dots = rows.map((row) => ({ id: row.perf.id, x: row.finish, y: row.finish - 2 * row.times[half]!, group: group(row) }));
  const differential = summary(dots.map((d) => d.y));
  return (
    <Card
      title="Second half against first"
      subtitle={`Median ${gap(differential.median)} s`}
    >
      <DotChart
        dots={dots}
        rows={rows}
        races={races}
        index={index}
        xLabel="Finishing time (s)"
        yLabel="Second half − first half (s)"
        reference={{ y: 0, label: "Even pace" }}
        highlight={athlete}
      />
    </Card>
  );
}

function DotChart({
  dots,
  rows,
  races,
  index,
  xLabel,
  yLabel,
  reference,
  highlight,
}: {
  dots: { id: string; x: number; y: number; group: string }[];
  rows: GridRow[];
  races: Map<string, RaceSummary>;
  index: Index;
  xLabel: string;
  yLabel: string;
  reference?: { y: number; label: string };
  highlight: string | null;
}) {
  const groups = [
    { id: "Heats", label: "Heats", color: "var(--series-1)" },
    { id: "Semi-finals", label: "Semi-finals", color: "var(--series-2)" },
    { id: "Finals", label: "Finals", color: "var(--series-3)" },
  ].filter((g) => dots.some((d) => d.group === g.id));
  const byId = new Map(rows.map((r) => [r.perf.id, r]));
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const highlighted = new Set(highlight ? rows.filter((r) => r.perf.athlete === highlight).map((r) => r.perf.id) : []);
  return (
    <div className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
      <Legend items={groups} shape="dot" />
      <ScatterChart
        dots={dots}
        groups={groups}
        xLabel={xLabel}
        yLabel={yLabel}
        xFormat={(v) => v.toFixed(1)}
        yFormat={(v) => v.toFixed(1)}
        reference={reference}
        highlight={highlighted}
        onSelect={(dot) => navigate(`/races/${byId.get(dot.id)?.perf.race}`)}
        tooltip={(dot) => {
          const row = byId.get(dot.id)!;
          const race = races.get(row.perf.race);
          const competition = index.competitions.find((c) => c.id === race?.competition);
          return (
            <>
              <div className="chart-tooltip-title">{athletes.get(row.perf.athlete)?.name}</div>
              <div className="chart-tooltip-row">
                <span />
                <span className="chart-tooltip-value num">{dot.y.toFixed(2)}</span>
                <span className="chart-tooltip-label">{yLabel.replace(/ \(s\)$/, "")}</span>
              </div>
              <div className="chart-tooltip-row">
                <span />
                <span className="chart-tooltip-value num">{time(row.finish)}</span>
                <span className="chart-tooltip-label">finish</span>
              </div>
              <div className="muted" style={{ marginTop: 6 }}>
                {competition?.name}, {race && roundName(race.round, race.heat)}
              </div>
            </>
          );
        }}
      />
    </div>
  );
}

function PerformanceTable({
  event,
  grid,
  perfs,
  races,
  index,
}: {
  event: EventData;
  grid: Grid | undefined;
  perfs: EventPerformance[];
  races: Map<string, RaceSummary>;
  index: Index;
}) {
  const [sort, setSort] = useState<{ key: string; ascending: boolean }>({ key: "finish", ascending: true });
  const [limit, setLimit] = useState(60);
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const competitions = new Map(index.competitions.map((c) => [c.id, c]));
  const points = grid?.points ?? [];
  const pointIndex = new Map(event.points.map((p, i) => [p.key, i]));
  const value = (perf: EventPerformance, key: string): number | string | null => {
    if (key === "finish") return perf.time;
    if (key === "date") return races.get(perf.race)?.date ?? "";
    const i = pointIndex.get(key);
    return i === undefined ? null : (perf.splits[i] ?? null);
  };
  const sorted = [...perfs].sort((a, b) => {
    const va = value(a, sort.key);
    const vb = value(b, sort.key);
    if (va === null) return 1;
    if (vb === null) return -1;
    const order = va < vb ? -1 : va > vb ? 1 : 0;
    return sort.ascending ? order : -order;
  });
  const header = (key: string, label: string, right = true) => (
    <th
      key={key}
      className={`sortable${right ? " right" : ""}`}
      onClick={() => setSort({ key, ascending: sort.key === key ? !sort.ascending : key !== "date" })}
      aria-sort={sort.key === key ? (sort.ascending ? "ascending" : "descending") : undefined}
    >
      {label}
      {sort.key === key ? (sort.ascending ? " ↑" : " ↓") : ""}
    </th>
  );
  return (
    <div className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Athlete</th>
              <th>Race</th>
              {header("date", "Date", false)}
              {points.map((p) => header(p.key, p.label))}
              {header("finish", "Result")}
            </tr>
          </thead>
          <tbody>
            {sorted.slice(0, limit).map((perf) => {
              const race = races.get(perf.race);
              const athlete = athletes.get(perf.athlete);
              return (
                <tr key={perf.id} className="clickable" onClick={() => navigate(`/races/${perf.race}`)}>
                  <td>
                    <Link to={`/athletes/${perf.athlete}`} className="link-plain" onClick={(e) => e.stopPropagation()}>
                      {athlete?.name}
                    </Link>{" "}
                    <span className="country">{athlete?.country}</span>
                  </td>
                  <td className="secondary">
                    {competitions.get(race?.competition ?? "")?.name.replace(/^World Athletics /, "")} ·{" "}
                    {race && roundName(race.round, race.heat)}
                  </td>
                  <td className="secondary">{race && date(race.date)}</td>
                  {points.map((p) => {
                    const i = pointIndex.get(p.key)!;
                    const v = perf.splits[i];
                    const suspect = perf.suspect.includes(i);
                    return (
                      <td key={p.key} className={`right${suspect ? " suspect-cell" : ""}`} title={suspect ? "Flagged as suspect" : undefined}>
                        {v === null || v === undefined ? <span className="muted">–</span> : time(v)}
                      </td>
                    );
                  })}
                  <td className="right">
                    <strong>{perf.time !== null ? time(perf.time) : perf.status.toUpperCase()}</strong>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {sorted.length > limit && (
        <button type="button" className="button" style={{ alignSelf: "flex-start" }} onClick={() => setLimit(limit + 200)}>
          Show more ({count(sorted.length - limit)} left)
        </button>
      )}
    </div>
  );
}
