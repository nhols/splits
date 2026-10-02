// Run with `npm test` (Node's own test runner; Node strips the types).
import assert from "node:assert/strict";
import { test } from "node:test";
import { offered, passing, type Filters } from "./filters.ts";
import type { RaceSummary } from "./types.ts";

const race = (id: string, competition: string, discipline: string, date: string) =>
  ({ id, competition, discipline, date }) as RaceSummary;

const RACES = [
  race("a", "og-1968-mexico-city", "400m", "1968-10-18"),
  race("b", "og-1968-mexico-city", "800m", "1968-10-15"),
  race("c", "og-2024-paris", "400m", "2024-08-09"),
  race("d", "dl-2024-paris", "800m", "2024-07-07"),
];

test("a menu offers what the other filters leave, whatever its own is set to", () => {
  const filters: Filters = {
    year: (r) => r.date.startsWith("2024"),
    discipline: (r) => r.discipline === "400m",
  };
  assert.deepEqual(passing(RACES, filters).map((r) => r.id), ["c"]);
  // The event menu still offers the 800m of 2024; the year menu, the 400m's years.
  assert.deepEqual(passing(RACES, filters, "discipline").map((r) => r.discipline), ["400m", "800m"]);
  assert.deepEqual(passing(RACES, filters, "year").map((r) => r.date.slice(0, 4)), ["1968", "2024"]);
});

test("a filter not set lets every race through", () => {
  assert.equal(passing(RACES, { year: null, discipline: null }).length, RACES.length);
});

test("the value chosen stays in its menu when nothing is left for it", () => {
  const years = ["2024", "2016", "1968"];
  assert.deepEqual(offered(years, (y) => y, ["2024"], null), ["2024"]);
  assert.deepEqual(offered(years, (y) => y, ["2024"], "1968"), ["2024", "1968"]);
});
