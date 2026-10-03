// What the project is, and how it works, for readers who are not statisticians: where the times
// come from, how they are checked, the track the replay draws, the race model (how races are
// typically run), and how it fills the gaps between a runner's splits.

import { Suspense } from "react";
import { Loading } from "../components/ui";
import { count, time } from "../data/format";
import { useIndex } from "../data/load";
import type { EventOut, Index } from "../data/types";
import { Link } from "../router";
import { AboutNav } from "./about/AboutNav";
import { RaceModelDiagram } from "./about/RaceModelDiagram";
import { SplitsDiagram } from "./about/SplitsDiagram";
import { TrackDiagram } from "./about/TrackDiagram";
import "./pages.css";
import "./about.css";

const SECTIONS = [
  { id: "sources", title: "Where the times come from" },
  { id: "checks", title: "How they're checked" },
  { id: "track", title: "The track" },
  { id: "model", title: "The race model" },
  { id: "between", title: "Between the splits" },
  { id: "replay", title: "Watching a race" },
  { id: "data", title: "The data" },
] as const;

/** How close the drawn runner comes to where they really were, at splits hidden from it: tested
 * on every run timed at its event's finest points (see docs/replay-positions.md). */
const ACCURACY = [
  ["100m", "every 20m", "5 cm", "16 cm"],
  ["100m", "finish only", "29 cm", "84 cm"],
  ["200m", "100m only", "18 cm", "55 cm"],
  ["200m", "finish only", "52 cm", "1.5 m"],
  ["400m", "every 100m", "27 cm", "72 cm"],
  ["400m", "finish only", "1.3 m", "3.7 m"],
  ["110m hurdles", "every other hurdle", "5 cm", "15 cm"],
  ["800m", "every 200m", "1.0 m", "2.6 m"],
] as const;

const COMPARE_BOLT_TEBOGO =
  "/compare?event=200m&setting=outdoor&sex=men&p=wch-2009-berlin%2F200m-men%2Ffinal%2Fusain-bolt%2Cog-2024-paris%2F200m-men%2Ffinal%2Fletsile-tebogo";

/** Times along a typical run of an event, in its median finishing time: when it reaches each of
 * the race model's points, from the gun. */
function typicalTimes(event: EventOut | undefined) {
  const shape = event?.shape;
  if (!shape) return null;
  const reaction = event.reaction ?? 0;
  const at = (share: number) => reaction + share * (shape.median - reaction);
  return { finish: shape.median, runs: shape.runs, points: shape.points.map((p) => ({ ...p, time: at(p.share) })), reaction };
}

/** The shortest and longest events with races, in metres. */
function range(index: Index): [number, number] {
  const distance = new Map(index.disciplines.map((d) => [d.id, d]));
  const track = index.events
    .filter((e) => e.races > 0)
    .map((e) => distance.get(e.discipline))
    .filter((d) => d && d.kind !== "relay" && d.kind !== "road" && d.kind !== "race-walk")
    .map((d) => d!.distance);
  return [Math.min(...track), Math.max(...track)];
}

