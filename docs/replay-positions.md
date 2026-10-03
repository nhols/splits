# Where runners are between splits

The replay shows every runner on the track at every moment, and the standings beside it rank
them. The splits say exactly where a runner was at a few moments; everything else is
interpolation. This is the model for that interpolation, in races and in comparisons of runs
from different races alike.

## Known points

Each runner's curve (distance against time) passes **exactly** through every point we know:

- **Leaving the blocks**, at their reaction time. Where none is published it is inferred: the
  median reaction time of that event and sex. Over the 200 m that is 0.156 s, and guessing it
  moves the drawn position by about 1 cm (tested below). Races with a standing start (800 m
  and up) leave at the gun.
- **Every split**, except those the checks mark as suspect. A split is ground truth: a runner is
  always drawn at the split's distance at the split's time. A suspect split (10 m reached
  0.20 s after the gun) is a misreading, not the race, so it is not drawn through.
- **The finish.**

## The shape of a race

Between known points, a runner moves as runners in that event typically move. Each event and
sex up to 800 m has one **shape**: the share of the race, from leaving the blocks to the finish,
that a typical runner has used up on reaching each distance. It is the median over every run
timed at the event's finest points:

| Event | Shape built from |
|---|---|
| 100 m, 200 m | splits every 10 m |
| 100 mH, 110 mH, 400 mH | a split at every hurdle |
| 400 m | splits every 50 m; the first 50 m spread as the 200 m spreads its first 50 m |
| 800 m | splits every 100 m |

The shape is continuous: a smooth, never-decreasing curve through its own points. So it can be
read at any distance, and runs timed on any grid use it: every 25 m, every 20 m over hurdles,
at 50 m and 150 m only. The grids need not line up.

The shape depends on the event and sex only, not on the round, the level of the field or
whether the race is indoors.

## Between known points

Take the runner's known points and plot each one's time against **how far through a typical
race** that distance is (the shape's share), instead of against metres. A runner who ran exactly
the typical race is a straight line on that chart; real runners bend gently away from it. Draw
one smooth, never-decreasing curve through the runner's points on that chart (a monotone cubic),
and read it back in metres. Then:

- the runner passes every split exactly;
- their speed changes smoothly, with no jump at a split;
- between splits they move as a typical runner does, bent to their own race;
- a runner with only a finish time runs exactly the typical race, scaled to their time.

## Above 800 m

No shape: a typical 1500 m means little when one race is run hard throughout and the next is
slow until the last lap. The curve is drawn smoothly through the splits alone (a monotone cubic
in metres), and a runner with only a finish time runs at an even pace from the gun to the line.

## Standings

At every moment the runners are ranked by how far along their curves they are: finishers by
finishing time (and the official place where times tie), the rest by distance. There are no
ties and no smoothing of the order.

This needs no splits in common. In a comparison of Bolt (timed every 50 m) and Tebogo (every
10 m), both are always somewhere on their curves, so they can always be ranked. Wherever two
runners were timed at the same distance, the order there is exactly the published order, as both
curves pass exactly through their splits and never run backwards. Elsewhere the order rests on
the curves: one runner's real time against another's interpolated one, or two interpolated.

## How well it works

Tested on every run timed at an event's finest points: hide some of a run's splits, draw it
from the rest, and measure how far the drawn runner is from where the hidden splits say. Each
run's shape is built from other races only. "Current" is the replay as it is today (a
modelled acceleration to the first split, then a smooth curve in metres). Errors are in metres,
typical and 9 runs in 10; "order wrong" is how often a runner drawn this way is on the wrong side
of a fully timed runner from the same race, at the hidden points.

