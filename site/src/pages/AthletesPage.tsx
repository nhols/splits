import { useMemo, useState } from "react";
import { Card, Select } from "../components/ui";
import { offered } from "../data/filters";
import { count, eventName, time } from "../data/format";
import { useIndex } from "../data/load";
import { Link, navigate, useParam } from "../router";
import "./pages.css";
import "./event.css";

function fold(text: string): string {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function AthletesPage() {
  const index = useIndex();
  const [query, setQuery] = useState("");
  const [event, setEvent] = useParam("event");
  const [limit, setLimit] = useState(100);
  const named = useMemo(() => {
    const terms = fold(query).split(/\s+/).filter(Boolean);
    return index.athletes.filter((a) => terms.every((t) => fold(`${a.name} ${a.country}`).includes(t)));
  }, [index, query]);
  const athletes = useMemo(
    () =>
      named
        .filter((a) => !event || a.events.includes(event))
        .sort((a, b) =>
          event ? (a.bests[event] ?? Infinity) - (b.bests[event] ?? Infinity) : a.familyName.localeCompare(b.familyName),
        ),
    [named, event],
  );
  // The events of the athletes the name filter leaves.
  const events = offered(index.events, (e) => e.id, named.flatMap((a) => a.events), event);
  return (
    <div className="page stack" style={{ "--gap": "20px" } as React.CSSProperties}>
      <header className="page-header">
        <h1>Athletes</h1>
        <p className="lede">{count(index.athletes.length)} athletes</p>
      </header>
      <div className="filter-bar">
        <input
          className="text-input"
          placeholder="Filter by name or country"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Filter athletes"
          style={{ width: 280 }}
        />
        <Select
          label="Event"
          value={event ?? ""}
          onChange={(v) => setEvent(v || null)}
          options={[{ value: "", label: "All events (A–Z)" }, ...events.map((e) => ({ value: e.id, label: `${eventName(index, e.id)}, fastest first` }))]}
        />
      </div>
      <Card>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Athlete</th>
                <th>Country</th>
                <th>Born</th>
                <th>Fastest</th>
                <th className="right">Races</th>
              </tr>
            </thead>
            <tbody>
              {athletes.slice(0, limit).map((a) => (
                <tr key={a.id} className="clickable" onClick={() => navigate(`/athletes/${a.id}`)}>
                  <td>
                    <Link to={`/athletes/${a.id}`} className="link-plain" onClick={(e) => e.stopPropagation()}>
                      {a.name}
                    </Link>
                  </td>
                  <td className="country">{a.country}</td>
                  <td className="secondary">{a.birthDate?.slice(0, 4) ?? "–"}</td>
                  <td className="secondary">
                    {Object.entries(a.bests)
                      .sort(([x], [y]) => (x === event ? -1 : y === event ? 1 : 0))
                      .map(([e, t]) => `${eventName(index, e).replace(/^(Men's|Women's) /, "")} ${time(t)}`)
                      .join(" · ") || "–"}
                  </td>
                  <td className="right">{a.races}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {athletes.length > limit && (
          <button type="button" className="button" style={{ marginTop: 12 }} onClick={() => setLimit(limit + 300)}>
            Show more ({count(athletes.length - limit)} left)
          </button>
        )}
        {athletes.length === 0 && <div className="empty">No athlete matches.</div>}
      </Card>
    </div>
  );
}
