// Runs compared like for like: one course (the distance, and the barriers if any) on one kind
// of track, outdoors or in. Men and women race each other wherever they run the same course.
// Choose the course, then add runs from its list: they race in a replay, each in a lane of
// its own, and their splits line up below. The choice is kept in the link.

import { Suspense, use, useMemo, useState } from "react";
import { LineChart, type Series } from "../components/charts/LineChart";
import { Legend } from "../components/charts/Legend";
import { EventList } from "../components/EventList";
import { SuspectTime } from "../components/Explained";
import { Card, Empty, Loading, Segmented } from "../components/ui";
import { timeline, type Mark } from "../data/analysis";
import { count, date, disciplineName, eventName, gap, roundName, time } from "../data/format";
import { fetchJson, useEvent, useIndex } from "../data/load";
import type { DisciplineOut, EventData, EventOut, EventPerformance, Index, RaceData } from "../data/types";
import { Link, navigate, useLocation } from "../router";
import { comparisonOnTrack, shortNames } from "../track/runners";
import { seriesColor } from "./race/model";
import { RaceThem } from "./race/RaceThem";
import "./pages.css";
import "./compare.css";

/** Runs in a comparison at most: one a lane. */
const MOST = 8;

/** What runs are compared on: a discipline, run by men and women alike unless their barriers
 * stand in different places (then each sex's event is a course of its own). */
interface Course {
  id: string;
  label: string;
  discipline: DisciplineOut;
  events: EventOut[];
  settings: string[];
}

/** Whether men and women run the same course: no barriers, or barriers in the same places
 * (the 400 m hurdles differ only in height). */
function oneCourse(discipline: DisciplineOut): boolean {
  const layouts = Object.values(discipline.barriers).filter((b) => b !== undefined);
  return layouts.every((b) => b.count === layouts[0]!.count && b.first === layouts[0]!.first && b.spacing === layouts[0]!.spacing);
}

/** Every course with runs, by distance, flat before hurdles and steeplechase. */
function coursesOf(index: Index): Course[] {
  const kinds = ["flat", "hurdles", "steeplechase"];
  const settings = (events: EventOut[]) => [...new Set(events.flatMap((e) => e.settings))];
  const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
  return [...index.disciplines]
    .sort((a, b) => a.distance - b.distance || kinds.indexOf(a.kind) - kinds.indexOf(b.kind))
    .flatMap((discipline) => {
      const events = index.events.filter((e) => e.discipline === discipline.id);
      if (!events.length) return [];
      if (oneCourse(discipline)) {
        return [{ id: discipline.id, label: capital(disciplineName(discipline)), discipline, events, settings: settings(events) }];
      }
      return events.map((event) => ({ id: event.id, label: eventName(index, event.id), discipline, events: [event], settings: event.settings }));
    });
}

export function ComparePage() {
  const index = useIndex();
  const { params } = useLocation();
  const courses = useMemo(() => coursesOf(index), [index]);
  const course = courses.find((c) => c.id === params.get("event")) ?? null;
  const asked = params.get("setting");
  const setting = !course
    ? null
    : asked && course.settings.includes(asked)
      ? asked
      : course.settings.includes("outdoor")
        ? "outdoor"
        : course.settings[0]!;
  const sex = params.get("sex");
  const ids = (params.get("p") ?? "").split(",").filter(Boolean);
  const go = (next: { course: string; setting?: string | null; sex?: string | null; runs?: string[] }) => {
    const query = new URLSearchParams({ event: next.course });
    if (next.setting) query.set("setting", next.setting);
    if (next.sex) query.set("sex", next.sex);
    if (next.runs?.length) query.set("p", next.runs.join(","));
    // Your time races on while the course stays the same.
    const you = params.get("you");
    if (you && next.course === course?.id) query.set("you", you);
    navigate(`/compare?${query.toString()}`, { replace: true, keepScroll: true });
  };
  // Where an event's runs are compared: its course, showing that sex's runs where it is shared.
  const courseOfEvent = (event: string) => {
    const found = courses.find((c) => c.events.some((e) => e.id === event))!;
    const shared = found.events.length > 1;
    return `/compare?event=${found.id}${shared ? `&sex=${event.slice(event.lastIndexOf("-") + 1)}` : ""}`;
  };
  return (
    <div className="page wide stack" style={{ "--gap": "24px" } as React.CSSProperties}>
      <header className="page-header compare-header">
        <h1>Compare</h1>
        <div className="row">
          <label className="select">
            <span className="visually-hidden">Event</span>
            <select value={course?.id ?? ""} onChange={(e) => go({ course: e.target.value })}>
              {!course && <option value="">Choose an event</option>}
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          {course && setting && course.settings.length > 1 && (
            <Segmented
              label="Track"
              value={setting}
              onChange={(track) => go({ course: course.id, setting: track, sex })}
              options={course.settings.map((s) => ({ value: s, label: s === "indoor" ? "Indoor" : "Outdoor" }))}
            />
          )}
        </div>
      </header>
      {course && setting ? (
        <Suspense fallback={<Loading />}>
          <Comparison
            key={`${course.id}/${setting}`}
            course={course}
            setting={setting}
            sex={sex}
            ids={ids}
            onRuns={(runs) => go({ course: course.id, setting, sex, runs })}
            onSex={(chosen) => go({ course: course.id, setting, sex: chosen, runs: ids })}
          />
        </Suspense>
      ) : (
        <EventList to={courseOfEvent} />
      )}
    </div>
  );
}

