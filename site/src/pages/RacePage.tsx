import { useMemo, useState } from "react";
import { LineChart, type Datum, type Series } from "../components/charts/LineChart";
import { Legend } from "../components/charts/Legend";
import { Card, ExternalIcon, FlagIcon, WarningIcon } from "../components/ui";
import { date, eventName, eventPath, gap, roundName, time } from "../data/format";
import { useIndex, useRace } from "../data/load";
import type { DocumentOut, Index, RaceData } from "../data/types";
import { Link } from "../router";
import { raceOnTrackFrom } from "../track/runners";
import { RaceThem } from "./race/RaceThem";
import { SegmentStrips } from "./race/SegmentStrips";
import { leaders, raceDistance, rows as buildRows, type Row } from "./race/model";
import { SplitsTable } from "./race/SplitsTable";
import "./pages.css";
import "./event.css";

export function RacePage({ id }: { id: string }) {
  const index = useIndex();
  const race = useRace(id);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [stretch, setStretch] = useState<string | null>(null);

  const names = useMemo(
    () => new Map(index.athletes.map((a) => [a.id, { name: a.name, family: a.familyName }])),
    [index],
  );
  const rows = useMemo(() => buildRows(race, names), [race, names]);
  const competition = index.competitions.find((c) => c.id === race.competition);
  const event = `${race.discipline}-${race.sex}`;
  const timed = rows.some((row) => row.cells.size > 0);
  const onTrack = useMemo(() => raceOnTrackFrom(race, index), [race, index]);
  const siblings = index.races
    .filter((r) => r.competition === race.competition && r.event === event)
    .sort((a, b) => (a.date + a.id).localeCompare(b.date + b.id));

  return (
    <div className="page wide stack" style={{ "--gap": "24px" } as React.CSSProperties}>
      <header className="page-header">
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link to={`/races?competition=${race.competition}`}>{competition?.name}</Link>
          <span>›</span>
          <Link to={eventPath(event)}>{eventName(index, event)}</Link>
        </nav>
        <h1>
          {eventName(index, event)} · {roundName(race.round, race.heat)}
        </h1>
        <div className="row meta-row">
          <span>{date(race.date.v)}</span>
          {competition && <span>{competition.venue}</span>}
          {race.setting === "indoor" && <span>Indoor</span>}
          {race.wind && (
            <span>
              Wind {race.wind.v > 0 ? "+" : ""}
              {race.wind.v.toFixed(1)}
            </span>
          )}
          {race.flags.length > 0 && (
            <a href="#notes" className="chip chip-warning">
              <WarningIcon /> {race.flags.length}
            </a>
          )}
          <span className="row documents">
            {race.documents.map((document, i) => (
              <a key={document.id} href={documentLink(race, i)} target="_blank" rel="noreferrer" className="pill-link">
                {documentName(index, document)}
                <ExternalIcon />
              </a>
            ))}
          </span>
          <Link to={`/report?from=${encodeURIComponent(`/races/${race.id}`)}`} className="quiet-link report-link">
            <FlagIcon />
            Report a problem
          </Link>
        </div>
        {siblings.length > 1 && (
          <div className="row sibling-races">
            {siblings.map((sibling) => (
              <Link key={sibling.id} to={`/races/${sibling.id}`} className={sibling.id === race.id ? "pill on" : "pill"}>
                {roundName(sibling.round, sibling.heat)}
              </Link>
            ))}
          </div>
        )}
      </header>

      {onTrack.runners.length > 0 && (
        <RaceThem
          race={onTrack}
          event={event}
          highlight={highlight}
          onHighlight={setHighlight}
          stretch={stretch}
          onStretch={setStretch}
          label={`Replay of the ${eventName(index, event)} ${roundName(race.round, race.heat).toLowerCase()}`}
        />
      )}

      <Card>
        <SplitsTable
          race={race}
          rows={rows}
          highlight={highlight}
          onHighlight={setHighlight}
          onStretch={setStretch}
        />
      </Card>

      {timed && (
        <div className="grid-2 align-start">
          <Card title="Behind the leader">
            <RaceStory race={race} rows={rows} highlight={highlight} onHighlight={setHighlight} />
          </Card>
          <Card title="Segment times">
            <SegmentStrips
              race={race}
              rows={rows}
              highlight={highlight}
              onHighlight={setHighlight}
              stretch={stretch}
              onStretch={setStretch}
            />
          </Card>
        </div>
      )}

      {race.flags.length > 0 && (
        <Card title="Notes" id="notes">
          <Notes race={race} rows={rows} />
        </Card>
      )}
    </div>
  );
}

