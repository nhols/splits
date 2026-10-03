// The race replay with you in it: type a time and a ghost runs in an empty lane, running the
// event's typical race in that time (see track/model.ts). Your time is kept per event (in this browser, and
// in the link), so you appear in every race of the event until you remove yourself.

import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useIndex } from "../../data/load";
import { useParam } from "../../router";
import { freeLanes, makeGhost, parseTime, type Basis, type Ghost } from "../../track/model";
import { RaceReplay } from "../../track/RaceReplay";
import type { RaceOnTrack } from "../../track/runners";

interface Props {
  race: RaceOnTrack;
  event: string;
  label: string;
  highlight: string | null;
  onHighlight: (id: string | null) => void;
  stretch?: string | null;
  onStretch?: (key: string | null) => void;
  /** The replay with fewer controls, looping (the home page: see ``RaceReplay``). */
  simple?: boolean;
  /** Whether your time goes in the link as well as this browser: not where the race shown
   * changes under the same link (the home page), taking your time to other events. */
  inLink?: boolean;
}

const storageKey = (event: string) => `splits.you.${event}`;

function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Storage may be unavailable: the time then lasts only as long as the link.
  }
}

export function RaceThem({ inLink = true, ...props }: Props) {
  const [linked, setLinked] = useParam("you");
  const [param, setParam] = inLink ? [linked, setLinked] : [null, () => {}];
  // Counts runs, so that racing again at the same time starts the race again.
  const [run, setRun] = useState(0);
  const target = parseTime(param ?? readStored(storageKey(props.event)) ?? "");
  const lane = freeLanes(props.race)[0]!;

  const setTarget = (value: number | null) => {
    const text = value === null ? null : value.toFixed(2);
    writeStored(storageKey(props.event), text);
    setParam(text);
    setRun((n) => n + 1);
  };
  const form = <RaceThemForm target={target} onTarget={setTarget} />;

  if (target === null) return <Replay {...props} ghost={null} controls={form} />;
  return <WithGhost {...props} target={target} lane={lane} run={run} form={form} />;
}

/** The race with you in it. */
function WithGhost({
  target,
  lane,
  run,
  form,
  ...props
}: Props & { target: number; lane: number; run: number; form: ReactNode }) {
  const index = useIndex();
  const event = index.events.find((e) => e.id === props.event);
  const ghost = useMemo(() => makeGhost(props.race, target, lane, event), [props.race, target, lane, event]);
  // A new run or time starts the race again, so you can watch yourself run it.
  return <Replay key={`${run}/${target}`} {...props} ghost={ghost} controls={form} />;
}

function Replay({
  race,
  ghost,
  controls,
  label,
  highlight,
  onHighlight,
  stretch,
  onStretch,
  simple,
}: Props & { ghost: Ghost | null; controls: ReactNode }) {
  const withGhost = useMemo(() => (ghost ? { ...race, runners: [...race.runners, ghost.runner] } : race), [race, ghost]);
  const notes = ghost ? [`You: ${describe(ghost.basis, ghost.runner.lane)}`] : [];
  return (
    <RaceReplay
      race={withGhost}
      autoplay
      simple={simple}
      loop={simple}
      highlight={highlight}
      onHighlight={onHighlight}
      stretch={stretch}
      onStretch={onStretch}
      controls={controls}
      modelNotes={notes}
      label={label}
    />
  );
}

/** What you run on, for the explainer. */
export function describe(basis: Basis | null, lane: number | null): string {
  const where = lane === null ? "" : `lane ${lane}, `;
  if (!basis) return `${where}an even pace: this event has no typical race.`;
  return `${where}the event's typical race (the median of ${basis.runs} runs), in your time.`;
}

function RaceThemForm({ target, onTarget }: { target: number | null; onTarget: (value: number | null) => void }) {
  const [draft, setDraft] = useState(target !== null ? target.toFixed(2) : "");
  const [invalid, setInvalid] = useState(false);
  useEffect(() => setDraft(target !== null ? target.toFixed(2) : ""), [target]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = parseTime(draft);
    setInvalid(value === null);
    if (value !== null) onTarget(value);
  };
  return (
    <form className="race-them" onSubmit={submit} title="Race the field at your own time, in an empty lane.">
      <input
        className="text-input num race-them-time"
        inputMode="decimal"
        placeholder="Your time"
        aria-label="Your time, in seconds"
        aria-invalid={invalid}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      <button type="submit" className="button">
        Race
      </button>
      {target !== null && (
        <button type="button" className="button ghost" onClick={() => onTarget(null)} aria-label="Remove yourself from the race">
          ×
        </button>
      )}
    </form>
  );
}

