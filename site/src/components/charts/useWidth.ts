import { useCallback, useLayoutEffect, useRef, useState, type RefObject } from "react";

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

/** The rendered height of an element, kept current as it resizes. */
export function useHeight<T extends HTMLElement>(initial = 480): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [height, setHeight] = useState(initial);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    setHeight(element.getBoundingClientRect().height);
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setHeight(entry.contentRect.height);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, height];
}

/** The rendered size of an element, kept current as it resizes; the element may come and go
 * (the ref is a callback, so it follows whichever element is rendered). */
export function useSize<T extends HTMLElement>(): [(element: T | null) => void, { width: number; height: number }] {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((element: T | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!element) return;
    const box = element.getBoundingClientRect();
    setSize({ width: box.width, height: box.height });
    observer.current = new ResizeObserver(([entry]) => {
      if (entry) setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.current.observe(element);
  }, []);
  return [ref, size];
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
