// Formatting and naming. Times keep hundredths; minutes appear only past 60 s.

import type { DisciplineOut, Index } from "./types";

export function time(seconds: number | null | undefined, digits = 2): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "–";
  if (seconds < 60) return seconds.toFixed(digits);
  const minutes = Math.floor(seconds / 60);
  const rest = seconds - minutes * 60;
  return `${minutes}:${rest.toFixed(digits).padStart(digits + 3, "0")}`;
}

/** Whether a time was printed to the tenth (``22.4``, ``2:21.0``) rather than the hundredth,
 * so that it is shown as printed. */
export function printedDigits(text: string | null | undefined): number {
  return /^\D*(?:\d+:)*\d+[.,]\d\D*$/.test(text ?? "") ? 1 : 2;
}

/** A time behind (or ahead), to the decimals the times it compares were printed with. */
export function gap(seconds: number, digits = 2): string {
  if (Math.abs(seconds) < 0.5 * 10 ** -digits) return (0).toFixed(digits);
  return `${seconds > 0 ? "+" : "−"}${Math.abs(seconds).toFixed(digits)}`;
}

export function speed(mps: number): string {
  return mps.toFixed(2);
}

export function percent(share: number, digits = 1): string {
  return `${(share * 100).toFixed(digits)}%`;
}

export function count(n: number): string {
  return n.toLocaleString("en-GB");
}

const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");

export function date(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTHS[(month ?? 1) - 1]} ${year}`;
}

export function dateRange(start: string, end: string): string {
  const [y1, m1, d1] = start.split("-").map(Number);
  const [y2, m2, d2] = end.split("-").map(Number);
  if (y1 === y2 && m1 === m2) return `${d1}–${d2} ${MONTHS[(m2 ?? 1) - 1]} ${y2}`;
  if (y1 === y2) return `${d1} ${MONTHS[(m1 ?? 1) - 1]} – ${d2} ${MONTHS[(m2 ?? 1) - 1]} ${y2}`;
  return `${date(start)} – ${date(end)}`;
}

export function roundName(round: string, heat: number | null): string {
  const names: Record<string, string> = {
    preliminary: "Preliminary",
    heat: "Heat",
    repechage: "Repechage",
    "quarter-final": "Quarter-final",
    "semi-final": "Semi-final",
    final: "Final",
  };
  const name = names[round] ?? round;
  return heat ? `${name} ${heat}` : name;
}

export function roundGroup(round: string): string {
  return round === "final" ? "Finals" : round === "semi-final" ? "Semi-finals" : "Heats";
}

export function sexName(sex: string): string {
  return sex === "men" ? "Men" : sex === "women" ? "Women" : "Mixed";
}

export function disciplineName(discipline: DisciplineOut | undefined, fallback = ""): string {
  if (!discipline) return fallback;
  if (discipline.kind === "hurdles") return `${discipline.distance}m hurdles`;
  if (discipline.kind === "steeplechase") return `${discipline.distance}m steeplechase`;
  if (discipline.id === "mile") return "mile";
  return discipline.shortName;
}

/** "Women's 400m hurdles" */
export function eventName(index: Index, event: string): string {
  const [disciplineId, sex] = splitEvent(event);
  const discipline = index.disciplines.find((d) => d.id === disciplineId);
  const owner = sex === "men" ? "Men's" : sex === "women" ? "Women's" : "Mixed";
  return `${owner} ${disciplineName(discipline, disciplineId)}`;
}

export function splitEvent(event: string): [string, string] {
  const cut = event.lastIndexOf("-");
  return [event.slice(0, cut), event.slice(cut + 1)];
}

/** How a race was timed, by its first split: ``10m``, ``50m``, ``100m``, ``200m``, ``hurdles``
 * (a time at every hurdle) or ``none``. */
export function splitType(points: string[]): string {
  if (!points.length) return "none";
  if (points.some((point) => /^h\d+$/i.test(point))) return "hurdles";
  return points[0]!;
}

export function splitTypeName(type: string): string {
  return type === "none" ? "No splits" : type === "hurdles" ? "Every hurdle" : `Every ${type}`;
}

export function settingName(setting: string): string {
  return setting === "indoor" ? "Indoor" : setting === "road" ? "Road" : "Outdoor";
}

export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

export function bytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
