// What a report is about, from the page the reporter came from: a race, an athlete, an event
// or a competition, so the form can start filled in.

import { athleteAt, eventName, groupName, roundName, sexName } from "../data/format";
import type { AthleteSummary, CompetitionOut, Index, RaceSummary } from "../data/types";
import { match } from "../router";
import type { Ref } from "./report.ts";

export interface About {
  race?: RaceSummary;
  athlete?: AthleteSummary;
  competition?: CompetitionOut;
  /** How the page names what it shows, for a missing race: "Men's 400m", "Paris 2024". */
  label?: string;
}

export function aboutPage(index: Index, page: string): About {
  const url = new URL(page, "https://splits.invalid");
  const path = decodeURI(url.pathname);
  let params: Record<string, string> | null;
  if ((params = match("/races/*", path))) {
    const race = index.races.find((r) => r.id === params!.rest);
    return race ? { race, label: raceName(index, race) } : {};
  }
  if ((params = match("/athletes/:id", path))) {
    const athlete = athleteAt(index, params.id!);
    return athlete ? { athlete } : {};
  }
  if ((params = match("/events/:group", path))) {
    const sex = url.searchParams.get("sex");
    const group = groupName(index, params.group!);
    return { label: sex ? `${sexName(sex)}'s ${group.toLowerCase()}` : group };
  }
  const competition = index.competitions.find((c) => c.id === url.searchParams.get("competition"));
  return competition ? { competition, label: competition.name } : {};
}

/** "Men's 400m · Final · Paris 2024" */
export function raceName(index: Index, race: RaceSummary): string {
  const competition = index.competitions.find((c) => c.id === race.competition);
  return [eventName(index, race.event), roundName(race.round, race.heat), competition?.name]
    .filter(Boolean)
    .join(" · ");
}

export const raceRef = (index: Index, race: RaceSummary): Ref => ({ id: race.id, name: raceName(index, race) });
export const athleteRef = (athlete: AthleteSummary): Ref => ({ id: athlete.id, name: athlete.name });
