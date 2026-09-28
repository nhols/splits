import { startTransition, Suspense, useMemo, useState } from "react";
import { EventGroupList, fastestByEvent } from "../components/EventList";
import { count, dateRange, eventName, time } from "../data/format";
import { useIndex, useRace } from "../data/load";
import type { Index } from "../data/types";
import { Link } from "../router";
import { onStraight } from "../track/geometry";
import { RaceReplay } from "../track/RaceReplay";
import { raceOnTrackFrom } from "../track/runners";
import "./home.css";
import "./pages.css";

/** The race the home page falls back on, should no other qualify. */
const FEATURED = "og-2024-paris/400mh-women/final";

/** The races the home page may replay: finals with published splits, run round the track (not
 * the straight: the 100 m and sprint hurdles) up to the mile (longer ones take too long to
 * watch go round). */
function showable(index: Index): string[] {
  const distance = new Map(index.disciplines.map((d) => [d.id, d.distance]));
  return index.races
    .filter((r) => {
      const d = distance.get(r.discipline) ?? Infinity;
      return r.round === "final" && r.winner && r.points.length > 0 && !onStraight(d) && d <= 1609.344;
    })
    .map((r) => r.id);
}

const pick = (races: string[], not?: string) => {
  const choices = races.length > 1 ? races.filter((id) => id !== not) : races;
  return choices[Math.floor(Math.random() * choices.length)] ?? FEATURED;
};

export function HomePage() {
  const index = useIndex();
  // A different race on every visit, and another at the reader's asking.
  const races = useMemo(() => showable(index), [index]);
  const [featured, setFeatured] = useState(() => pick(races));
  // In a transition, the race showing stays until the next has loaded.
  const shuffle = () => startTransition(() => setFeatured(pick(races, featured)));
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
        <Featured id={featured} onShuffle={shuffle} />
      </Suspense>

      <section className="stack" style={{ "--gap": "12px" } as React.CSSProperties}>
        <h2>Events</h2>
        <EventGroupList />
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

function Featured({ id, onShuffle }: { id: string; onShuffle: () => void }) {
  const index = useIndex();
  const race = useRace(id);
  const onTrack = useMemo(() => raceOnTrackFrom(race, index), [race, index]);
  const winner = race.performances.find((p) => p.place?.v === 1);
  const name = index.athletes.find((a) => a.id === winner?.athlete)?.name;
  const record = winner?.records.some((r) => r.v === "WR");
  const competition = index.competitions.find((c) => c.id === race.competition);
  const event = `${race.discipline}-${race.sex}`;
  return (
    <figure className="home-track">
      <RaceReplay key={id} race={onTrack} compact autoplay loop label={`Replay of the ${eventName(index, event)} final at ${competition?.name}`} />
      <figcaption className="home-caption">
        <Link to={`/races/${id}`} className="link-plain">
          {record && <strong>World record · </strong>}
          {name && `${name} `}
          <span className="num">{time(winner?.time?.v)}</span> · {eventName(index, event)} · {competition?.name} →
        </Link>
        <button type="button" className="button ghost home-shuffle" onClick={onShuffle} title="Another race">
          <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M1.5 4.5h2c2 0 3 1.2 4.5 3.5s2.5 3.5 4.5 3.5h2" />
            <path d="M1.5 11.5h2c1.1 0 1.9-.4 2.7-1.2M9.3 5.7c.8-.8 1.6-1.2 2.7-1.2h2.5" />
            <path d="M12.5 2.5l2 2-2 2M12.5 9.5l2 2-2 2" />
          </svg>
          Shuffle
        </button>
      </figcaption>
    </figure>
  );
}
