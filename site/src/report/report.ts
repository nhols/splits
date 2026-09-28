// A report from the site, and the GitHub issue it becomes. Shared by the form (site/src) and
// the function that files it (site/functions/api/report.ts), so both check the same rules.
// Everything a reporter types is untrusted: it is length-limited, kept out of titles where it
// could mislead, and quoted so it cannot mention anyone or pass for the context below it.

export const KINDS = ["data", "race", "bug", "idea"] as const;
export type Kind = (typeof KINDS)[number];

export const LABELS: Record<Kind, string> = {
  data: "data-error",
  race: "race-request",
  bug: "site-bug",
  idea: "idea",
};
export const SITE_LABEL = "from-site";

/** What a wrong value is. */
export const FIELDS = ["split", "result", "place", "lane", "reaction", "athlete", "other"] as const;
export type Field = (typeof FIELDS)[number];

export const FIELD_NAMES: Record<Field, string> = {
  split: "A split",
  result: "A finishing time",
  place: "A place",
  lane: "A lane",
  reaction: "A reaction time",
  athlete: "The athlete's name or identity",
  other: "Something else",
};

/** A record the report is about: its ID in the dataset and how the site names it. */
export interface Ref {
  id: string;
  name: string;
}

export interface Report {
  kind: Kind;
  details: string;
  /** Wrong data. */
  field?: Field;
  race?: Ref;
  athlete?: Ref;
  point?: Ref;
  correct?: string;
  /** A missing race: where its documents are, and what it is. */
  analysisUrl?: string;
  resultsUrl?: string;
  raceName?: string;
  /** A missing race that replaces the source of one the site has. */
  replaces?: Ref;
  /** Wrong data, and a missing race: a page or document that shows the right value. */
  sourceUrl?: string;
  /** A site problem. */
  expected?: string;
  /** Where the report was made from, filled in by the site. */
  context: {
    page: string;
    builtAt: string;
    codeVersion: string;
    userAgent?: string;
    viewport?: string;
  };
}

const LIMITS = { short: 200, text: 5000, url: 2000 };

export class Invalid extends Error {}

/** Check an untrusted payload and return it as a report, or throw :class:`Invalid`. */
export function parseReport(input: unknown): Report {
  const o = object(input, "report");
  const kind = oneOf(o.kind, KINDS, "kind");
  const context = object(o.context, "context");
  const page = text(context.page, "page", LIMITS.url, true);
  if (!page.startsWith("/") || page.startsWith("//")) throw new Invalid("page must be a path on the site");
  const report: Report = {
    kind,
    details: text(o.details, "details", LIMITS.text, kind !== "data" && kind !== "race"),
    context: {
      page,
      builtAt: text(context.builtAt, "builtAt", LIMITS.short, true),
      codeVersion: text(context.codeVersion, "codeVersion", LIMITS.short, true),
      userAgent: optional(context.userAgent, (v) => text(v, "userAgent", LIMITS.short * 2)),
      viewport: optional(context.viewport, (v) => text(v, "viewport", LIMITS.short)),
    },
  };
  if (kind === "data") {
    report.field = oneOf(o.field, FIELDS, "field");
    report.race = optional(o.race, (v) => ref(v, "race"));
    report.athlete = optional(o.athlete, (v) => ref(v, "athlete"));
    report.point = optional(o.point, (v) => ref(v, "point"));
    report.correct = optional(o.correct, (v) => text(v, "correct", LIMITS.short));
    report.sourceUrl = optional(o.sourceUrl, (v) => url(v, "sourceUrl"));
    if (!report.race && !report.athlete && !report.details) throw new Invalid("say which race or athlete it is");
  }
  if (kind === "race") {
    report.analysisUrl = url(o.analysisUrl, "analysisUrl");
    report.resultsUrl = optional(o.resultsUrl, (v) => url(v, "resultsUrl"));
    report.raceName = optional(o.raceName, (v) => text(v, "raceName", LIMITS.short));
    report.replaces = optional(o.replaces, (v) => ref(v, "replaces"));
  }
  if (kind === "bug") {
    report.expected = optional(o.expected, (v) => text(v, "expected", LIMITS.text));
  }
  return report;
}

export interface Issue {
  title: string;
  body: string;
  labels: string[];
}

/** The GitHub issue a report is filed as; ``site`` is the site's address, for links back. */
export function issueFor(report: Report, site: string): Issue {
  return {
    title: clip(titleFor(report), 120),
    body: bodyFor(report, site.replace(/\/$/, "")),
    labels: [SITE_LABEL, LABELS[report.kind]],
  };
}

function titleFor(report: Report): string {
  switch (report.kind) {
    case "data": {
      const what = FIELD_NAMES[report.field!].replace(/^(A|The) /, "");
      const where = [report.race?.name, report.athlete?.name, report.point?.name].filter(Boolean);
      return `Wrong ${what.toLowerCase()}: ${where.join(" · ")}`;
    }
    case "race":
      return report.replaces
        ? `Better source: ${report.replaces.name}`
        : `Missing race: ${report.raceName || hostOf(report.analysisUrl!)}`;
    case "bug":
      return `Site problem: ${firstLine(report.details)}`;
    case "idea":
      return `Idea: ${firstLine(report.details)}`;
  }
}

