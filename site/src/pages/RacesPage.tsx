import { CompetitionMenus, useCompetitionFilters } from "../components/CompetitionMenus";
import { Card, Segmented, Select, WarningIcon } from "../components/ui";
import { useIncremental } from "../components/useIncremental";
import {
  count,
  date,
  disciplineName,
  eventName,
  roundGroup,
  roundName,
  splitType,
  splitTypeName,
  time,
} from "../data/format";
import { offered, passing, type Filters } from "../data/filters";
import { useIndex } from "../data/load";
import { Link, navigate, useParam } from "../router";
import "./pages.css";
import "./event.css";

export function RacesPage() {
  const index = useIndex();
  const [series] = useParam("series");
  const [competition] = useParam("competition");
  const [year, setYear] = useParam("year");
  const [discipline, setDiscipline] = useParam("discipline");
  const [sex, setSex] = useParam("sex");
  const [setting, setSetting] = useParam("setting");
  const [splits, setSplits] = useParam("splits");
  const [round, setRound] = useParam("round");
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const competitions = new Map(index.competitions.map((c) => [c.id, c]));
  const competitionFilters = useCompetitionFilters();
  const filters: Filters = {
    year: year ? (r) => r.date.startsWith(year) : null,
    ...competitionFilters,
    discipline: discipline ? (r) => r.discipline === discipline : null,
    splits: splits ? (r) => splitType(r.points) === splits : null,
    sex: sex ? (r) => r.sex === sex : null,
    setting: setting ? (r) => r.setting === setting : null,
    round: round ? (r) => roundGroup(r.round) === round : null,
  };
  const races = passing(index.races, filters);
  // Each menu offers what the other filters leave.
  const left = (filter: string) => passing(index.races, filters, filter);
  const allYears = [...new Set(index.races.map((r) => r.date.slice(0, 4)))].sort().reverse();
  const years = offered(allYears, (y) => y, left("year").map((r) => r.date.slice(0, 4)), year);
  const allDisciplines = [...index.disciplines].sort((a, b) => a.distance - b.distance || a.kind.localeCompare(b.kind));
  const disciplines = offered(allDisciplines, (d) => d.id, left("discipline").map((r) => r.discipline), discipline);
  // Split types in the data: by distance, then every hurdle, then none.
  const rank = (type: string) => (type === "none" ? 1e9 : type === "hurdles" ? 1e8 : parseFloat(type));
  const allSplitTypes = [...new Set(index.races.map((r) => splitType(r.points)))].sort((a, b) => rank(a) - rank(b));
  const splitTypes = offered(allSplitTypes, (t) => t, left("splits").map((r) => splitType(r.points)), splits);
  const selected = competition ? competitions.get(competition) : index.series.find((s) => s.id === series);
  const filtered = series || competition || year || discipline || sex || setting || splits || round;
  const { shown: rows, more, sentinel } = useIncremental(
    races,
    [series, competition, year, discipline, sex, setting, splits, round].join("|"),
  );
  return (
    <div className="page stack" style={{ "--gap": "20px" } as React.CSSProperties}>
      <header className="page-header">
        <h1>{selected ? selected.name : "Races"}</h1>
        <p className="lede">
          {count(races.length)} race{races.length === 1 ? "" : "s"}
        </p>
      </header>
      <div className="filter-bar" role="group" aria-label="Filters">
        <Select
          label="Year"
          value={year ?? ""}
          onChange={(v) => setYear(v || null)}
          options={[{ value: "", label: "All years" }, ...years.map((y) => ({ value: y, label: y }))]}
        />
        <CompetitionMenus races={index.races} filters={filters} />
        <Select
          label="Event"
          value={discipline ?? ""}
          onChange={(v) => setDiscipline(v || null)}
          options={[
            { value: "", label: "All events" },
            ...disciplines.map((d) => ({ value: d.id, label: disciplineName(d) })),
          ]}
        />
        <Select
          label="Splits"
          value={splits ?? ""}
          onChange={(v) => setSplits(v || null)}
          options={[
            { value: "", label: "All splits" },
            ...splitTypes.map((type) => ({ value: type, label: splitTypeName(type) })),
          ]}
        />
        <Segmented
          label="Men or women"
          value={sex ?? ""}
          onChange={(v) => setSex(v || null)}
          options={[
            { value: "", label: "Both" },
            { value: "men", label: "Men" },
            { value: "women", label: "Women" },
          ]}
        />
        <Segmented
          label="Indoor or outdoor"
          value={setting ?? ""}
          onChange={(v) => setSetting(v || null)}
          options={[
            { value: "", label: "Both" },
            { value: "outdoor", label: "Outdoor" },
            { value: "indoor", label: "Indoor" },
          ]}
        />
        <Segmented
          label="Round"
          value={round ?? ""}
          onChange={(v) => setRound(v || null)}
          options={[
            { value: "", label: "All rounds" },
            { value: "Heats", label: "Heats" },
            { value: "Semi-finals", label: "Semi-finals" },
            { value: "Finals", label: "Finals" },
            { value: "B races", label: "B races" },
          ]}
        />
        {filtered && (
          <button type="button" className="button ghost" onClick={() => navigate("/races", { replace: true, keepScroll: true })}>
            Clear
          </button>
        )}
      </div>
      <Card>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Date</th>
                <th>Race</th>
                <th>Competition</th>
                <th>Winner</th>
                <th className="right">Time</th>
                <th>Splits</th>
                <th aria-label="Data notes" />
              </tr>
            </thead>
            <tbody>
              {rows.map((race) => {
                const winner = race.winner ? athletes.get(race.winner.athlete) : undefined;
                return (
                  <tr key={race.id} className="clickable" onClick={() => navigate(`/races/${race.id}`)}>
                    <td className="secondary">{date(race.date)}</td>
                    <td>
                      <Link to={`/races/${race.id}`} className="link-plain" onClick={(e) => e.stopPropagation()}>
                        {eventName(index, race.event)} · {roundName(race.round, race.heat)}
                      </Link>
                    </td>
                    <td className="secondary">{competitions.get(race.competition)?.name}</td>
                    <td>
                      {winner?.name} <span className="country">{winner?.country}</span>
                    </td>
                    <td className="right">{race.winner ? time(race.winner.time) : "–"}</td>
                    <td className="secondary">{splitTypeName(splitType(race.points))}</td>
                    <td>{race.flags > 0 && <WarningIcon title={`${race.flags} data note(s)`} />}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {more && <div ref={sentinel} aria-hidden="true" />}
      </Card>
    </div>
  );
}