export function AboutPage() {
  const index = useIndex();
  const event = (id: string) => index.events.find((e) => e.id === id);
  const [shortest, longest] = range(index);

  // Facts for the race model, read off the typical runs of the men's 100 m, 400 m and 800 m.
  const sprint = typicalTimes(event("100m-men"));
  const sprintSteps = sprint?.points.map((p, i) => ({ to: p.distance, from: i ? sprint.points[i - 1]!.distance : 0, took: p.time - (i ? sprint.points[i - 1]!.time : 0) }));
  const fastestStep = sprintSteps?.slice(1).reduce((best, s) => (s.took / (s.to - s.from) < best.took / (best.to - best.from) ? s : best));
  const lap = typicalTimes(event("400m-men"));
  const halfLap = lap?.points.find((p) => p.distance === 200);
  const two = typicalTimes(event("800m-men"));
  const firstLap = two?.points.find((p) => p.distance === 400);
  const fromGun = (share: number) => (lap ? (lap.reaction + share * (lap.finish - lap.reaction)) / lap.finish : share);

  return (
    <div className="page stack" style={{ "--gap": "28px" } as React.CSSProperties}>
      <header className="page-header">
        <h1>About</h1>
        <p className="lede">
          Splits collects the split times of elite track races, from {count(shortest)} m to {count(longest)} m, so
          athletes and coaches can see how the best in the world actually run them.
        </p>
      </header>

      <div className="about-layout">
        <AboutNav sections={SECTIONS} />
        <div className="prose about">
          <p>
            It holds {count(index.build.splits)} splits from {count(index.build.races)} races.
          </p>

          <h2 id="sources">Where the times come from</h2>
          <p>
            After a race, its timing company publishes documents with each athlete's time at points along the
            way. Splits reads those documents and keeps, for every number, the page and the exact words it came
            from. Each race links to its original documents, so any time can be checked at source.
          </p>
          <p>
            Athletes are linked to their World Athletics profile.
          </p>

          <h2 id="checks">How they're checked</h2>
          <p>
            A race usually has two documents: the result and the split analysis. Where both give the same fact,
            they must agree. Every run is also checked against what is humanly possible, and against how others
            ran the same event.
          </p>
          <details className="about-checks">
            <summary>All {index.checks.length} checks</summary>
            {[...new Set(index.checks.map((check) => check.group))].map((group) => (
              <section key={group} className="about-check-group">
                <h3>{group}</h3>
                <dl>
                  {index.checks
                    .filter((check) => check.group === group)
                    .map((check) => (
                      <div key={check.id}>
                        <dt>{check.title}</dt>
                        <dd>
                          {check.explanation}
                          {check.suspect && <span className="about-suspect"> Times it flags are left out of analyses.</span>}
                        </dd>
                      </div>
                    ))}
                </dl>
              </section>
            ))}
          </details>
          <p>
            Flagged times are kept as published, struck through, with a warning sign: point at one, or tap it, to
            see why. They are left out of averages, charts and the replay, where the runner is drawn as if that
            split were missing.
          </p>

          <h2 id="track">The track</h2>
          <p>
            The replay draws an outdoor track to World Athletics' dimensions: two straights of 84.39 m, and two
            bends whose kerb is a half circle of radius 36.50 m, with eight lanes 1.22 m wide. A lane isn't
            measured along its middle but close to the inside, where an athlete runs: lane 1 0.30 m outside the
            kerb, every other lane 0.20 m outside its inner line. That makes lane 1 exactly 400 m, and the outer
            lanes longer, which is why races round a bend start staggered. The dimensions are World Athletics'
            standard 400 m track, from its{" "}
            <a href="https://worldathletics.org/about-iaaf/documents/technical-information" target="_blank" rel="noreferrer">
              Track and Field Facilities Manual
            </a>
            ; how lanes are measured is Technical Rule 14, in its{" "}
            <a href="https://worldathletics.org/about-iaaf/documents/book-of-rules" target="_blank" rel="noreferrer">
              Book of Rules
            </a>
            .
          </p>
          <p>
            Indoors, the track is a 200 m oval of two straights and two bends, which are usually banked, with four
            to six lanes 0.90 m to 1.10 m wide (Technical Rules 41 to 44). The rules don't fix the bends' radius,
            so the replay draws a typical oval: bends of radius 17.20 m, six lanes 1.00 m wide, and straights of
            45.02 m, so that lane 1 measures exactly 200 m. Lanes are measured as outdoors, and the banking is drawn
            flat. Pick a track, a race and a lane:
          </p>
          <TrackDiagram />
          <p>
            Races up to 300 m are run in lanes all the way. Indoors the 400 m keeps to lanes for two bends, and
            the 800 m, indoors and out, for one; after the break line runners may cut in. From there the splits say
            how far along each runner is, not where across the track, so they're drawn as races are run: on the
            inside, in single file, moving out only to pass or when someone is alongside, and back in once clear.
            From 1000 m up, races start from a curved line across the track, without lanes, and runners funnel in
            over the first 60 m. The 100 m and the sprint hurdles are run on the home straight, extended beyond
            the bend, so their replay is a straight of its own.
          </p>

          <h2 id="model">The race model</h2>
          <p>Nobody runs a race at an even pace.</p>
          <ul>
            {sprint && fastestStep && sprintSteps && (
              <li>
                <strong>Getting up to speed.</strong> From the blocks, a sprinter takes several seconds to reach top
                speed. In a typical {time(sprint.finish)} men's 100 m, the first 10 m takes {sprintSteps[0]!.took.toFixed(2)} s,
                reaction included, and the fastest 10 m, from {fastestStep.from} m to {fastestStep.to} m,{" "}
                {fastestStep.took.toFixed(2)} s.
              </li>
            )}
            {lap && halfLap && (
              <li>
                <strong>Fatigue.</strong> Nobody holds top speed for long. A typical {time(lap.finish)} men's 400 m covers
                the second 200 m {(lap.finish - 2 * halfLap.time).toFixed(2)} s slower than the first
                {two && firstLap
                  ? `, and a typical ${time(two.finish)} men's 800 m runs its second lap in ${time(two.finish - firstLap.time)}, after a first of ${time(firstLap.time)}`
                  : ""}
                .
              </li>
            )}
            <li>
              <strong>Bends.</strong> Running a bend costs a little speed, the more so the tighter it is: in the
              inside lanes, and on indoor tracks.
            </li>
            <li>
              <strong>Tactics.</strong> Longer races are often run slowly early and decided by a fast finish.
            </li>
          </ul>
          {lap && halfLap && (
            <p>
              Yet whatever their time, runners in an event spread a race in much the same way. Of {count(lap.runs)}{" "}
              men's 400 m runs timed every 50 m, the faster half (under {time(lap.finish)}) reached 200 m having used{" "}
              {(fromGun(halfLap.faster) * 100).toFixed(1)}% of their time; the slower half,{" "}
              {(fromGun(halfLap.slower) * 100).toFixed(1)}%.
            </p>
          )}
          <p>
            That makes a model of the race. For every event up to 800 m, Splits takes each run timed at the event's
            finest points (every 10 m in the sprints, every hurdle, every 50 m in the 400 m, every 100 m in the
            800 m) and finds, at each point, the median share of the race the runners had used up, counting from
            leaving the blocks. Together those shares are the event's typical race. Pick an event and a time to
            see it against an even pace:
          </p>
          <RaceModelDiagram />
          <p>
            Above 800 m there is no race model: one 1500 m is run hard from the gun, the next is slow until the
            last lap, and a typical race would describe neither.
          </p>

          <h2 id="between">Between the splits</h2>
          <p>
            A runner's splits say exactly where they were at a few moments, and the replay always draws them there.
            Between splits it interpolates their position, using the race model: over each stretch between two
            splits, the runner spends their time the way typical runners spend theirs over that stretch, stretched
            or squeezed to the runner's own time for it. If typical runners cover the first half of a stretch in,
            say, 48% of their time over it, so does this runner. The replay smooths the joins, so a runner's speed
            never jumps at a split.
          </p>
          <p>
            Here is Letsile Tebogo's Olympic final, timed every 10 m. Keep only some of his splits, and compare two
            ways of filling the gaps: straight lines, which hold one speed from each split to the next and jump to
            another at every split, and the race model.
          </p>
          <Suspense fallback={<Loading />}>
            <SplitsDiagram />
          </Suspense>
          <p>The same interpolation is used wherever a runner's position between known times is needed:</p>
          <ul>
            <li>
              <strong>Missing splits.</strong> Some splits aren't published, and some are flagged as wrong and left
              out. The runner is interpolated across the gap.
            </li>
            <li>
              <strong>Only a finishing time.</strong> Many races publish only results. A runner with nothing but a
              finishing time runs the typical race in that time: the best guess there is, though it can't know
              whether they went out hard or came home strong. The same goes for you: enter a time on any race, or
              in Compare, and you race the field as the dashed runner, leaving the blocks at the event's typical
              reaction and running the typical race in your time.
            </li>
            <li>
              <strong>Comparing runs timed differently.</strong> Usain Bolt's 2009 world record was timed every
              50 m, Letsile Tebogo's 2024 Olympic win every 10 m. In <Link to={COMPARE_BOLT_TEBOGO}>Compare</Link>,
              Bolt is interpolated between his 50 m splits, so the two can be raced side by side, each moving as
              they did in their own race.
            </li>
            <li>
              <strong>The split planner.</strong> Event pages apply the race model to a target time: each split is
              the median share at that point, applied to your time, and the middle half shows where half of all runs
              fall. You choose the timing points, and can keep indoor and outdoor races, or heats and finals, apart.
            </li>
            <li>
              <strong>Pacing charts.</strong> Athlete pages set each run against a typical run in the same time,
              stretch by stretch: to the left (blue) the athlete was quicker there, to the right (red) slower. Both
              finish in the same time, so the differences add up to zero: the chart says how the time was spent,
              not whether the race was good. A red start and a blue finish means going out easier and closing
              stronger than usual. Differences of a few hundredths are within what timing and ordinary variation
              allow.
            </li>
          </ul>
          <p>
            <strong>The first few metres.</strong> Over the first stretch of the model (10 m in a sprint) there's
            too little detail to show a runner gathering speed, so there they accelerate as sprinters do: from their
            reaction, their speed <var>v</var> rises towards a top speed <var>v</var>
            <sub>max</sub> as
            <span className="formula">
              <var>v</var>(<var>t</var>) = <var>v</var>
              <sub>max</sub>(1 − <var>e</var>
              <sup>
                −<var>t</var>/<var>τ</var>
              </sup>
              )
            </span>
            (the model of{" "}
            <a href="https://doi.org/10.1098/rspb.1927.0035" target="_blank" rel="noreferrer">
              Furusawa, Hill and Parkinson, 1927
            </a>
            ), with the time constant <var>τ</var>, about a second, chosen so they arrive
            at the speed the race carries on at. A runner whose reaction wasn't published leaves at the event's
            median one; from a standing start (800 m and up), everyone leaves at the gun.
          </p>
          <p>
            <strong>Above 800 m</strong>, with no race model, the replay interpolates smoothly between the splits
            alone, and a runner with only a finishing time runs at an even pace.
          </p>
          <p>
            <strong>How close it comes.</strong> Hiding some splits of every run timed at its event's finest points,
            and interpolating from the rest, shows how far the drawn runner is from where the hidden splits put them:
          </p>
          <div className="table-wrap">
            <table className="data about-accuracy">
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Splits kept</th>
                  <th className="right">Typically</th>
                  <th className="right">9 runs in 10</th>
                </tr>
              </thead>
              <tbody>
                {ACCURACY.map(([name, kept, typical, most]) => (
                  <tr key={`${name}/${kept}`}>
                    <td>{name}</td>
                    <td>{kept}</td>
                    <td className="right num">within {typical}</td>
                    <td className="right num">within {most}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 id="replay">Watching a race</h2>
          <p>
            The standings beside the track rank runners by how far along they are drawn at every moment, finishers
            by their time. Wherever two runners were timed at the same point, their order there is exactly the
            published order; between points it rests on the interpolated positions. The times shown are always the
            published splits.
          </p>
          <p>
            The key under each replay says what the marks on the track are: splits, hurdles in yellow, and the blue
            break line. <strong>Follow</strong> (or the F key) closes in on the leaders and moves with them; choose a
            name in the standings to follow that runner instead. Space plays and pauses, and the arrow keys step
            through the race. Point at a stretch of the splits table to see it on the track.
          </p>
          <p>
            <Link to="/compare">Compare</Link> races any runs over the same distance against each other, from any
            race, men's and women's alike. A split only one run has is marked in its own lane.
          </p>

          <h2 id="data">The data</h2>
          <p>
            Everything is free to download from the <Link to="/data">Data</Link> page. If you spot a mistake or know
            of a race that's missing, <Link to="/report?from=%2Fabout">let us know</Link>.
          </p>
        </div>
      </div>
    </div>
  );
}
