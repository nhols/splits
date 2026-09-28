// The race replay with you in it: type a time and a ghost runs in an empty lane, on the typical
// splits for that time (see track/model.ts), as do athletes whose splits were not published. Your time is kept per event (in this browser, and
// in the link), so you appear in every race of the event until you remove yourself.

import { Suspense, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { time } from "../../data/format";
import { useEvent, useIndex } from "../../data/load";
import { useParam } from "../../router";
import { freeLanes, makeGhost, needsModel, parseTime, withModelledRunners, type Basis, type Ghost } from "../../track/model";
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

  if (target === null && !needsModel(props.race)) return <Replay {...props} ghost={null} basis={null} controls={form} />;
  return (
    <Suspense fallback={<Replay {...props} ghost={null} basis={null} controls={form} />}>
      <Modelled {...props} target={target} lane={lane} run={run} form={form} />
    </Suspense>
  );
}

/** The race with its modelled runners: you, and anyone whose splits were not published. */
function Modelled({
  target,
  lane,
  run,
  form,
  ...props
}: Props & { target: number | null; lane: number; run: number; form: ReactNode }) {
  const index = useIndex();
  const event = useEvent(props.event);
  const modelled = useMemo(
    () => (needsModel(props.race) ? withModelledRunners(props.race, () => event, index.races) : { race: props.race, basis: null }),
    [props.race, event, index],
  );
  const ghost = useMemo(
    () => (target === null ? null : makeGhost(modelled.race, target, lane, event, index.races)),
    [modelled.race, target, lane, event, index],
  );
  // A new run or time starts the race again, so you can watch yourself run it.
  return <Replay key={`${run}/${target}`} {...props} race={modelled.race} ghost={ghost} basis={modelled.basis} controls={form} />;
}

function Replay({
  race,
  ghost,
  basis,
  controls,
  label,
  highlight,
  onHighlight,
  stretch,
  onStretch,
  simple,
}: Props & { ghost: Ghost | null; basis: Basis | null; controls: ReactNode }) {
  const withGhost = useMemo(() => (ghost ? { ...race, runners: [...race.runners, ghost.runner] } : race), [race, ghost]);
  const notes = [
    ghost && `You: ${describe(ghost.basis, ghost.runner.lane)}`,
    basis && `Runners without published splits: ${describe(basis, null)}`,
  ].filter((note): note is string => Boolean(note));
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

/** What a modelled runner's splits rest on, for the explainer. */
export function describe(basis: Basis | null, lane: number | null): string {
  const where = lane === null ? "" : `lane ${lane}, `;
  if (!basis) return `${where}an even pace: too few runs to model splits.`;
  return (
    `${where}modelled ${basis.every} from ${basis.runs} runs ` +
    `(${time(basis.fastest)}–${time(basis.slowest)})${basis.extrapolated ? ", extrapolated" : ""}.`
  );
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