/** Documents that are not about one race: a handbook of past results, a research report. */
const COMPILATIONS: Record<string, string> = {
  "wa-handbook": "Statistics handbook",
  "iaaf-biomechanics": "Biomechanics report",
};

/** What a race's document is: its results, its race analysis, or a compilation. */
function documentName(index: Index, document: DocumentOut): string {
  const kind = index.formats.find((f) => f.id === document.format)?.kind;
  return COMPILATIONS[document.format] ?? (kind === "results" ? "Results" : "Race analysis");
}

/** A link to a document, open at the page this race was read from. */
function documentLink(race: RaceData, doc: number): string {
  const document = race.documents[doc]!;
  const url = document.archiveUrl ?? document.url;
  const pages = race.sources.filter((s) => s.doc === doc && s.page != null).map((s) => s.page!);
  return pages.length && Math.min(...pages) > 1 ? `${url}#page=${Math.min(...pages)}` : url;
}

/** Axis labels at the timing points: at most about ten, always the finish. */
function ticks(race: RaceData) {
  const every = Math.ceil(race.points.length / 10);
  return race.points
    .filter((_, i) => (race.points.length - 1 - i) % every === 0)
    .map((p) => ({ value: p.distance, label: p.kind === "finish" ? `${p.distance}m` : p.label }));
}

function RaceStory({ race, rows, highlight, onHighlight }: ChartProps) {
  const leader = leaders(race, rows);
  const finishIndex = race.points.length - 1;
  const series: Series[] = rows
    .map((row) => {
      const data: Datum[] = [{ x: 0, y: 0 }];
      for (const [index, cell] of [...row.cells].sort((a, b) => a[0] - b[0])) {
        const best = leader.get(index);
        if (best !== undefined) {
          data.push({ x: race.points[index]!.distance, y: cell.split.time.v - best, suspect: cell.suspect });
        }
      }
      const winner = leader.get(finishIndex);
      if (row.finish !== null && winner !== undefined) data.push({ x: raceDistance(race), y: row.finish - winner });
      return {
        id: row.perf.id,
        label: row.name,
        endLabel: `${row.perf.place?.v ?? "–"}  ${row.short}`,
        color: row.color,
        data,
      };
    })
    .filter((s) => s.data.length > 1);
  const legend = rows.map((row) => ({ id: row.perf.id, label: row.short, color: row.color }));
  return (
    <div className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
      <Legend items={legend} highlight={highlight} onHighlight={onHighlight} />
      <LineChart
        series={series}
        xDomain={[0, raceDistance(race)]}
        xTicks={ticks(race)}
        yFormat={(v) => (v === 0 ? "0" : `+${v.toFixed(v < 1 ? 2 : 1)}`)}
        yLabel="Seconds"
        highlight={highlight}
        onHighlight={onHighlight}
        tooltipTitle={(x) => (x === 0 ? "Start" : race.points.find((p) => p.distance === x)?.label ?? `${x} m`)}
        tooltipValue={(_, d) => (d.y < 0.005 ? "leading" : gap(d.y))}
      />
    </div>
  );
}

interface ChartProps {
  race: RaceData;
  rows: Row[];
  highlight: string | null;
  onHighlight: (id: string | null) => void;
}

/** What the checks found, each with a link to the page of the document the value is on. */
function Notes({ race, rows }: { race: RaceData; rows: Row[] }) {
  const index = useIndex();
  return (
    <ul className="quality-list">
      {race.flags.map((flag, i) => {
        const check = index.checks.find((c) => c.id === flag.check);
        const row = rows.find((r) => flag.subject.startsWith(r.perf.id));
        const cell = row ? [...row.cells.values()].find((c) => c.id === flag.subject) : undefined;
        const source = cell ? race.sources[cell.split.time.s] : undefined;
        const document = source?.doc != null ? race.documents[source.doc] : undefined;
        return (
          <li key={i}>
            <WarningIcon />
            <div>
              <div className="quality-title">
                {row ? `${row.name}: ` : ""}
                {check?.title ?? flag.check}
                {cell && ` (${time(cell.split.time.v)})`}
                {document && (
                  <>
                    {" "}
                    <a href={`${document.archiveUrl ?? document.url}#page=${source!.page ?? 1}`} target="_blank" rel="noreferrer" className="link">
                      Source
                    </a>
                  </>
                )}
              </div>
              <p className="secondary">{flag.message}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