| Event | Splits kept | Current: error, order wrong | Shape: error, order wrong |
|---|---|---|---|
| 100 m men | every 20 m | 0.10 / 0.58 m, 7.0% | 0.05 / 0.16 m, 1.6% |
| | 50 m only | 0.24 / 0.56 m, 9.2% | 0.09 / 0.29 m, 4.0% |
| | finish only | 0.50 / 1.04 m, 14.1% | 0.29 / 0.84 m, 12.8% |
| 200 m men | every 20 m | 0.06 / 0.40 m, 2.9% | 0.05 / 0.13 m, 0.8% |
| | 100 m only | 1.20 / 2.53 m, 24.8% | 0.18 / 0.55 m, 5.1% |
| | finish only | 2.76 / 4.40 m, 18.8% | 0.52 / 1.47 m, 14.2% |
| 400 m men | every 100 m | 0.65 / 1.82 m, 12.8% | 0.27 / 0.72 m, 3.6% |
| | 200 m only | 2.10 / 3.65 m, 18.2% | 0.65 / 1.76 m, 9.7% |
| | finish only | 11.59 / 16.40 m, 24.5% | 1.31 / 3.72 m, 18.8% |
| 110 mH | every other hurdle | 0.06 / 0.23 m, 3.3% | 0.05 / 0.15 m, 2.2% |
| | one hurdle, mid-race | 0.16 / 0.54 m, 10.8% | 0.12 / 0.43 m, 6.6% |
| | finish only | 2.16 / 3.04 m, 19.7% | 0.34 / 1.30 m, 17.2% |
| 400 mH men | every other hurdle | 0.21 / 0.71 m, 5.5% | 0.18 / 0.53 m, 2.9% |
| | one hurdle, mid-race | 2.90 / 4.91 m, 18.0% | 0.58 / 1.80 m, 8.1% |
| | finish only | 13.79 / 19.67 m, 19.8% | 1.40 / 4.23 m, 16.9% |
| 800 m men | every 200 m | 1.87 / 4.20 m, 18.6% | 0.98 / 2.57 m, 9.6% |
| | 400 m only | 5.12 / 11.15 m, 28.3% | 1.82 / 5.05 m, 18.6% |
| | finish only | 10.63 / 19.55 m, 32.5% | 3.36 / 10.55 m, 30.5% |

Women's events, and the 100 mH, behave the same way. The shape is better in every case, and
most where splits are sparse. With only a finish time it removes the bias (the current replay
draws such a runner several metres behind mid-race, up to 14 m in the 400 mH) but cannot know how
that runner actually ran the race: they are on the wrong side of a fully timed rival 12–19% of
the time up to 400 m, and about 30% in the 800 m. That is accepted.

The 400 m's first 50 m (taken from the 200 m) is not tested: nothing times a 400 m inside 50 m.

## Known limits

- **Runners within the noise of the splits swap places.** When two runners are level and one is
  timed every 10 m, small jumps in that runner's splits make the order swap back and forth;
  the published splits themselves often swap them too. If it looks bad on screen, the fix is to
  keep the current order and swap two neighbours only once the one behind is clearly ahead.
  That always leaves a proper order. A tolerance in which runners count as level does not
  (A level with B and B with C, while A is clearly ahead of C).
- **Barriers move with the stadium.** The steeplechase water jump sits inside or outside the
  track, so barriers fall in slightly different places from race to race. Above 800 m there is
  no shape, so this only matters for how closely the drawn runner follows the barriers.
- **Noisy splits pass the checks.** Impossible ones (10 m reached 0.20 s after the gun) are
  marked suspect by `segment-speed` and `split-outlier`, and left out. Merely jumpy ones (10 m
  stretches swinging between 0.83 s and 1.24 s) are possible, so they stay, and curves pass
  through them.

## Where it lives

- `src/splits/publish/shapes.py`: each event's shape and typical reaction time, built when the
  data is published and written to the index (`events[].shape`, `events[].reaction`).
- `site/src/track/geometry.ts` (`motion`): the curve against the shape, or in metres without one.
- `site/src/track/runners.ts`: each runner's known points, with the typical reaction where theirs
  was not published, and their event's shape. A comparison keeps every run's own splits.
- `site/src/track/Standings.tsx` (`standings`): the order by distance along the curves.

The shape replaces the typical splits that finish-only runners and the ghost (the time a reader
types in) used to run on (`plan`, in `site/src/data/analysis.ts`), which now serve only the
split planner. The ghost runs as a finish-only runner does (`site/src/track/model.ts`).
