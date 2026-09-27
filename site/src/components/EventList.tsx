import { eventName, time } from "../data/format";
import { useIndex } from "../data/load";
import type { EventOut, Index, Winner } from "../data/types";
import { Link } from "../router";

/** Each event's fastest winning time in the dataset: who ran it, and any record it set. */
export function fastestByEvent(index: Index): Map<string, Winner> {
  const fastest = new Map<string, Winner>();
  for (const race of index.races) {
    const best = fastest.get(race.event);
    if (race.winner && (!best || race.winner.time < best.time)) fastest.set(race.event, race.winner);
  }
  return fastest;
}

/** Every event in the order the site lists them: by distance, flat before hurdles and
 * steeplechase, the sprint hurdles (110 m for men, 100 m for women) as one pair; each row the
 * men's and the women's event, either missing where only one sex's event has races. */
function eventRows(index: Index): [string, Partial<Record<string, EventOut>>][] {
  const pair = (discipline: string) => (discipline === "100mh" ? "110mh" : discipline);
  const distance = new Map(index.disciplines.map((d) => [d.id, d.distance]));
  const rows = new Map<string, Partial<Record<string, EventOut>>>();
  for (const event of index.events) {
    const key = pair(event.discipline);
    rows.set(key, { ...rows.get(key), [event.sex]: event });
  }
  return [...rows].sort(([a], [b]) => (distance.get(a) ?? 0) - (distance.get(b) ?? 0) || a.localeCompare(b));
}

/** Every event, men on the left and women on the right, with the fastest time in the dataset.
 * Each links to its page, or wherever ``to`` says. */
export function EventList({ to = (event) => `/events/${event}` }: { to?: (event: string) => string }) {
  const index = useIndex();
  const athletes = new Map(index.athletes.map((a) => [a.id, a]));
  const fastestIn = fastestByEvent(index);
  return (
    <div className="event-list">
      {eventRows(index).flatMap(([key, row]) =>
        ["men", "women"].map((sex) => {
          const event = row[sex];
          if (!event) return <span key={`${key}/${sex}`} className="event-row empty" aria-hidden="true" />;
          const fastest = fastestIn.get(event.id);
          return (
            <Link key={event.id} to={to(event.id)} className="event-row">
              <span className="event-row-name">{eventName(index, event.id)}</span>
              <span className="event-row-time">
                <span className="num">{fastest ? time(fastest.time) : "–"}</span>
                {fastest?.records?.includes("WR") && <span className="tag">WR</span>}
              </span>
              <span className="event-row-who muted">{fastest ? athletes.get(fastest.athlete)?.name : ""}</span>
            </Link>
          );
        }),
      )}
    </div>
  );
}
