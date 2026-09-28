// Run with `npm test`. Nothing here reaches GitHub or Cloudflare: fetch is faked.
import assert from "node:assert/strict";
import { test } from "node:test";
import { fileReport } from "./file.ts";
import { Invalid, issueFor, parseReport } from "./report.ts";

const context = { page: "/races/og-2024-paris/400m-men/final", builtAt: "2026-09-27T20:11:00Z", codeVersion: "ab9e34a" };
const SITE = "https://track-splits.pages.dev";

const wrongSplit = {
  kind: "data",
  field: "split",
  race: { id: "og-2024-paris/400m-men/final", name: "Men's 400m · Final · Paris 2024" },
  athlete: { id: "quincy-hall", name: "Quincy Hall" },
  point: { id: "200m", name: "200m" },
  correct: "21.36",
  details: "",
  context,
};

test("a wrong split becomes an issue naming the race, athlete and point, with their IDs", () => {
  const issue = issueFor(parseReport(wrongSplit), SITE);
  assert.equal(issue.title, "Wrong split: Men's 400m · Final · Paris 2024 · Quincy Hall · 200m");
  assert.deepEqual(issue.labels, ["from-site", "data-error"]);
  assert.match(issue.body, /`og-2024-paris\/400m-men\/final`, \[on the site\]\(https:\/\/track-splits\.pages\.dev\/races\/og-2024-paris\/400m-men\/final\)/);
  assert.match(issue.body, /\*\*Correct value:\*\* 21\.36/);
  assert.match(issue.body, /"codeVersion": "ab9e34a"/);
});

test("wrong data must say which race or athlete it is about, or describe where", () => {
  assert.throws(() => parseReport({ ...wrongSplit, race: undefined, athlete: undefined }), Invalid);
  parseReport({ ...wrongSplit, race: undefined, athlete: undefined, details: "Oslo 2025, the 1500m" });
});

test("a missing race needs a web link to its race analysis", () => {
  const race = { kind: "race", details: "", analysisUrl: "https://example.org/rs5.pdf", context };
  assert.equal(issueFor(parseReport(race), SITE).title, "Missing race: example.org");
  assert.throws(() => parseReport({ ...race, analysisUrl: "" }), Invalid);
  assert.throws(() => parseReport({ ...race, analysisUrl: "javascript:alert(1)" }), Invalid);
});

test("a better source for a race the site has names that race", () => {
  const issue = issueFor(
    parseReport({
      kind: "race",
      details: "",
      analysisUrl: "https://example.org/rs5.pdf",
      replaces: { id: "og-2024-paris/400m-men/final", name: "Men's 400m · Final · Paris 2024" },
      context,
    }),
    SITE,
  );
  assert.equal(issue.title, "Better source: Men's 400m · Final · Paris 2024");
  assert.deepEqual(issue.labels, ["from-site", "race-request"]);
});

test("site problems and ideas need a description, and link the page they came from", () => {
  assert.throws(() => parseReport({ kind: "bug", details: "  ", context }), Invalid);
  const issue = issueFor(parseReport({ kind: "idea", details: "Show 60m splits\nplease", context }), SITE);
  assert.equal(issue.title, "Idea: Show 60m splits");
  assert.match(issue.body, /\*\*Page:\*\* <https:\/\/track-splits\.pages\.dev\/races\/og-2024-paris\/400m-men\/final>/);
});

test("visitors' text cannot mention people, break out of its quote, or point the page elsewhere", () => {
  const issue = issueFor(parseReport({ kind: "bug", details: "cc @nhols\nsee #12", context }), SITE);
  assert.ok(!/@nhols/.test(issue.body) && !/ #12/.test(issue.body));
  assert.match(issue.body, /^> cc @​nhols\n> see #​12$/m);
  assert.throws(() => parseReport({ kind: "bug", details: "x", context: { ...context, page: "//evil.example/x" } }), Invalid);
  assert.throws(() => parseReport({ ...wrongSplit, race: { id: "a b", name: "x" } }), Invalid);
  assert.throws(() => parseReport({ kind: "idea", details: "x".repeat(5001), context }), Invalid);
});

// ---- filing --------------------------------------------------------------------------------------

const env = { GITHUB_TOKEN: "token", GITHUB_REPO: "nhols/splits", TURNSTILE_SECRET_KEY: "secret" };

function fakeFetch(turnstile: boolean, github: number = 201) {
  const calls: { url: string; body: unknown }[] = [];
  const fetcher = (async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body });
    if (url.includes("turnstile")) return Response.json({ success: turnstile });
    if (github !== 201) return new Response("nope", { status: github });
    return Response.json({ number: 7, html_url: "https://github.com/nhols/splits/issues/7" }, { status: 201 });
  }) as typeof fetch;
  return { fetcher, calls };
}

const post = (body: unknown) =>
  new Request(`${SITE}/api/report`, { method: "POST", body: JSON.stringify(body) });

test("a verified report is filed as an issue and its link returned", async () => {
  const { fetcher, calls } = fakeFetch(true);
  const response = await fileReport(post({ report: wrongSplit, turnstile: "ok" }), env, fetcher);
  assert.equal(response.status, 201);
  assert.deepEqual(await response.json(), { number: 7, url: "https://github.com/nhols/splits/issues/7" });
  assert.equal(calls[1]!.url, "https://api.github.com/repos/nhols/splits/issues");
  assert.deepEqual(JSON.parse(calls[1]!.body as string).labels, ["from-site", "data-error"]);
});

test("nothing is filed without a passing Turnstile check", async () => {
  const { fetcher, calls } = fakeFetch(false);
  assert.equal((await fileReport(post({ report: wrongSplit, turnstile: "bad" }), env, fetcher)).status, 403);
  assert.equal((await fileReport(post({ report: wrongSplit }), env, fetcher)).status, 403);
  assert.ok(calls.every((call) => !call.url.includes("api.github.com")));
});

test("invalid reports, missing settings and GitHub failures are answered, not thrown", async () => {
  assert.equal((await fileReport(post({ report: { kind: "nope" }, turnstile: "ok" }), env, fakeFetch(true).fetcher)).status, 422);
  assert.equal((await fileReport(post({ report: wrongSplit, turnstile: "ok" }), {}, fakeFetch(true).fetcher)).status, 503);
  assert.equal((await fileReport(post({ report: wrongSplit, turnstile: "ok" }), env, fakeFetch(true, 401).fetcher)).status, 502);
});
