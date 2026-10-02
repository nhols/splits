// The series menu (every Olympic Games at once, say) and the competition menu, each offering
// what the page's other filters leave.

import { offered, passing, type Filters } from "../data/filters";
import { useIndex } from "../data/load";
import type { RaceSummary } from "../data/types";
import { useParam } from "../router";
import { Select } from "./ui";

/** The series and competition chosen (``?series=``, ``?competition=``), as filters. */
export function useCompetitionFilters(): Filters {
  const index = useIndex();
  const [series] = useParam("series");
  const [competition] = useParam("competition");
  const seriesOf = new Map(index.competitions.map((c) => [c.id, c.series]));
  return {
    series: series ? (race) => seriesOf.get(race.competition) === series : null,
    competition: competition ? (race) => race.competition === competition : null,
  };
}

/** The two menus, over ``races`` (the page's) and ``filters`` (all of the page's). */
export function CompetitionMenus({ races, filters }: { races: RaceSummary[]; filters: Filters }) {
  const index = useIndex();
  const [series, setSeries] = useParam("series");
  const [competition, setCompetition] = useParam("competition");
  const seriesOf = new Map(index.competitions.map((c) => [c.id, c.series]));
  const seriesLeft = passing(races, filters, "series").flatMap((r) => seriesOf.get(r.competition) ?? []);
  const competitionsLeft = passing(races, filters, "competition").map((r) => r.competition);
  return (
    <>
      <Select
        label="Series"
        value={series ?? ""}
        onChange={(v) => setSeries(v || null)}
        options={[
          { value: "", label: "All series" },
          ...offered(index.series, (s) => s.id, seriesLeft, series).map((s) => ({ value: s.id, label: s.shortName })),
        ]}
      />
      <Select
        label="Competition"
        value={competition ?? ""}
        onChange={(v) => setCompetition(v || null)}
        options={[
          { value: "", label: "All competitions" },
          ...offered(index.competitions, (c) => c.id, competitionsLeft, competition).map((c) => ({
            value: c.id,
            label: c.name,
          })),
        ]}
      />
    </>
  );
}
