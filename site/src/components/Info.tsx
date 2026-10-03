// A small "i" button that opens a short explanation in the middle of the screen. Clicking the
// backdrop, the close button or pressing Escape closes it.

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./info.css";

export function Info({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const escape = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("keydown", escape);
      button.current?.focus();
    };
  }, [open]);
  return (
    <>
      <button
        ref={button}
        type="button"
        className={`info-button${open ? " on" : ""}`}
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
      >
        i
      </button>
      {open &&
        createPortal(
          <div className="info-backdrop" onPointerDown={(event) => event.target === event.currentTarget && setOpen(false)}>
            <div className="info-panel" id={id} role="dialog" aria-modal="true" aria-label={label} tabIndex={-1} ref={panel}>
              <button type="button" className="info-close" aria-label="Close" onClick={() => setOpen(false)}>
                ×
              </button>
              {children}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}

/** How typical splits are modelled, for the split planner. */
export function ModelExplainer({ basis }: { basis?: ReactNode }) {
  return (
    <>
      <strong>Modelled splits</strong>
      <span>
        Elite pacing barely depends on level: a 400m runner reaches 200m in about 47.5% of their
        finishing time, whatever that time. At each timing point, the share of the finishing time
        is fitted as a straight line in the finishing time, across every run of the event with
        splits (indoors and outdoors apart, heats and finals apart), then applied to the time.
      </span>
      <span>
        Tested on runs left out of the fit, it gets 400m splits right to about 0.25s, against about
        1s for an even pace. Beyond the range of the runs, the shares stay as at its edge.
      </span>
      {basis && <span className="info-basis">{basis}</span>}
    </>
  );
}

/** How the replay moves runners between their published times. */
export function MotionExplainer() {
  return (
    <>
      <strong>How runners move</strong>
      <span>
        Each runner passes every published split at exactly its time. Between splits, in events up
        to 800m, they move as runners in that event typically do: the median share of the race
        used up at each distance, from every run timed at the event’s finest points, bent to pass
        through the runner’s own splits. A runner with only a finishing time runs that typical
        race. Above 800m the curve runs smoothly through the splits alone. Either way runners
        accelerate from the blocks after their reaction time (the event’s typical one where theirs
        wasn’t published), and their speed changes gradually rather than jumping at a split.
        Positions between splits are estimates, and the standings rank runners by them; the times
        shown are the published splits.
      </span>
      <span>Lanes, staggers and hurdles follow World Athletics dimensions; indoor tracks are a typical 200m oval.</span>
      <span>
        Out of lanes (after the 800m break line, or from a waterfall start) the splits say how far
        along each runner is, not where across the track. Runners are drawn as races are run: in
        lane 1, in single file, moving out only to pass or when someone is alongside, and back in
        once clear.
      </span>
      <span>
        <strong>Follow</strong> (or press F) closes in on the leaders and moves with them; choose a
        name in the standings to follow that runner instead.
      </span>
      <span>
        <strong>The dashed runner</strong> is you, when you enter a time to race: you run as an
        athlete with only a finishing time does, the event’s typical race in your time. Your
        modelled times are marked ≈ in the standings and never appear in the tables.
      </span>
    </>
  );
}
