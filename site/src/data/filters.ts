// Filters over races, and the values their menus offer. Each menu offers only what the other
// filters leave: the values of the races every other filter lets through.

import type { RaceSummary } from "./types";

/** A page's filters by name (one per menu or control): a test races must pass, or null when
 * the filter is not set. */
export type Filters = Record<string, ((race: RaceSummary) => boolean) | null>;

/** Whether ``race`` passes every filter but the one named ``except``. */
export function passes(race: RaceSummary, filters: Filters, except?: string): boolean {
  return Object.entries(filters).every(([name, test]) => name === except || !test || test(race));
}

/** The races every filter lets through but the one named ``except``: a menu's own filter is
 * left out, so it offers every value the others allow, not just the one chosen. */
export function passing(races: RaceSummary[], filters: Filters, except?: string): RaceSummary[] {
  return races.filter((race) => passes(race, filters, except));
}

/** The values a menu offers, in their own order: those the races left have, and the value
 * chosen, kept even when nothing is left for it, so the menu can still show it. */
export function offered<T>(values: T[], id: (value: T) => string, left: Iterable<string>, chosen: string | null): T[] {
  const have = new Set(left);
  return values.filter((value) => have.has(id(value)) || id(value) === chosen);
}
