// A long list draws its first rows at once and the rest as the reader scrolls towards them, so a
// page of a thousand rows appears as fast as one of a hundred.

import { useState, type RefCallback } from "react";

interface Shown {
  key: string;
  limit: number;
}

/** The first `step` items, and more as the element given `sentinel` (placed after the list)
 * nears the viewport. Back to the first `step` whenever `key` (e.g. the filters) changes. How
 * many are shown is kept in the history entry, so going back to the list draws as many rows as
 * before and the browser can return to where the reader was. One such list per page. */
export function useIncremental<T>(
  items: readonly T[],
  key: string,
  step = 100,
): { shown: readonly T[]; more: boolean; sentinel: RefCallback<HTMLElement> } {
  const [state, setState] = useState<Shown>(() => {
    const saved = (window.history.state as { shown?: Shown } | null)?.shown;
    return saved?.key === key ? saved : { key, limit: step };
  });
  const limit = state.key === key ? state.limit : step;
  const sentinel: RefCallback<HTMLElement> = (element) => {
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        const next = { key, limit: limit + step };
        window.history.replaceState({ ...window.history.state, shown: next }, "");
        setState(next);
      },
      { rootMargin: "1500px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  };
  return { shown: items.slice(0, limit), more: items.length > limit, sentinel };
}
