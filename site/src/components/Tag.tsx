// A mark printed beside a result (PB, TR16.8, YC). Pointing at it, or tapping it, shows what it
// means just above it, over the page, so nothing moves.

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useIndex } from "../data/load";
import "./tag.css";

/** Room between the meaning and the mark, and between the meaning and the window's edges. */
const GAP = 6;
const MARGIN = 8;

export function Tag({ value }: { value: string }) {
  const index = useIndex();
  const meanings = useMemo(() => new Map(index.annotations.map((a) => [a.value, a.meaning])), [index]);
  const meaning = meanings.get(value);
  return meaning ? <ExplainedTag value={value} meaning={meaning} /> : <span className="tag">{value}</span>;
}

function ExplainedTag({ value, meaning }: { value: string; meaning: string }) {
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [place, setPlace] = useState<{ left: number; top: number } | null>(null);
  const button = useRef<HTMLButtonElement>(null);
  const tip = useRef<HTMLSpanElement>(null);
  const id = useId();
  const open = hovered || pinned;

  // Centred above the mark (below it, when there is no room above), and inside the window.
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

  // Closes on a tap or click elsewhere, on Escape, and once the page scrolls away from it.
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
        className={`tag tag-button${open ? " on" : ""}`}
        aria-describedby={open ? id : undefined}
        onPointerEnter={(event) => event.pointerType === "mouse" && setHovered(true)}
        onPointerLeave={(event) => event.pointerType === "mouse" && setHovered(false)}
        onClick={() => setPinned(!pinned)}
      >
        {value}
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
            {meaning}
          </span>,
          document.body,
        )}
    </>
  );
}
