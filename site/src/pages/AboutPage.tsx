// What the project is, and how it works, for readers who are not statisticians.

import { count } from "../data/format";
import { useIndex } from "../data/load";
import { Link } from "../router";
import "./pages.css";
import "./about.css";

export function AboutPage() {
  const index = useIndex();
  return (
    <div className="page stack" style={{ "--gap": "28px" } as React.CSSProperties}>
      <header className="page-header">
        <h1>About</h1>
        <p className="lede">
          Splits collects the split times of elite track races, from the 100 m to the 10,000 m, so athletes
          and coaches can see how the best in the world actually run them.
        </p>
      </header>

      <div className="prose about">
        <p>
          It holds {count(index.build.splits)} splits from {count(index.build.races)} races: Diamond League
          meetings since 2021, the Paris Olympics and Olympic finals back to 1932, recent World
          Championships, and many world-record runs.
        </p>

        <h2>Where the times come from</h2>
        <p>
          After a big race, the timing company (usually OMEGA) publishes a PDF with each athlete's time at
          every 10 m, 50 m, 100 m, hurdle or lap. Splits reads those documents and keeps, for every number,
          the page and the exact words it came from. Each race links to its original documents, so any time
          can be checked at source.
        </p>

        <h2>How it is checked</h2>
        <p>
          A race usually has two documents: the result and the split analysis. Where both give the same
          fact, they must agree. Official documents do contain mistakes, such as a split slower than the one
          after it; these are kept as published but flagged, and left out of averages and charts.
        </p>

        <h2>The race replay</h2>
        <p>
          Every race can be watched again on a track drawn to official dimensions. Each runner passes every
          timing point at exactly their published time; between points, the motion is smoothed. Runners
          stay in their lanes as long as the rules say, and after the break they're drawn on the inside,
          moving out only to pass.
        </p>

        <h2>Racing a ghost</h2>
        <p>
          Elite athletes pace a race in much the same proportions whatever their finishing time: a 44-second
          and a 46-second 400 m reach halfway at nearly the same share of the race. From every run in the
          data, Splits learns those proportions, so it can produce typical splits for any time. That lets you
          enter a time and race the field as a ghost, and lets runners whose splits weren't published take
          part too. Ghosts are drawn dashed and never count as real data.
        </p>

        <h2>Comparing runs</h2>
        <p>
          Event pages give typical splits and a planner for a target time. Athlete pages set each run against
          others who finished in the same time. <Link to="/compare">Compare</Link> puts any runs over the same
          distance side by side on the track, from any race, men's and women's alike.
        </p>

        <h2>The data</h2>
        <p>
          Everything is free to download from the <Link to="/data">Data</Link> page. If you spot a mistake or
          know of a race that's missing, <Link to="/report?from=%2Fabout">let us know</Link>.
        </p>
      </div>
    </div>
  );
}
