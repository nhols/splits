// A small router over the History API. Navigation runs inside a transition, so while the
// next page's data loads the current page stays on screen instead of flashing a fallback.

import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useState,
  type AnchorHTMLAttributes,
  type MouseEvent,
  type ReactNode,
} from "react";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export interface Location {
  path: string;
  params: URLSearchParams;
}

function read(): Location {
  const raw = window.location.pathname;
  const path = raw.startsWith(BASE) ? raw.slice(BASE.length) || "/" : raw;
  return { path: decodeURI(path), params: new URLSearchParams(window.location.search) };
}

const listeners = new Set<() => void>();

export function navigate(to: string, { replace = false, keepScroll = false } = {}): void {
  const url = BASE + to;
  if (replace) window.history.replaceState(null, "", url);
  else window.history.pushState(null, "", url);
  listeners.forEach((listener) => listener());
  if (!keepScroll) window.scrollTo({ top: 0 });
}

const LocationContext = createContext<Location>(read());

export function RouterProvider({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState(read);
  useEffect(() => {
    const update = () => startTransition(() => setLocation(read()));
    listeners.add(update);
    window.addEventListener("popstate", update);
    return () => {
      listeners.delete(update);
      window.removeEventListener("popstate", update);
    };
  }, []);
  return <LocationContext.Provider value={location}>{children}</LocationContext.Provider>;
}

export function useLocation(): Location {
  return useContext(LocationContext);
}

/** Read and write one query parameter, keeping the others. */
export function useParam(name: string): [string | null, (value: string | null) => void] {
  const { path, params } = useLocation();
  const set = (value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "") next.delete(name);
    else next.set(name, value);
    const query = next.toString();
    navigate(path + (query ? `?${query}` : ""), { replace: true, keepScroll: true });
  };
  return [params.get(name), set];
}

export function href(to: string): string {
  return BASE + to;
}

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string };

export function Link({ to, onClick, children, ...rest }: LinkProps) {
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      rest.target
    ) {
      return;
    }
    event.preventDefault();
    navigate(to);
  };
  return (
    <a href={href(to)} onClick={handle} {...rest}>
      {children}
    </a>
  );
}

/** Match ``path`` against a pattern such as ``/races/*`` or ``/athletes/:id``. */
export function match(pattern: string, path: string): Record<string, string> | null {
  if (pattern.endsWith("/*")) {
    const prefix = pattern.slice(0, -2);
    return path.startsWith(prefix + "/") ? { rest: path.slice(prefix.length + 1) } : null;
  }
  const want = pattern.split("/");
  const have = path.replace(/\/$/, "").split("/");
  if (want.length !== have.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < want.length; i++) {
    const w = want[i]!;
    const h = have[i]!;
    if (w.startsWith(":")) params[w.slice(1)] = h;
    else if (w !== h) return null;
  }
  return params;
}
