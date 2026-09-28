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
import { useIndex } from "../data/load";
import { Link, navigate, useParam } from "../router";
import "./pages.css";
import "./event.css";

export function RacesPage() {
  const index = useIndex();
  const [competition, setCompetition] = useParam("competition");
  const [year, setYear] = useParam("year");
  const [discipline, setDiscipline] = useParam("discipline");
  const [sex, setSex] = useParam("sex");
  const [setting, setSetting] = useParam("setting");
  const [splits, setSplits] = useParam("splits");
  const [round, setRound] = useParam("round");
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const competitions = new Map(index.competitions.map((c) => [c.id, c]));
  const races = index.races.filter(
    (r) =>
      (!competition || r.competition === competition) &&
      (!year || r.date.startsWith(year)) &&
      (!discipline || r.discipline === discipline) &&
      (!sex || r.sex === sex) &&
      (!setting || r.setting === setting) &&
      (!splits || splitType(r.points) === splits) &&
      (!round || roundGroup(r.round) === round),
  );
  const selected = competition ? competitions.get(competition) : undefined;
  const years = [...new Set(index.races.map((r) => r.date.slice(0, 4)))].sort().reverse();
  // The competitions of the year chosen (and the one chosen, so the menu can show it).
  const shown = index.competitions.filter((c) => !year || c.startDate.startsWith(year) || c.id === competition);
  const disciplines = index.disciplines
    .filter((d) => index.races.some((r) => r.discipline === d.id))
    .sort((a, b) => a.distance - b.distance || a.kind.localeCompare(b.kind));
  // Split types in the data: by distance, then every hurdle, then none.
  const rank = (type: string) => (type === "none" ? 1e9 : type === "hurdles" ? 1e8 : parseFloat(type));
  const splitTypes = [...new Set(index.races.map((r) => splitType(r.points)))].sort((a, b) => rank(a) - rank(b));
  const filtered = competition || year || discipline || sex || setting || splits || round;
  const { shown: rows, more, sentinel } = useIncremental(
    races,
    [competition, year, discipline, sex, setting, splits, round].join("|"),
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
        <Select
          label="Competition"
          value={competition ?? ""}
          onChange={(v) => setCompetition(v || null)}
          options={[{ value: "", label: "All competitions" }, ...shown.map((c) => ({ value: c.id, label: c.name }))]}
        />
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
