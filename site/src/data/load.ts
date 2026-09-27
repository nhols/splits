// Loading the static data files written by `splits build`. Requests are cached by path, so
// every component can ask for what it needs and `use()` it under a <Suspense> boundary.

import { use } from "react";
import type { EventData, Index, RaceData } from "./types";

const cache = new Map<string, Promise<unknown>>();

export function fetchJson<T>(path: string): Promise<T> {
  let request = cache.get(path) as Promise<T> | undefined;
  if (!request) {
    request = fetch(`${import.meta.env.BASE_URL}data/${path}`).then((response) => {
      if (!response.ok) throw new Error(`Could not load ${path} (${response.status})`);
      return response.json() as Promise<T>;
    });
    request.catch(() => cache.delete(path));
    cache.set(path, request);
  }
  return request;
}

export const useIndex = (): Index => use(fetchJson<Index>("index.json"));

export const useEvent = (event: string): EventData =>
  use(fetchJson<EventData>(`events/${event}.json`));

export const useRace = (race: string): RaceData => use(fetchJson<RaceData>(`races/${race}.json`));

export const dataUrl = (path: string): string => `${import.meta.env.BASE_URL}data/${path}`;

// The table exports and database are too large for some static hosts, so they can be served
// from elsewhere: VITE_DOWNLOADS_URL, or else alongside the site's data.
const DOWNLOADS = (import.meta.env.VITE_DOWNLOADS_URL || dataUrl("downloads")).replace(
  /\/?$/,
  "/",
);

export const downloadUrl = (file: string): string => DOWNLOADS + file;
