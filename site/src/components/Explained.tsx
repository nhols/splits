// Something on the page that says what it means: pointing at it, or tapping it on a touch screen,
// shows the explanation just above it, over the page, so nothing moves. It opens at once, unlike
// the browser's own tooltips, and closes on a tap elsewhere, on Escape or once the page scrolls.

import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { WarningIcon } from "./ui";
import "./tag.css";

/** Room between the explanation and the thing, and between the explanation and the window's edges. */
const GAP = 6;
const MARGIN = 8;

export function Explained({ explanation, className, children }: { explanation: ReactNode; className?: string; children: ReactNode }) {
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null);
  const button = useRef<HTMLButtonElement>(null);
  const tip = useRef<HTMLSpanElement>(null);
  const id = useId();
  const open = hovered || pinned;

  // Centred above the thing (below it, when there is no room above), and inside the window.
  useLayoutEffect(() => {
    if (!open || !button.current || !tip.current) return;
    const mark = button.current.getBoundingClientRect();
    const { offsetWidth: width, offsetHeight: height } = tip.current;
    const right = document.documentElement.clientWidth - MARGIN - width;
    const above = mark.top - GAP - height;
    setPlace({
      left: Math.max(MARGIN, Math.min(mark.left + mark.width / 2 - width / 2, right)),
      top: above < MARGIN ? mark.bottom + GAP : above,
    });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = () => {
      setHovered(false);
      setPinned(false);
    };
    const outside = (event: PointerEvent) => {
      if (!(event.target instanceof Node && button.current?.contains(event.target))) close();
    };
    const escape = (event: KeyboardEvent) => event.key === "Escape" && close();
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  return (
    <>
      <button
        ref={button}
        type="button"
        className={`explained${className ? ` ${className}` : ""}${open ? " on" : ""}`}
        aria-describedby={open ? id : undefined}
        onPointerEnter={(event) => event.pointerType === "mouse" && setHovered(true)}
        onPointerLeave={(event) => event.pointerType === "mouse" && setHovered(false)}
        onClick={(event) => {
          // Inside a row that opens something when clicked, a tap here only explains.
          event.stopPropagation();
          setPinned(!pinned);
        }}
      >
        {children}
      </button>
      {open &&
        createPortal(
          <span
            ref={tip}
            role="tooltip"
            id={id}
            className="tag-tip"
            style={place ? { left: place.left, top: place.top } : { visibility: "hidden" }}
          >
            {explanation}
          </span>,
          document.body,
        )}
    </>
  );
}

/** What a suspect time says where no check's own words are to hand. */
export const SUSPECT = "Flagged as suspect by a check: shown as published, but left out of comparisons, charts and the replay.";

/** A time a check marked as suspect: shown as published, struck through, saying why on hover or tap. */
export function SuspectTime({ children, why = SUSPECT }: { children: ReactNode; why?: ReactNode }) {
  return (
    <Explained className="suspect-time" explanation={why}>
      <WarningIcon />
      {children}
    </Explained>
  );
}
