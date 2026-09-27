import { Suspense, useMemo } from "react";
import { EventList, fastestByEvent } from "../components/EventList";
import { count, dateRange, eventName, time } from "../data/format";
import { useIndex, useRace } from "../data/load";
import { Link } from "../router";
import { RaceReplay } from "../track/RaceReplay";
import { raceOnTrackFrom } from "../track/runners";
import "./home.css";
import "./pages.css";

/** The race the home page replays. */
const FEATURED = "og-2024-paris/400mh-women/final";

export function HomePage() {
  const index = useIndex();
  // The events whose world record is not in the data (none published its splits).
  const fastest = fastestByEvent(index);
  const missing = index.events
    .filter((event) => !fastest.get(event.id)?.records?.includes("WR"))
    .map((event) => `the ${eventName(index, event.id).toLowerCase()}`);
  const total = index.events.length;
  const records =
    missing.length === 0
      ? "every world record"
      : missing.length <= 2
        ? `the world record in every event but ${new Intl.ListFormat("en-GB").format(missing)}`
        : `the world records of ${total - missing.length} of the ${total} events`;
  return (
    <div className="page wide stack" style={{ "--gap": "40px" } as React.CSSProperties}>
      <section className="home-intro">
        <h1>Elite track races, split by split.</h1>
        <p className="lede">
          {count(index.build.splits)} splits from {count(index.build.races)} races, including {records}.
        </p>
      </section>

      <Suspense fallback={<div className="home-track" />}>
        <Featured />
      </Suspense>

      <section className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
        <h2>Events</h2>
        <EventList />
      </section>

      <section className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
        <h2>Competitions</h2>
        <div className="competition-list">
          {index.competitions.map((c) => (
            <Link key={c.id} to={`/races?competition=${c.id}`} className="competition-row">
              <span className="competition-name">{c.name}</span>
              <span className="muted">{dateRange(c.startDate, c.endDate)}</span>
              <span className="competition-count num">{c.races} races</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function Featured() {
  const index = useIndex();
  const race = useRace(FEATURED);
  const onTrack = useMemo(() => raceOnTrackFrom(race, index), [race, index]);
  const winner = race.performances.find((p) => p.place?.v === 1);
  const name = index.athletes.find((a) => a.id === winner?.athlete)?.name;
  const record = winner?.records.some((r) => r.v === "WR");
  const competition = index.competitions.find((c) => c.id === race.competition);
  const event = `${race.discipline}-${race.sex}`;
  return (
    <figure className="home-track">
      <RaceReplay race={onTrack} compact autoplay loop label={`Replay of the ${eventName(index, event)} final at ${competition?.name}`} />
      <figcaption>
        <Link to={`/races/${FEATURED}`} className="link-plain">
          {record && <strong>World record · </strong>}
          {name && `${name} `}
          <span className="num">{time(winner?.time?.v)}</span> · {eventName(index, event)} · {competition?.name} →
        </Link>
      </figcaption>
    </figure>
  );
}
