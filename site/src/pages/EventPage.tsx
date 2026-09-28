// An event across every race: how elites distribute their effort, what splits a target time
// takes, and every performance. Filters at the top scope everything below them.

import { useEffect, useMemo, useState } from "react";
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
import { SinaChart, type SinaGroup, type SinaRun } from "../components/charts/SinaChart";
import { Info, ModelExplainer } from "../components/Info";
import { Card, Segmented, Select, Stat } from "../components/ui";
import { count, date, eventGroup, eventName, eventPath, gap, groupName, roundGroup, roundName, speed, time } from "../data/format";
import { useEvent, useIndex } from "../data/load";
import type { EventData, EventPerformance, Index, RaceSummary } from "../data/types";
import { Link, navigate, useParam } from "../router";
import { NotFound } from "./NotFound";
import "./pages.css";
import "./event.css";

export function EventPage({ event: key }: { event: string }) {
  const index = useIndex();
  // The old address of one sex's event: its discipline's page, filtered to that sex.
  const legacy = index.events.some((e) => e.id === key);
  useEffect(() => {
    if (legacy) navigate(eventPath(key), { replace: true });
  }, [legacy, key]);
  if (legacy) return null;
  const events = index.events
    .filter((e) => eventGroup(e.discipline) === key)
    .sort((a, b) => SEXES.indexOf(a.sex) - SEXES.indexOf(b.sex));
  if (events.length === 0) return <NotFound />;
  return <GroupPage group={key} events={events.map((e) => e.id)} />;
}

const SEXES = ["men", "women"];

/** Men in blue, women in pink, wherever the two are drawn together. */
const SEX_GROUPS: SinaGroup[] = [
  { id: "men", label: "Men", color: "var(--men)" },
  { id: "women", label: "Women", color: "var(--women)" },
];

const sexGroup = (sex: string) => SEX_GROUPS.find((g) => g.id === sex) ?? SEX_GROUPS[0]!;

/** One sex's share of the page: its event, its performances in the filters, and, on the timing
 * points chosen, its runs. */
interface Side {
  sex: string;
  event: EventData;
  perfs: EventPerformance[];
  grids: Grid[];
  distance: number;
}

interface Shown extends Side {
  grid: Grid;
  rows: GridRow[];
}