/** A run, with the event it belongs to (men's and women's runs may share a course). */
interface Entry {
  perf: EventPerformance;
  event: EventData;
}

/** The comparison on one course and kind of track: the runs chosen racing each other, and the
 * list to choose them from. */
function Comparison({
  course,
  setting,
  sex,
  ids,
  onRuns,
  onSex,
}: {
  course: Course;
  setting: string;
  sex: string | null;
  ids: string[];
  onRuns: (runs: string[]) => void;
  onSex: (sex: string | null) => void;
}) {
  const index = useIndex();
  // `use` may be called in a loop: each event file loads once.
  const events = course.events.map((e) => useEvent(e.id));
  const races = useMemo(() => new Map(index.races.map((r) => [r.id, r])), [index]);
  // Every finished run on the course on this kind of track, fastest first.
  const pool = useMemo(
    () =>
      events
        .flatMap((event) => event.performances.map((perf) => ({ perf, event })))
        .filter(({ perf }) => perf.status === "finished" && perf.time !== null && races.get(perf.race)?.setting === setting)
        .sort((a, b) => a.perf.time! - b.perf.time!),
    // The course fixes the events.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [course, races, setting],
  );
  const byId = useMemo(() => new Map(pool.map((entry) => [entry.perf.id, entry])), [pool]);
  const picked = [...new Set(ids)]
    .filter((id) => byId.has(id))
    .slice(0, MOST)
    .map((id) => byId.get(id)!);
  // Colours follow the runs, in the order they were added.
  const colors = new Map(picked.map(({ perf }, i) => [perf.id, seriesColor(i)]));
  const [highlight, setHighlight] = useState<string | null>(null);
  const toggle = (id: string) => {
    const now = picked.map(({ perf }) => perf.id);
    onRuns(now.includes(id) ? now.filter((x) => x !== id) : [...now, id]);
  };
  return (
    <div className="compare-layout">
      <div className="compare-main stack" style={{ "--gap": "24px" } as React.CSSProperties}>
        {picked.length ? (
          <>
            <Suspense
              fallback={
                <div className="compare-waiting">
                  <Loading />
                </div>
              }
            >
              <CompareReplay course={course} sex={sex} picked={picked} colors={colors} highlight={highlight} onHighlight={setHighlight} />
            </Suspense>
            <SplitsComparison course={course} picked={picked} colors={colors} highlight={highlight} onHighlight={setHighlight} />
          </>
        ) : (
          <Card>
            <Empty>Add runs from the list to race them against each other.</Empty>
          </Card>
        )}
      </div>
      <RunList
        pool={pool}
        picked={picked}
        colors={colors}
        sexes={course.events.map((e) => e.sex)}
        sex={sex}
        onSex={onSex}
        onToggle={toggle}
        onClear={() => onRuns([])}
      />
    </div>
  );
}

/** The runs racing each other: each in a lane of its own, moving as it did in its own race; and
 * you, at a time you choose, running the typical race of the sex shown (of the first run, where
 * the list shows both). */
