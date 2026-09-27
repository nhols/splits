import { useLayoutEffect, useRef, useState, type RefObject } from "react";

/** The rendered width of an element, kept current as it resizes. */
export function useWidth<T extends HTMLElement>(initial = 640): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(initial);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.getBoundingClientRect().width);
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

/** Spread labels vertically so none overlap, keeping each as close to its wish as possible. */
export function spreadLabels(
  wishes: { id: string; y: number }[],
  gap: number,
  top: number,
  bottom: number,
): Map<string, number> {
  const sorted = [...wishes].sort((a, b) => a.y - b.y);
  const ys = sorted.map((w) => Math.min(Math.max(w.y, top), bottom));
  for (let i = 1; i < ys.length; i++) ys[i] = Math.max(ys[i]!, ys[i - 1]! + gap);
  const overflow = (ys[ys.length - 1] ?? bottom) - bottom;
  if (overflow > 0) {
    for (let i = ys.length - 1; i >= 0; i--) {
      ys[i] = i === ys.length - 1 ? ys[i]! - overflow : Math.min(ys[i]!, ys[i + 1]! - gap);
    }
    for (let i = 0; i < ys.length; i++) ys[i] = Math.max(ys[i]!, top + i * gap);
  }
  return new Map(sorted.map((w, i) => [w.id, ys[i]!]));
}