function GroupPage({ group, events: eventIds }: { group: string; events: string[] }) {
  const index = useIndex();
  // The page's events never change (it is keyed by its address), so neither does this.
  const all = eventIds.map((id) => useEvent(id));
  const [sexParam, setSex] = useParam("sex");
  const sex = all.some((e) => e.sex === sexParam) ? sexParam : null;
  const events = all.filter((e) => !sex || e.sex === sex);
  const [setting, setSetting] = useParam("setting");
  const [round, setRound] = useParam("round");
  const [competition, setCompetition] = useParam("competition");
  const races = useMemo(() => new Map(index.races.map((r) => [r.id, r])), [index]);
  const eventRaces = index.races.filter((r) => events.some((e) => e.event === r.event));
  const settings = [...new Set(eventRaces.map((r) => r.setting))];
  const competitions = [...new Set(eventRaces.map((r) => r.competition))]
    .map((id) => index.competitions.find((c) => c.id === id)!)
    .sort((a, b) => b.startDate.localeCompare(a.startDate));

  const sides: Side[] = useMemo(
    () =>
      events.map((event) => {
        const inScope = (race: RaceSummary) =>
          (!setting || race.setting === setting) &&
          (!round || roundGroup(race.round) === round) &&
          (!competition || race.competition === competition);
        const perfs = event.performances.filter((perf) => {
          const race = races.get(perf.race);
          return race !== undefined && inScope(race);
        });
        const scoped = index.races.filter((r) => r.event === event.event && inScope(r));
        return {
          sex: event.sex,
          event,
          perfs,
          grids: gridsFor(event, scoped, perfs),
          distance: index.disciplines.find((d) => d.id === event.discipline)?.distance ?? 0,
        };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sex, index, races, setting, round, competition],
  );
  // The timing points either sex's races were timed at, those both share (by the same points)
  // as one, most widely available first.
  const grids = useMemo(() => {
    const merged = new Map<string, Grid>();
    for (const side of sides) {
      for (const grid of side.grids) {
        const seen = merged.get(grid.id);
        merged.set(grid.id, seen ? { ...seen, count: seen.count + grid.count } : grid);
      }
    }
    return [...merged.values()].sort((a, b) => b.count - a.count || b.points.length - a.points.length);
  }, [sides]);
  const [gridId, setGridId] = useParam("grid");
  const grid = grids.find((g) => g.id === gridId) ?? grids[0];
  const shown: Shown[] = sides.flatMap((side) => {
    const own = grid && side.grids.find((g) => g.id === grid.id);
    return own ? [{ ...side, grid: own, rows: onGrid(side.event, own, side.perfs) }] : [];
  });
  const perfs = sides.flatMap((side) => side.perfs.map((perf) => ({ perf, event: side.event })));
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const finished = (side: Side) => side.perfs.filter((p) => p.time !== null && p.status === "finished");
  const fastestOf = (side: Side) =>
    finished(side).reduce<EventPerformance | null>((best, p) => (!best || p.time! < best.time! ? p : best), null);
  const finishers = sides.flatMap(finished);

  return (
    <div className="page stack" style={{ "--gap": "24px" } as React.CSSProperties}>
      <header className="page-header">
        <nav className="breadcrumb">
          <Link to="/events">Events</Link>
        </nav>
        <h1>{sex ? eventName(index, events[0]!.event) : groupName(index, group)}</h1>
      </header>

      <div className="filter-bar" role="group" aria-label="Filters">
        {all.length > 1 && (
          <Segmented
            label="Men or women"
            value={sex ?? ""}
            onChange={(v) => setSex(v || null)}
            options={[
              { value: "", label: "Both" },
              ...all.map((e) => ({
                value: e.sex,
                label: (
                  <span className="sex-option">
                    <span className="legend-swatch-dot" style={{ background: sexGroup(e.sex).color }} />
                    {sexGroup(e.sex).label}
                  </span>
                ),
              })),
            ]}
          />
        )}
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
        {sides.length > 1 ? (
          // A median across men and women means nothing: each sex's fastest instead.
          sides.map((side) => {
            const fastest = fastestOf(side);
            return (
              <Stat
                key={side.sex}
                label={`Fastest, ${sexGroup(side.sex).label.toLowerCase()}`}
                value={fastest ? time(fastest.time) : "–"}
                detail={fastest ? athletes.get(fastest.athlete)?.name : undefined}
              />
            );
          })
        ) : (
          <>
            <Stat
              label="Median finish"
              value={finishers.length ? time(summary(finishers.map((p) => p.time!)).median) : "–"}
            />
            <Stat
              label="Fastest"
              value={sides[0] && fastestOf(sides[0]) ? time(fastestOf(sides[0])!.time) : "–"}
              detail={sides[0] && fastestOf(sides[0]) ? athletes.get(fastestOf(sides[0])!.athlete)?.name : undefined}
            />
          </>
        )}
        <Stat
          label="With splits"
          value={count(shown.reduce((n, side) => n + side.rows.length, 0))}
          detail={grid?.label}
        />
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

      {shown.length ? (
        <Analysis sides={shown} index={index} races={races} />
      ) : (
        <Card title="No splits">
          <p className="secondary">No race in this selection was timed at intermediate points.</p>
        </Card>
      )}

      <Card title="Every performance">
        <PerformanceTable perfs={perfs} grid={grid} both={sides.length > 1} races={races} index={index} />
      </Card>
    </div>
  );
}

interface AnalysisProps {
  sides: Shown[];
  index: Index;
  races: Map<string, RaceSummary>;
}

function Analysis({ sides, index, races }: AnalysisProps) {
  return (
    <>
      <PaceProfile sides={sides} index={index} races={races} />
      <div className="grid-2 align-start">
        <PlannerCard sides={sides} races={races} />
        <Distribution sides={sides} index={index} races={races} />
      </div>
    </>
  );
}

/** Each segment's time (or speed) for every run: the spread per segment, and any run through
 * the race when pointed at. Men and women share each violin, a half each. */
function PaceProfile({ sides, index, races }: AnalysisProps) {
  const [measure, setMeasure] = useState<Measure>("time");
  const [showTable, setShowTable] = useState(false);
  const format = measure === "speed" ? (v: number) => v.toFixed(1) : measure === "cumulative" ? (v: number) => time(v) : (v: number) => v.toFixed(2);
  const { grid, distance } = sides[0]!;
  // The sprint hurdles finish at 110 m for men and 100 m for women: then just "Finish".
  const finish = sides.every((side) => side.distance === distance) ? `${distance}m` : "Finish";
  const labels = ["0m", ...grid.points.map((p) => p.label), finish];
  // "100–200m", "H1–H2": the unit once.
  const columns = labels.slice(1).map((label, i) => {
    const from = labels[i]!;
    return /^\d+m$/.test(from) && /^\d+m$/.test(label) ? `${from.slice(0, -1)}–${label}` : `${from === "0m" ? "Start" : from}–${label}`;
  });
  const athletes = useMemo(() => new Map(index.athletes.map((a) => [a.id, a.name])), [index]);
  const runs: SinaRun[] = useMemo(
    () =>
      sides.flatMap((side) => {
        const edges = [0, ...side.grid.points.map((p) => p.distance), side.distance];
        return side.rows.map((row) => {
          const race = races.get(row.perf.race);
          return {
            id: row.perf.id,
            group: side.sex,
            values: edges.slice(1).map((to, i) => {
              if (measure === "cumulative") return row.times[i]!;
              const elapsed = row.times[i]! - (i > 0 ? row.times[i - 1]! : 0);
              return measure === "speed" ? (to - edges[i]!) / elapsed : elapsed;
            }),
            title: `${athletes.get(row.perf.athlete) ?? row.perf.athlete} · ${time(row.finish)}`,
            detail: race ? `${index.competitions.find((c) => c.id === race.competition)?.name ?? ""} · ${roundName(race.round, race.heat)}` : "",
          };
        });
      }),
    [sides, measure, athletes, races, index],
  );
  const spread = (sex: string, i: number) => {
    const sorted = runs.filter((r) => r.group === sex).map((r) => r.values[i]!).sort((a, b) => a - b);
    const at = (q: number) => sorted[Math.min(sorted.length - 1, Math.round((sorted.length - 1) * q))]!;
    return `${format(at(0.05))}–${format(at(0.95))}`;
  };
  const both = sides.length > 1;
  return (
    <Card
      title={measure === "speed" ? "Segment speeds (m/s)" : measure === "cumulative" ? "Cumulative times (s)" : "Segment times (s)"}
      actions={
        <>
          <Segmented
            label="Measure"
            value={measure}
            onChange={setMeasure}
            options={[
              { value: "time", label: "Segment times" },
              { value: "cumulative", label: "Cumulative" },
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
                <th>{measure === "cumulative" ? "Point" : "Segment"}</th>
                {both && <th />}
                <th className="right">Median</th>
                <th className="right">Middle half</th>
                <th className="right">5–95%</th>
                <th className="right">Runs</th>
              </tr>
            </thead>
            <tbody>
              {columns.flatMap((column, i) =>
                sides.map((side, k) => {
                  const step = profile(side.rows, side.grid, side.distance, measure)[i]!;
                  return (
                    <tr
                      key={`${column}/${side.sex}`}
                      className={both ? "sex-row" : undefined}
                      style={both ? ({ "--row-tint": sexGroup(side.sex).color } as React.CSSProperties) : undefined}
                    >
                      <td>{k === 0 ? (measure === "cumulative" ? labels[i + 1] : column) : ""}</td>
                      {both && (
                        <td>
                          <SexKey sex={side.sex} />
                        </td>
                      )}
                      <td className="right">
                        <strong>{format(step.median)}</strong>
                      </td>
                      <td className="right muted">
                        {format(step.q1)}–{format(step.q3)}
                      </td>
                      <td className="right muted">{spread(side.sex, i)}</td>
                      <td className="right muted">{side.rows.length}</td>
                    </tr>
                  );
                }),
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="stack" style={{ "--gap": "8px" } as React.CSSProperties}>
          {both && <Legend items={sides.map((side) => sexGroup(side.sex))} shape="dot" />}
          <SinaChart
            columns={measure === "cumulative" ? labels.slice(1) : columns}
            shortColumns={labels.slice(1)}
            runs={runs}
            groups={sides.map((side) => sexGroup(side.sex))}
            format={format}
            yLabel={measure === "speed" ? "Metres per second" : "Seconds"}
            independent={measure === "cumulative"}
          />
        </div>
      )}
    </Card>
  );
}

function SexKey({ sex }: { sex: string }) {
  const group = sexGroup(sex);
  return (
    <span className="sex-option">
      <span className="legend-swatch-dot" style={{ background: group.color }} />
      {group.label}
    </span>
  );
}

/** The planner models one sex at a time: with both shown, the reader picks which. */
function PlannerCard({ sides, races }: { sides: Shown[]; races: Map<string, RaceSummary> }) {
  const [sex, setSex] = useState(sides[0]!.sex);
  const side = sides.find((s) => s.sex === sex) ?? sides[0]!;
  const picker =
    sides.length > 1 ? (
      <Segmented
        label="Men or women"
        value={side.sex}
        onChange={setSex}
        options={sides.map((s) => ({ value: s.sex, label: sexGroup(s.sex).label }))}
      />
    ) : undefined;
  return <Planner key={`${side.sex}/${side.grid.id}`} side={side} races={races} actions={picker} />;
}

function Planner({ side, races, actions }: { side: Shown; races: Map<string, RaceSummary>; actions?: React.ReactNode }) {
  const { rows, grid, distance } = side;
  const finals = rows.filter((r) => races.get(r.perf.race)?.round === "final");
  const suggested = summary((finals.length >= 5 ? finals : rows).map((r) => r.finish)).median;
  const [input, setInput] = useState(() => (Number.isFinite(suggested) ? suggested.toFixed(2) : ""));
  const target = Number.parseFloat(input);
  const result = makePlan(rows, grid, distance, target);
  const lo = result?.runs[0]?.finish;
  const hi = result?.runs[result.runs.length - 1]?.finish;
  return (
    <Card title="Split planner" actions={actions}>
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

/** Second half against first (or the first split against the finish, without a halfway
 * point): by sex with both shown, else by round. */
function Distribution({ sides, index, races }: AnalysisProps) {
  const halfOf = (side: Shown) => side.grid.points.findIndex((p) => Math.abs(p.distance - side.distance / 2) < 1e-6);
  const [athlete] = useParam("athlete");
  const both = sides.length > 1;
  const group = (side: Shown, row: GridRow) => (both ? side.sex : roundGroup(races.get(row.perf.race)?.round ?? ""));
  const groups = both
    ? sides.map((side) => sexGroup(side.sex))
    : [
        { id: "Heats", label: "Heats", color: "var(--series-1)" },
        { id: "Semi-finals", label: "Semi-finals", color: "var(--series-2)" },
        { id: "Finals", label: "Finals", color: "var(--series-3)" },
      ];
  const rows = sides.flatMap((side) => side.rows);
  if (!sides.every((side) => halfOf(side) >= 0)) {
    const first = sides[0]!.grid.points[0]!;
    const dots = sides.flatMap((side) =>
      side.rows.map((row) => ({ id: row.perf.id, x: row.finish, y: row.times[0]!, group: group(side, row) })),
    );
    return (
      <Card title={`${first.label} against finish`}>
        <DotChart dots={dots} groups={groups} rows={rows} races={races} index={index} xLabel="Finishing time (s)" yLabel={`${first.label} split (s)`} highlight={athlete} />
      </Card>
    );
  }
  const dots = sides.flatMap((side) =>
    side.rows.map((row) => ({ id: row.perf.id, x: row.finish, y: row.finish - 2 * row.times[halfOf(side)]!, group: group(side, row) })),
  );
  const median = (sex: string) => gap(summary(dots.filter((d) => d.group === sex).map((d) => d.y)).median);
  const subtitle = both
    ? `Median ${sides.map((side) => `${sexGroup(side.sex).label.toLowerCase()} ${median(side.sex)} s`).join(", ")}`
    : `Median ${gap(summary(dots.map((d) => d.y)).median)} s`;
  return (
    <Card title="Second half against first" subtitle={subtitle}>
      <DotChart
        dots={dots}
        groups={groups}
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
  groups: all,
  rows,
  races,
  index,
  xLabel,
  yLabel,
  reference,
  highlight,
}: {
  dots: { id: string; x: number; y: number; group: string }[];
  groups: { id: string; label: string; color: string }[];
  rows: GridRow[];
  races: Map<string, RaceSummary>;
  index: Index;
  xLabel: string;
  yLabel: string;
  reference?: { y: number; label: string };
  highlight: string | null;
}) {
  const groups = all.filter((g) => dots.some((d) => d.group === g.id));
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
  perfs,
  grid,
  both,
  races,
  index,
}: {
  perfs: { perf: EventPerformance; event: EventData }[];
  grid: Grid | undefined;
  /** Whether men and women are both listed, so each row says which. */
  both: boolean;
  races: Map<string, RaceSummary>;
  index: Index;
}) {
  const [sort, setSort] = useState<{ key: string; ascending: boolean }>({ key: "finish", ascending: true });
  const [limit, setLimit] = useState(60);
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const competitions = new Map(index.competitions.map((c) => [c.id, c]));
  const points = grid?.points ?? [];
  // Where each point is in each event's splits (the sexes' hurdles are timed apart).
  const pointIndexes = new Map(perfs.map(({ event }) => [event.event, new Map(event.points.map((p, i) => [p.key, i]))]));
  const split = ({ perf, event }: { perf: EventPerformance; event: EventData }, key: string) => {
    const i = pointIndexes.get(event.event)?.get(key);
    return i === undefined ? { i, v: null } : { i, v: perf.splits[i] ?? null };
  };
  const value = (entry: { perf: EventPerformance; event: EventData }, key: string): number | string | null => {
    if (key === "finish") return entry.perf.time;
    if (key === "date") return races.get(entry.perf.race)?.date ?? "";
    return split(entry, key).v;
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
            {sorted.slice(0, limit).map((entry) => {
              const { perf, event } = entry;
              const race = races.get(perf.race);
              const athlete = athletes.get(perf.athlete);
              return (
                <tr key={perf.id} className="clickable" onClick={() => navigate(`/races/${perf.race}`)}>
                  <td>
                    {both && (
                      <span
                        className="legend-swatch-dot sex-dot"
                        style={{ background: sexGroup(event.sex).color }}
                        title={sexGroup(event.sex).label}
                      />
                    )}
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
                    const { i, v } = split(entry, p.key);
                    const suspect = i !== undefined && perf.suspect.includes(i);
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