function CompareReplay({
  course,
  sex,
  picked,
  colors,
  highlight,
  onHighlight,
}: {
  course: Course;
  sex: string | null;
  picked: Entry[];
  colors: Map<string, string>;
  highlight: string | null;
  onHighlight: (id: string | null) => void;
}) {
  const index = useIndex();
  // Each run's own race (`use` may be called in a loop; each race file loads once).
  const own = new Map(picked.map(({ perf }) => [perf.race, use(fetchJson<RaceData>(`races/${perf.race}.json`))]));
  const key = picked.map(({ perf }) => perf.id).join();
  const race = useMemo(() => {
    return comparisonOnTrack(
      picked.map(({ perf }) => ({ race: own.get(perf.race)!, performance: perf.id, color: colors.get(perf.id)! })),
      index,
    );
    // The runs chosen fix everything else here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, index]);
  const event = course.events.find((e) => e.sex === sex) ?? course.events.find((e) => e.id === picked[0]!.event.event) ?? course.events[0]!;
  return (
    <RaceThem
      key={key}
      race={race}
      event={event.id}
      highlight={highlight}
      onHighlight={onHighlight}
      label={`${course.label}: ${picked.length} runs side by side`}
    />
  );
}

interface Run {
  perf: EventPerformance;
  marks: Mark[];
  /** Times a check marked as suspect, by distance: shown, but left out of every comparison. */
  suspect: Map<number, number>;
  /** Distances its race was timed at, whether or not this run has a clean time there. */
  timedAt: number[];
  label: string;
  color: string;
}

/** The runs' splits side by side, and how far each was behind the fastest through the race. */
function SplitsComparison({
  course,
  picked,
  colors,
  highlight,
  onHighlight,
}: {
  course: Course;
  picked: Entry[];
  colors: Map<string, string>;
  highlight: string | null;
  onHighlight: (id: string | null) => void;
}) {
  const index = useIndex();
  const [view, setView] = useState<"splits" | "segments">("splits");
  const races = new Map(index.races.map((r) => [r.id, r]));
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const distance = course.discipline.distance;
  const runs: Run[] = picked.map(({ perf, event }) => {
    const race = races.get(perf.race)!;
    return {
      perf,
      marks: timeline(event.points, perf, distance),
      suspect: new Map(perf.suspect.flatMap((i) => (perf.splits[i] != null ? [[event.points[i]!.distance, perf.splits[i]!] as const] : []))),
      timedAt: [...event.points.filter((p) => race.points.includes(p.key)).map((p) => p.distance), distance],
      label: `${athletes.get(perf.athlete)?.name ?? perf.athlete} · ${runName(index, race.id)}`,
      color: colors.get(perf.id)!,
    };
  });
  // Every point any run was timed at (a suspect time too, so that it is shown); gaps only where
  // every run has a time.
  const common = [...new Set(runs.flatMap((r) => [...r.marks.map((m) => m.distance), ...r.suspect.keys()]))].sort((a, b) => a - b);
  const at = (run: Run, d: number) => run.marks.find((m) => m.distance === d);
  // Segments only between points every run was timed at, so that each compares like with like.
  const timedByAll = common.filter((d) => runs.every((r) => r.timedAt.includes(d)));
  const segmented = view === "segments" && timedByAll.length > 1;
  const columns = segmented ? timedByAll : common;
  // The value in a column: the time at the point, or for the segment ending there.
  const value = (run: Run, i: number): number | null => {
    const mark = at(run, columns[i]!);
    if (!mark) return null;
    if (!segmented || i === 0) return mark.time;
    const previous = at(run, columns[i - 1]!);
    return previous ? mark.time - previous.time : null;
  };
  // "Behind the fastest" only where every run has a time: elsewhere the fastest of the rest
  // would stand in, and gaps would jump from one point to the next as runs came and went.
  const fastest = (i: number) => {
    const values = runs.map((r) => value(r, i));
    return values.every((v) => v !== null) ? Math.min(...(values as number[])) : null;
  };
  const shared = common.filter((d) => runs.every((r) => at(r, d)));
  // End labels as in the replay's standings: "Bednarek Paris", "Bednarek ’26".
  const short = shortNames(
    picked.map(({ perf }) => {
      const race = races.get(perf.race)!;
      const family = athletes.get(perf.athlete)?.familyName ?? perf.athlete;
      return { id: perf.id, athlete: perf.athlete, family, competition: race.competition, date: race.date, round: race.round, heat: race.heat };
    }),
  );
  const gapSeries: Series[] = runs.map((run) => ({
    id: run.perf.id,
    label: run.label,
    endLabel: short.get(run.perf.id),
    color: run.color,
    data: [
      { x: 0, y: 0 },
      ...shared.map((d) => ({ x: d, y: at(run, d)!.time - Math.min(...runs.map((r) => at(r, d)!.time)) })),
    ],
  }));

  return (
    <>
      <Card
        title={segmented ? "Segments" : "Splits"}
        actions={
          timedByAll.length > 1 ? (
            <Segmented
              label="Times"
              value={view}
              onChange={setView}
              options={[
                { value: "splits", label: "Splits" },
                { value: "segments", label: "Segments" },
              ]}
            />
          ) : undefined
        }
      >
        <div className="table-wrap">
          <table className="data compare-splits">
            <thead>
              <tr>
                <th>Run</th>
                {columns.map((d, i) => (
                  <th key={d} className={`split${i % 2 === 0 ? " band" : ""}`}>
                    {segmented ? `${i > 0 ? columns[i - 1] : 0}–${d}m` : d === distance ? "Finish" : `${d}m`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.perf.id}
                  className={highlight === run.perf.id ? "highlighted" : ""}
                  onPointerEnter={() => onHighlight(run.perf.id)}
                  onPointerLeave={() => onHighlight(null)}
                >
                  <td>
                    <span className="athlete-cell">
                      <span className="swatch" style={{ background: run.color }} />
                      <Link to={`/races/${run.perf.race}`} className="link-plain">
                        {run.label}
                      </Link>
                      <span className="muted">{date(races.get(run.perf.race)?.date ?? "")}</span>
                    </span>
                  </td>
                  {columns.map((d, i) => {
                    const mine = value(run, i);
                    const band = i % 2 === 0 ? " band" : "";
                    const flagged = !segmented ? run.suspect.get(d) : undefined;
                    if (mine === null && flagged !== undefined) {
                      return (
                        <td key={d} className={`split${band}`}>
                          <SuspectTime>{time(flagged)}</SuspectTime>
                        </td>
                      );
                    }
                    if (mine === null) {
                      return (
                        <td key={d} className={`split muted${band}`}>
                          –
                        </td>
                      );
                    }
                    const best = fastest(i);
                    return (
                      <td key={d} className={`split${band}`}>
                        <span className="split-time">
                          {time(mine)}
                          {best !== null && mine - best >= 0.005 && <span className="rank">{gap(mine - best)}</span>}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {runs.length > 1 && shared.length > 1 && (
        <Card title="Behind the fastest">
          <div className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
            <Legend items={runs.map((r) => ({ id: r.perf.id, label: r.label, color: r.color }))} highlight={highlight} onHighlight={onHighlight} />
            <LineChart
              series={gapSeries}
              xDomain={[0, distance]}
              xTicks={shared.map((d) => ({ value: d, label: `${d}m` }))}
              yFormat={(v) => (v === 0 ? "0" : `+${v.toFixed(v < 1 ? 2 : 1)}`)}
              yLabel="Seconds behind"
              endLabels={runs.length <= 4}
              highlight={highlight}
              onHighlight={onHighlight}
              tooltipTitle={(x) => (x === 0 ? "Start" : x === distance ? "Finish" : `${x} m`)}
              tooltipValue={(_, d) => (d.y < 0.005 ? "fastest" : gap(d.y))}
            />
          </div>
        </Card>
      )}
    </>
  );
}

/** Where a run was: the meeting, and the round where the event had more than one there
 * ("Olympic Games Paris 2024", "final"; "Weltklasse Zürich 2026", ""). */
function whereRun(index: Index, raceId: string): { meet: string; round: string } {
  const race = index.races.find((r) => r.id === raceId);
  const competition = index.competitions.find((c) => c.id === race?.competition);
  const rounds = index.races.filter((r) => r.competition === race?.competition && r.event === race?.event).length;
  return { meet: competition?.name ?? raceId, round: race && rounds > 1 ? roundName(race.round, race.heat).toLowerCase() : "" };
}

/** "Olympic Games Paris 2024 final", "Weltklasse Zürich 2026" for a one-off race. */
function runName(index: Index, raceId: string): string {
  const { meet, round } = whereRun(index, raceId);
  return round ? `${meet} ${round}` : meet;
}

/** Text folded for searching: lower case, without accents. */
const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();

/** The course's runs to choose from: those chosen first, then the rest, fastest first,
 * narrowed to men or women where both run the course, and by a search over athletes,
 * countries, meetings, years and rounds. */
function RunList({
  pool,
  picked,
  colors,
  sexes,
  sex,
  onSex,
  onToggle,
  onClear,
}: {
  pool: Entry[];
  picked: Entry[];
  colors: Map<string, string>;
  sexes: string[];
  sex: string | null;
  onSex: (sex: string | null) => void;
  onToggle: (id: string) => void;
  onClear: () => void;
}) {
  const index = useIndex();
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(50);
  const described = useMemo(() => {
    const athletes = new Map(index.athletes.map((a) => [a.id, a]));
    return new Map(
      pool.map(({ perf }) => {
        const athlete = athletes.get(perf.athlete);
        const race = index.races.find((r) => r.id === perf.race);
        const where = whereRun(index, perf.race);
        const text = fold(`${athlete?.name ?? perf.athlete} ${athlete?.country ?? ""} ${where.meet} ${where.round} ${race?.date.slice(0, 4) ?? ""}`);
        return [perf.id, { athlete: athlete?.name ?? perf.athlete, country: athlete?.country ?? "", ...where, text }];
      }),
    );
  }, [pool, index]);
  const words = fold(query).split(/\s+/).filter(Boolean);
  const chosen = new Set(picked.map(({ perf }) => perf.id));
  const matches = pool.filter(
    ({ perf, event }) => !chosen.has(perf.id) && (!sex || event.sex === sex) && words.every((w) => described.get(perf.id)!.text.includes(w)),
  );
  const full = picked.length >= MOST;
  const row = ({ perf }: Entry) => {
    const about = described.get(perf.id)!;
    const on = chosen.has(perf.id);
    return (
      <li key={perf.id}>
        <button
          type="button"
          className={`run-pick${on ? " on" : ""}`}
          aria-pressed={on}
          disabled={!on && full}
          title={!on && full ? "Eight runs at most, one a lane" : undefined}
          onClick={() => onToggle(perf.id)}
        >
          <span className="run-pick-mark" style={on ? { background: colors.get(perf.id), borderColor: colors.get(perf.id) } : undefined} aria-hidden="true">
            {on ? "✓" : "+"}
          </span>
          <span className="run-pick-who">
            <span className="run-pick-name">
              {about.athlete} <span className="country">{about.country}</span>
            </span>
            <span className="run-pick-race">
              <span className="run-pick-meet">{about.meet}</span>
              {about.round && <span className="run-pick-round"> · {about.round}</span>}
              {perf.splits.every((s) => s === null) && <span className="run-pick-round"> · no splits</span>}
            </span>
          </span>
          <span className="run-pick-time num">{time(perf.time)}</span>
        </button>
      </li>
    );
  };
  return (
    <aside className="compare-side">
      <Card
        title="Runs"
        subtitle={`${count(picked.length)} of ${MOST} · ${count(pool.length)} runs`}
        actions={
          picked.length ? (
            <button type="button" className="button ghost" onClick={onClear}>
              Clear
            </button>
          ) : undefined
        }
      >
        <div className="run-filters">
          <input
            type="search"
            className="text-input"
            placeholder="Search athletes, meetings, years"
            aria-label="Search runs"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setLimit(50);
            }}
          />
          {sexes.length > 1 && (
            <Segmented
              label="Men or women"
              value={sex ?? "all"}
              onChange={(value) => onSex(value === "all" ? null : value)}
              options={[
                { value: "all", label: "All" },
                { value: "men", label: "Men" },
                { value: "women", label: "Women" },
              ]}
            />
          )}
        </div>
        <ol className="run-list">
          {picked.map(row)}
          {matches.slice(0, limit).map(row)}
        </ol>
        {matches.length > limit && (
          <button type="button" className="button ghost run-more" onClick={() => setLimit(limit + 50)}>
            Show more
          </button>
        )}
        {matches.length === 0 && words.length > 0 && <p className="muted run-none">No runs match.</p>}
      </Card>
    </aside>
  );
}