function bodyFor(report: Report, site: string): string {
  const lines: string[] = [];
  const field = (label: string, value: string | undefined) => {
    if (value) lines.push(`**${label}:** ${inline(value)}`);
  };
  const link = (label: string, value: string | undefined) => {
    if (value) lines.push(`**${label}:** <${value}>`);
  };
  const record = (label: string, value: Ref | undefined, path?: string) => {
    if (value) lines.push(`**${label}:** ${inline(value.name)} (\`${code(value.id)}\`${path ? `, [on the site](${site}${path})` : ""})`);
  };

  if (report.kind === "data") {
    field("What is wrong", FIELD_NAMES[report.field!]);
    record("Race", report.race, report.race && `/races/${report.race.id}`);
    record("Athlete", report.athlete, report.athlete && `/athletes/${report.athlete.id}`);
    record("Timing point", report.point);
    field("Correct value", report.correct);
    link("Where it shows", report.sourceUrl);
  }
  if (report.kind === "race") {
    record("Replaces the source of", report.replaces, report.replaces && `/races/${report.replaces.id}`);
    field("Race", report.raceName);
    link("Race analysis (splits)", report.analysisUrl);
    link("Results", report.resultsUrl);
  }
  if (report.kind === "bug" || report.kind === "idea") link("Page", new URL(report.context.page, site + "/").href);
  if (report.details) {
    if (lines.length) lines.push("");
    lines.push(quote(report.details));
  }
  if (report.kind === "bug" && report.expected) {
    lines.push("", "**Expected:**", "", quote(report.expected));
  }

  // The context, for whoever picks the report up: exact IDs, and the build it was made on.
  const { details: _details, expected: _expected, ...rest } = report;
  lines.push(
    "",
    "<details><summary>Context</summary>",
    "",
    "```json",
    JSON.stringify(rest, null, 2).replaceAll("```", "'''"),
    "```",
    "",
    "</details>",
    "",
    "_Filed from the site's report form. The text above was written by a visitor._",
  );
  return lines.join("\n");
}

// ---- untrusted text --------------------------------------------------------------------------

/** Stop @mentions and #references from notifying anyone or linking elsewhere. */
function defuse(value: string): string {
  return value.replace(/([@#])(?=\w)/g, "$1​");
}

function inline(value: string): string {
  return defuse(value.replace(/\s+/g, " ").trim()).replace(/[<>*_`[\]]/g, "\\$&");
}

function quote(value: string): string {
  return defuse(value.trim())
    .split(/\r?\n/)
    .map((line) => `> ${line}`)
    .join("\n");
}

function code(value: string): string {
  return value.replaceAll("`", "");
}

function firstLine(value: string): string {
  return defuse(value.trim().split(/\r?\n/)[0] ?? "");
}

function clip(value: string, length: number): string {
  return value.length <= length ? value : value.slice(0, length - 1).trimEnd() + "…";
}

function hostOf(value: string): string {
  return new URL(value).host;
}

// ---- checking the payload ----------------------------------------------------------------------

function object(value: unknown, name: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Invalid(`${name} is missing`);
  return value as Record<string, unknown>;
}

function text(value: unknown, name: string, limit: number, required = false): string {
  if (value === undefined || value === null || value === "") {
    if (required) throw new Invalid(`${name} is required`);
    return "";
  }
  if (typeof value !== "string") throw new Invalid(`${name} must be text`);
  const trimmed = value.trim();
  if (required && !trimmed) throw new Invalid(`${name} is required`);
  if (trimmed.length > limit) throw new Invalid(`${name} is too long (at most ${limit} characters)`);
  return trimmed;
}

function url(value: unknown, name: string): string {
  const raw = text(value, name, LIMITS.url, true);
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Invalid(`${name} is not a link`);
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") throw new Invalid(`${name} is not a web link`);
  return parsed.href;
}

function ref(value: unknown, name: string): Ref {
  const o = object(value, name);
  const id = text(o.id, `${name}.id`, LIMITS.short, true);
  if (!/^[\w./-]+$/.test(id)) throw new Invalid(`${name}.id is not an ID`);
  return { id, name: text(o.name, `${name}.name`, LIMITS.short, true) };
}

function oneOf<T extends string>(value: unknown, options: readonly T[], name: string): T {
  if (typeof value !== "string" || !options.includes(value as T)) throw new Invalid(`${name} is not one of ${options.join(", ")}`);
  return value as T;
}

function optional<T>(value: unknown, read: (value: unknown) => T): T | undefined {
  if (value === undefined || value === null || value === "") return undefined;
  const result = read(value);
  return result === "" ? undefined : result;
}
