// Reporting wrong data, a missing race, a problem with the site, or an idea. Each report is
// filed as a GitHub issue (see src/report/). The form starts from the page the reporter came
// from, passed as ?from=: on a race page it is about that race, and so on.

import { Suspense, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Card, Loading, Segmented } from "../components/ui";
import { useIndex, useRace } from "../data/load";
import { aboutPage, athleteRef, raceRef, type About } from "../report/context";
import { FIELD_NAMES, FIELDS, type Field, type Kind, type Ref, type Report } from "../report/report.ts";
import { Turnstile, turnstileEnabled } from "../report/Turnstile";
import { Link, useParam } from "../router";
import "./pages.css";
import "./report.css";

const KIND_OPTIONS: { value: Kind; label: string }[] = [
  { value: "data", label: "Wrong data" },
  { value: "race", label: "Missing race" },
  { value: "bug", label: "Site problem" },
  { value: "idea", label: "Idea" },
];

type Status = { state: "editing" | "sending" } | { state: "sent"; number: number; url: string } | { state: "failed"; error: string };

export function ReportPage() {
  const index = useIndex();
  const [from] = useParam("from");
  const [kindParam, setKind] = useParam("kind");
  const page = from && from.startsWith("/") && !from.startsWith("//") ? from : "/";
  const about = useMemo(() => aboutPage(index, page), [index, page]);
  const kind: Kind = KIND_OPTIONS.some((o) => o.value === kindParam)
    ? (kindParam as Kind)
    : about.race || about.athlete
      ? "data"
      : about.label
        ? "race"
        : "idea";

  const [field, setField] = useState<Field>("split");
  const [athlete, setAthlete] = useState<Ref | null>(about.athlete ? athleteRef(about.athlete) : null);
  const [point, setPoint] = useState<Ref | null>(null);
  const [correct, setCorrect] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [analysisUrl, setAnalysisUrl] = useState("");
  const [resultsUrl, setResultsUrl] = useState("");
  const [raceName, setRaceName] = useState(about.race ? "" : (about.label ?? ""));
  const [replaces, setReplaces] = useState(false);
  const [details, setDetails] = useState("");
  const [expected, setExpected] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  const [status, setStatus] = useState<Status>({ state: "editing" });

  const race = about.race ? raceRef(index, about.race) : undefined;

  function report(): Report {
    const context = {
      page,
      builtAt: index.build.builtAt,
      codeVersion: index.build.codeVersion,
      userAgent: kind === "bug" ? navigator.userAgent : undefined,
      viewport: kind === "bug" ? `${window.innerWidth}×${window.innerHeight}` : undefined,
    };
    switch (kind) {
      case "data":
        return {
          kind,
          field,
          race,
          athlete: athlete ?? undefined,
          point: field === "split" && point ? point : undefined,
          correct,
          sourceUrl,
          details,
          context,
        };
      case "race":
        return { kind, analysisUrl, resultsUrl, raceName, replaces: replaces ? race : undefined, details, context };
      case "bug":
        return { kind, details, expected, context };
      case "idea":
        return { kind, details, context };
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setStatus({ state: "sending" });
    try {
      const response = await fetch(`${import.meta.env.BASE_URL}api/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report: report(), turnstile: token }),
      });
      const answer = (await response.json().catch(() => ({}))) as { error?: string; number?: number; url?: string };
      if (response.ok && answer.number && answer.url) setStatus({ state: "sent", number: answer.number, url: answer.url });
      else setStatus({ state: "failed", error: answer.error ?? "The report couldn't be sent. Please try again later." });
    } catch {
      setStatus({ state: "failed", error: "The report couldn't be sent. Check your connection and try again." });
    }
    setGeneration((g) => g + 1);
  }

  if (status.state === "sent") {
    return (
      <div className="page narrow stack" style={{ "--gap": "20px" } as React.CSSProperties}>
        <h1>Thank you</h1>
        <p className="lede">
          Filed as{" "}
          <a className="link" href={status.url} target="_blank" rel="noreferrer">
            #{status.number}
          </a>
        </p>
        <div className="row">
          <Link to={page} className="button">
            Back
          </Link>
          <button type="button" className="button ghost" onClick={() => setStatus({ state: "editing" })}>
            Report something else
          </button>
        </div>
      </div>
    );
  }

  const describe = kind === "bug" || kind === "idea";
  const ready = (!turnstileEnabled || token) && status.state !== "sending";

  return (
    <div className="page narrow stack" style={{ "--gap": "20px" } as React.CSSProperties}>
      <header className="page-header">
        <h1>Report</h1>
      </header>
      <Segmented label="What to report" value={kind} options={KIND_OPTIONS} onChange={(value) => setKind(value)} />
      <Card>
        <form className="report-form" onSubmit={submit}>
          {kind === "data" && (
            <>
              <AboutLine about={about} race={race} />
              <Row label="What's wrong">
                <select className="text-input" value={field} onChange={(e) => setField(e.target.value as Field)}>
                  {FIELDS.map((f) => (
                    <option key={f} value={f}>
                      {FIELD_NAMES[f]}
                    </option>
                  ))}
                </select>
              </Row>
              {about.race && (
                <Suspense fallback={<Loading />}>
                  <RaceChoices
                    race={about.race.id}
                    field={field}
                    athlete={athlete}
                    point={point}
                    onAthlete={setAthlete}
                    onPoint={setPoint}
                  />
                </Suspense>
              )}
              <Row label="Correct value" optional>
                <input className="text-input" value={correct} onChange={(e) => setCorrect(e.target.value)} maxLength={200} />
              </Row>
              <Row label="Source for the correct value" hint="A link to a page or document that shows it" optional>
                <input className="text-input" type="url" placeholder="https://" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
              </Row>
              <Row label={race || athlete ? "Details" : "Which race, and what's wrong"} optional={Boolean(race || athlete)}>
                <textarea className="text-input" rows={4} value={details} onChange={(e) => setDetails(e.target.value)} maxLength={5000} required={!race && !athlete} />
              </Row>
            </>
          )}

          {kind === "race" && (
            <>
              {race && (
                <label className="report-check">
                  <input type="checkbox" checked={replaces} onChange={(e) => setReplaces(e.target.checked)} />
                  A better source for {race.name}
                </label>
              )}
              {!replaces && (
                <Row label="Race" optional>
                  <input className="text-input" placeholder="Women's 1500m, Oslo 2025" value={raceName} onChange={(e) => setRaceName(e.target.value)} maxLength={200} />
                </Row>
              )}
              <Row label="Link to the splits" hint="The page or PDF with the times at each split">
                <input className="text-input" type="url" required placeholder="https://" value={analysisUrl} onChange={(e) => setAnalysisUrl(e.target.value)} />
              </Row>
              <Row label="Link to the official results" hint="If they're separate: they give the lanes and reaction times" optional>
                <input className="text-input" type="url" placeholder="https://" value={resultsUrl} onChange={(e) => setResultsUrl(e.target.value)} />
              </Row>
              <Row label="Details" optional>
                <textarea className="text-input" rows={3} value={details} onChange={(e) => setDetails(e.target.value)} maxLength={5000} />
              </Row>
            </>
          )}

          {describe && (
            <Row label={kind === "bug" ? "What happened" : "Your idea"}>
              <textarea className="text-input" rows={6} required value={details} onChange={(e) => setDetails(e.target.value)} maxLength={5000} />
            </Row>
          )}
          {kind === "bug" && (
            <Row label="What you expected" optional>
              <textarea className="text-input" rows={3} value={expected} onChange={(e) => setExpected(e.target.value)} maxLength={5000} />
            </Row>
          )}

          <Turnstile onToken={setToken} generation={generation} />
          {status.state === "failed" && (
            <p className="report-error" role="alert">
              {status.error}
            </p>
          )}
          <div className="row">
            <button type="submit" className="button primary" disabled={!ready}>
              {status.state === "sending" ? "Sending…" : "Send"}
            </button>
            <span className="muted report-note">Reports are public on GitHub.</span>
          </div>
        </form>
      </Card>
    </div>
  );
}

function AboutLine({ about, race }: { about: About; race: Ref | undefined }) {
  const name = race?.name ?? about.athlete?.name;
  return name ? (
    <Row label="About">
      <div className="report-about">{name}</div>
    </Row>
  ) : null;
}

/** On a race page: which athlete, and for a split, which timing point. */
function RaceChoices({
  race: id,
  field,
  athlete,
  point,
  onAthlete,
  onPoint,
}: {
  race: string;
  field: Field;
  athlete: Ref | null;
  point: Ref | null;
  onAthlete: (athlete: Ref | null) => void;
  onPoint: (point: Ref | null) => void;
}) {
  const index = useIndex();
  const race = useRace(id);
  const names = new Map(index.athletes.map((a) => [a.id, a.name]));
  const runners = race.performances.map((p) => ({
    id: p.athlete,
    name: names.get(p.athlete) ?? `${p.givenName} ${p.familyName}`,
  }));
  const points = race.points.map((p) => ({ id: p.key, name: p.label }));
  return (
    <>
      <Row label="Athlete" optional>
        <select
          className="text-input"
          value={athlete?.id ?? ""}
          onChange={(e) => onAthlete(runners.find((r) => r.id === e.target.value) ?? null)}
        >
          <option value="">—</option>
          {runners.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </Row>
      {field === "split" && points.length > 0 && (
        <Row label="Split" optional>
          <select
            className="text-input"
            value={point?.id ?? ""}
            onChange={(e) => onPoint(points.find((p) => p.id === e.target.value) ?? null)}
          >
            <option value="">—</option>
            {points.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Row>
      )}
    </>
  );
}

function Row({
  label,
  hint,
  optional = false,
  children,
}: {
  label: string;
  hint?: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="report-row">
      <span className="report-label">
        {label}
        {optional && <span className="report-optional"> · optional</span>}
      </span>
      {hint && <span className="report-hint">{hint}</span>}
      {children}
    </label>
  );
}
