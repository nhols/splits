// Search across athletes, races, events and competitions. Opens with ⌘K, Ctrl+K or "/".

import { useEffect, useMemo, useRef, useState } from "react";
import { date, eventName, eventPath, roundName, time } from "../data/format";
import { useIndex } from "../data/load";
import type { Index } from "../data/types";
import { navigate } from "../router";

interface Result {
  group: string;
  title: string;
  meta: string;
  to: string;
  text: string;
}

function fold(text: string): string {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function candidates(index: Index): Result[] {
  const competitions = new Map(index.competitions.map((c) => [c.id, c]));
  const results: Result[] = [];
  for (const event of index.events) {
    const name = eventName(index, event.id);
    results.push({ group: "Events", title: name, meta: `${event.races} races`, to: eventPath(event.id), text: fold(name) });
  }
  for (const athlete of index.athletes) {
    const best = Object.entries(athlete.bests)
      .map(([event, value]) => `${eventName(index, event).replace(/^(Men's|Women's) /, "")} ${time(value)}`)
      .join(" · ");
    results.push({
      group: "Athletes",
      title: athlete.name,
      meta: `${athlete.country}${best ? ` · ${best}` : ""}`,
      to: `/athletes/${athlete.id}`,
      text: fold(`${athlete.name} ${athlete.familyName} ${athlete.country}`),
    });
  }
  for (const competition of index.competitions) {
    results.push({
      group: "Competitions",
      title: competition.name,
      meta: `${competition.city} · ${competition.startDate.slice(0, 4)}`,
      to: `/races?competition=${competition.id}`,
      text: fold(`${competition.name} ${competition.city} ${competition.startDate.slice(0, 4)}`),
    });
  }
  for (const race of index.races) {
    const competition = competitions.get(race.competition);
    const title = `${eventName(index, race.event)} · ${roundName(race.round, race.heat)}`;
    results.push({
      group: "Races",
      title,
      meta: `${competition?.name ?? race.competition} · ${date(race.date)}`,
      to: `/races/${race.id}`,
      text: fold(`${title} ${competition?.name ?? ""} ${competition?.city ?? ""} ${race.date.slice(0, 4)}`),
    });
  }
  return results;
}

export function Search() {
  const index = useIndex();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const all = useMemo(() => candidates(index), [index]);

  const results = useMemo(() => {
    const terms = fold(query).split(/\s+/).filter(Boolean);
    if (!terms.length) return all.filter((r) => r.group === "Events");
    return all.filter((r) => terms.every((term) => r.text.includes(term))).slice(0, 40);
  }, [all, query]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const typing = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
      if ((event.key === "k" && (event.metaKey || event.ctrlKey)) || (event.key === "/" && !typing)) {
        event.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
      requestAnimationFrame(() => input.current?.focus());
    }
  }, [open]);

  const go = (result: Result | undefined) => {
    if (!result) return;
    setOpen(false);
    navigate(result.to);
  };

  let lastGroup = "";
  return (
    <>
      <button type="button" className="search-trigger" onClick={() => setOpen(true)} aria-label="Search">
        <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" strokeWidth="2.2" />
          <path d="m15.5 15.5 5 5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
        <span>Search athletes, races…</span>
        <kbd>⌘K</kbd>
      </button>
      {open && (
        <div className="search-backdrop" onMouseDown={() => setOpen(false)}>
          <div className="search-panel" role="dialog" aria-label="Search" onMouseDown={(e) => e.stopPropagation()}>
            <input
              ref={input}
              className="search-input"
              placeholder="Search athletes, races, competitions…"
              value={query}
              aria-controls="search-results"
              aria-activedescendant={results.length ? `search-result-${cursor}` : undefined}
              onChange={(event) => {
                setQuery(event.target.value);
                setCursor(0);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") setOpen(false);
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setCursor((c) => Math.min(c + 1, results.length - 1));
                }
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setCursor((c) => Math.max(c - 1, 0));
                }
                if (event.key === "Enter") go(results[cursor]);
              }}
            />
            <div className="search-results" id="search-results" role="listbox">
              {results.length === 0 && <div className="empty" style={{ padding: 16 }}>Nothing matches “{query}”.</div>}
              {results.map((result, i) => {
                const header = result.group !== lastGroup ? result.group : null;
                lastGroup = result.group;
                return (
                  <div key={`${result.to}-${i}`}>
                    {header && <div className="search-group eyebrow">{header}</div>}
                    <button
                      type="button"
                      id={`search-result-${i}`}
                      role="option"
                      aria-selected={i === cursor}
                      className="search-result"
                      onMouseEnter={() => setCursor(i)}
                      onClick={() => go(result)}
                    >
                      <span className="title">{result.title}</span>
                      <span className="meta">{result.meta}</span>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
