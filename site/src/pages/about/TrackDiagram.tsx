// The track as the replay draws it, with the numbers behind it: pick outdoors or in, a race and
// a lane, and see where that lane is measured, how long a lap of it is, and how far ahead it
// starts.

import { useState } from "react";
import { useWidth } from "../../components/charts/useWidth";
import { Explained } from "../../components/Explained";
import { Segmented } from "../../components/ui";
import { course, cutIn, indoorTrack, laneRadius, lapLength, lineRadius, loopPath, outdoorTrack, type Point } from "../../track/geometry";

const RACES = [200, 400, 800] as const;
type Race = (typeof RACES)[number];
type Setting = "outdoor" | "indoor";
const TRACKS = { outdoor: outdoorTrack(8), indoor: indoorTrack(6) };
/** Bends run in lanes. Outdoors: one in the 200 m, two in the 400 m, one before the 800 m break
 * line. Indoors, a lap has two: the 200 m is a lap in lanes, the 400 m runs two bends in lanes,
 * the 800 m one (World Athletics Technical Rule 44). */
const BENDS: Record<Setting, Record<Race, number>> = {
  outdoor: { 200: 1, 400: 2, 800: 1 },
  indoor: { 200: 2, 400: 2, 800: 1 },
};

const metres = (value: number) => `${value.toFixed(2)} m`;

/** A number in a formula that says what it is, on hover or tap. */
function Term({ children, why }: { children: React.ReactNode; why: string }) {
  return (
    <Explained className="about-term" explanation={why}>
      {children}
    </Explained>
  );
}

export function TrackDiagram() {
  const [setting, setSetting] = useState<Setting>("outdoor");
  const [chosenLane, setLane] = useState(8);
  const [race, setRace] = useState<Race>(400);
  const [box, width] = useWidth<HTMLDivElement>(640);
  const TRACK = TRACKS[setting];
  const lane = Math.min(chosenLane, TRACK.lanes);
  const bends = BENDS[setting][race];
  const two = (value: number) => value.toFixed(2);

  const outer = lineRadius(TRACK, TRACK.lanes);
  const half = TRACK.straight / 2;
  // On a narrow screen the track stands upright, the home straight on the right, so it can be
  // drawn larger.
  const upright = width < 560;
  // Room round the track for the labels outside it.
  const pad = 26;
  const across1 = 2 * outer;
  const along1 = 2 * (half + outer);
  const scale = (width - 2 * pad) / (upright ? across1 : along1);
  const height = (upright ? along1 : across1) * scale + 2 * pad;
  // Turned a quarter round when upright (a rotation, so bends still curve the right way).
  const toSvg = (p: Point): Point =>
    upright ? { x: width / 2 + p.y * scale, y: height / 2 - p.x * scale } : { x: width / 2 + p.x * scale, y: height / 2 + p.y * scale };

  const r1 = laneRadius(TRACK, 1);
  const rn = laneRadius(TRACK, lane);
  const lap = lapLength(TRACK, rn);
  const path = course(TRACK, race, TRACK.lanes);
  // With a break line, a little more for cutting in across the straight after it.
  const cut = path.breakAt !== null ? cutIn(TRACK, lane) : 0;
  const stagger = bends * Math.PI * (rn - r1) + cut;
  // The runner's path in lanes: the whole race, or to the 800 m break line.
  const inLanes = path.breakAt ?? race;
  const along = (n: number, to: number) =>
    Array.from({ length: Math.ceil(to) + 1 }, (_, i) => toSvg(path.frame(n, Math.min(i, to)).p))
      .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(" ");
  // A mark across lane ``n`` at ``d`` metres into the race.
  const across = (n: number, d: number) => {
    const { p, q } = { p: path.frame(n, d).p, q: path.frame(n, d).n };
    const inner = lineRadius(TRACK, n - 1) - laneRadius(TRACK, n);
    const outerEdge = lineRadius(TRACK, n) - laneRadius(TRACK, n);
    const a = toSvg({ x: p.x + q.x * inner, y: p.y + q.y * inner });
    const b = toSvg({ x: p.x + q.x * outerEdge, y: p.y + q.y * outerEdge });
    return { x1: a.x, y1: a.y, x2: b.x, y2: b.y };
  };
  // The radius, from the far bend's centre out to the lane's measuring line.
  const centre = toSvg({ x: -half, y: 0 });
  const angle = (-150 * Math.PI) / 180;
  const rim = toSvg({ x: -half + rn * Math.cos(angle), y: rn * Math.sin(angle) });
  const startLane = toSvg(path.frame(lane, 0).p);
  const startOne = toSvg(path.frame(1, 0).p);
  const finish = [toSvg({ x: half, y: TRACK.kerb }), toSvg({ x: half, y: outer })];
  const font = Math.max(10, Math.min(12, width / 50));
  // A label in the infield, level with the start in lane ``n``: there is room there at any width.
  const outside = (n: number) => {
    const { p, n: out } = path.frame(n, 0);
    const inward = laneRadius(TRACK, n) - TRACK.kerb + 3;
    const at = toSvg({ x: p.x - out.x * inward, y: p.y - out.y * inward });
    // Which way is out of the infield, on the page.
    const tip = toSvg({ x: p.x + out.x, y: p.y + out.y });
    const base = toSvg(p);
    const [ox, oy] = [(tip.x - base.x) / scale, (tip.y - base.y) / scale];
    const anchor: "start" | "middle" | "end" = ox > 0.5 ? "end" : ox < -0.5 ? "start" : "middle";
    return { x: at.x, y: at.y + (oy > 0.5 ? -font * 0.4 : oy < -0.5 ? font : font / 3), anchor };
  };
  // Labels for the straight and the finish, inside the infield and beside the line.
  // Construction lines: the circles the bends are halves of (at the chosen lane's radius), the
  // lines where straight meets bend, through the circles' centres, and between those centres
  // the length of a straight.
  const centres = [toSvg({ x: -half, y: 0 }), toSvg({ x: half, y: 0 })];
  const joins = [-half, half].map((x) => [toSvg({ x, y: -outer - 2 }), toSvg({ x, y: outer + 2 })]);
  const straightAt = { x: (centres[0]!.x + centres[1]!.x) / 2, y: (centres[0]!.y + centres[1]!.y) / 2 };
  const finishLabel = upright
    ? { x: finish[1]!.x, y: finish[1]!.y - 6, anchor: "end" as const }
    : { x: finish[1]!.x, y: Math.min(finish[1]!.y + font * 1.3, height - 2), anchor: "middle" as const };
  const labelLane = outside(lane);
  const labelOne = outside(1);
  const nearFinish = (q: { x: number; y: number }) => Math.hypot(q.x - finish[1]!.x, q.y - finish[1]!.y) < 60;

  return (
    <figure className="about-figure">
      <div className="about-controls">
        <Segmented
          label="Track"
          value={setting}
          onChange={setSetting}
          options={[
            { value: "outdoor", label: "Outdoor" },
            { value: "indoor", label: "Indoor" },
          ]}
        />
        <Segmented label="Race" value={String(race)} onChange={(v) => setRace(Number(v) as Race)} options={RACES.map((r) => ({ value: String(r), label: `${r}m` }))} />
        <div className="about-lane">
          <span>Lane</span>
          <Segmented
            label="Lane"
            value={String(lane)}
            onChange={(v) => setLane(Number(v))}
            options={Array.from({ length: TRACK.lanes }, (_, k) => ({ value: String(k + 1), label: String(k + 1) }))}
          />
        </div>
      </div>
      <div ref={box} className="about-track">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`An ${setting} ${race}m in lane ${lane}, starting ${metres(stagger)} ahead of lane 1`}>
          <path d={loopPath(TRACK, outer, toSvg)} className="track-surface" />
          <path d={loopPath(TRACK, TRACK.kerb, toSvg)} className="track-infield" />
          {Array.from({ length: TRACK.lanes }, (_, k) => (
            <path key={k} d={loopPath(TRACK, lineRadius(TRACK, k + 1), toSvg)} className="track-line" />
          ))}
          <path d={loopPath(TRACK, TRACK.kerb, toSvg)} className="track-kerb" />
          <line x1={finish[0]!.x} y1={finish[0]!.y} x2={finish[1]!.x} y2={finish[1]!.y} className="track-finish" />
          {path.breakAt !== null && Array.from({ length: TRACK.lanes }, (_, k) => <line key={k} {...across(k + 1, path.breakAt!)} className="track-break" />)}
          {/* Lane 1's path, for comparison, then the chosen lane's. */}
          {lane > 1 && <polyline points={along(1, inLanes)} className="about-path-one" />}
          <polyline points={along(lane, inLanes)} className="about-path" />
          <line {...across(1, 0)} className="about-start-one" />
          <line {...across(lane, 0)} className="about-start" />
          {centres.map((c, i) => (
            <circle key={i} cx={c.x} cy={c.y} r={rn * scale} className="about-sketch" />
          ))}
          {joins.map(([a, b], i) => (
            <line key={i} x1={a!.x} y1={a!.y} x2={b!.x} y2={b!.y} className="about-sketch" />
          ))}
          <line x1={centres[0]!.x} y1={centres[0]!.y} x2={centres[1]!.x} y2={centres[1]!.y} className="about-dimension" />
          <circle cx={centres[1]!.x} cy={centres[1]!.y} r={2.5} className="about-centre" />
          <line x1={centre.x} y1={centre.y} x2={rim.x} y2={rim.y} className="about-radius" />
          <circle cx={centre.x} cy={centre.y} r={2.5} className="about-centre" />
          <text x={centre.x + 6} y={centre.y + font * 1.4} className="about-label" fontSize={font}>
            r = {metres(rn)}
          </text>
          <text
            x={straightAt.x + (upright ? 6 : 0)}
            y={straightAt.y + (upright ? font / 3 : -6)}
            className="about-label"
            fontSize={font}
            textAnchor={upright ? "start" : "middle"}
          >
            {metres(TRACK.straight)} (straight)
          </text>
          <text x={labelLane.x} y={labelLane.y} className="about-label strong" fontSize={font} textAnchor={labelLane.anchor}>
            Start, lane {lane}
          </text>
          {lane > 1 && Math.hypot(startLane.x - startOne.x, startLane.y - startOne.y) > 60 && !nearFinish(labelOne) && (
            <text x={labelOne.x} y={labelOne.y} className="about-label" fontSize={font} textAnchor={labelOne.anchor}>
              lane 1
            </text>
          )}
          <text x={finishLabel.x} y={finishLabel.y} className="about-label" fontSize={font} textAnchor={finishLabel.anchor}>
            Finish
          </text>
        </svg>
      </div>
      <div className="about-maths">
        <p>
          Lane {lane} is measured {lane === 1 ? "0.30 m outside the kerb" : "0.20 m outside its inner line"}, so on the bends it is a
          circle of radius
          <span className="formula">
            <var>r</var>
            <sub>{lane}</sub> ={" "}
            <Term
              why={
                setting === "outdoor"
                  ? "The radius of the kerb, the inside edge of lane 1: 36.50 m on World Athletics' standard track."
                  : "The radius of the kerb on the replay's indoor oval. The rules leave it to each track; 17.20 m is typical."
              }
            >
              {two(TRACK.kerb)}
            </Term>{" "}
            +{" "}
            {lane === 1 ? (
              <Term why="Lane 1 is measured 0.30 m outside the kerb, about where a runner's feet fall (Technical Rule 14).">0.30</Term>
            ) : (
              <>
                <Term
                  why={
                    setting === "outdoor"
                      ? "The width of a lane: 1.22 m outdoors."
                      : "The width of a lane: 1.00 m on the replay's indoor oval (the rules allow 0.90 m to 1.10 m)."
                  }
                >
                  {two(TRACK.laneWidth)}
                </Term>{" "}
                × <Term why={`The lanes inside lane ${lane}, between it and the kerb.`}>{lane - 1}</Term> +{" "}
                <Term why="Lanes other than lane 1 are measured 0.20 m outside their inner line (Technical Rule 14).">0.20</Term>
              </>
            )}{" "}
            ={" "}
            <Term why={`The radius of lane ${lane}'s measuring line round the bends: the line its distance is measured along.`}>
              <strong>{metres(rn)}</strong>
            </Term>
          </span>
        </p>
        <p>
          One lap of it is two straights and two half circles:
          <span className="formula">
            <var>L</var>
            <sub>{lane}</sub> ={" "}
            <Term
              why={
                setting === "outdoor"
                  ? "Two straights of 84.39 m, the distance between the bends' centres."
                  : "Two straights of 45.02 m, sized on the replay's indoor oval so that lane 1 measures exactly 200 m."
              }
            >
              2 × {two(TRACK.straight)}
            </Term>{" "}
            +{" "}
            <Term why={`Two half circles of radius ${metres(rn)}: together one full circle, 2π times its radius.`}>2π × {two(rn)}</Term> ={" "}
            <Term why={`One lap, measured along lane ${lane}'s measuring line.`}>
              <strong>{metres(lap)}</strong>
            </Term>
          </span>
        </p>
        <p>
          Every lane must be the same distance to the line, so each bend run in lanes puts lane {lane} π(
          <var>r</var>
          <sub>{lane}</sub> − <var>r</var>
          <sub>1</sub>) further ahead. {setting === "indoor" ? "Indoors" : "Outdoors"} the {race}m runs{" "}
          {bends === 1 ? "one bend" : "two bends"} in lanes
          {path.breakAt !== null
            ? ". Then runners may cut in to lane 1 across the straight after the blue break line, a diagonal longer than lane 1's straight, so outer lanes start a little further ahead again, and the break line is an arc, reached a little later in each lane out"
            : race === 200 && setting === "indoor"
              ? ", a whole lap"
              : ""}
          :
          <span className="formula">
            stagger ={" "}
            <Term why={`The bends the ${race}m runs in lanes, before runners may leave them${bends === 2 && path.breakAt === null ? " (here, the whole race)" : ""}.`}>{bends}</Term> ×{" "}
            <Term why={`How much longer one bend, a half circle, is in lane ${lane} than in lane 1: π times the difference of their radii.`}>
              π × ({two(rn)} − {two(r1)})
            </Term>{" "}
            {path.breakAt !== null && (
              <>
                +{" "}
                <Term
                  why={`The extra for cutting in: from the break line, lane ${lane} runs diagonally to lane 1 at the end of the ${two(TRACK.straight)} m straight, a straight's length from every point of the arced line. It is ${two(TRACK.straight)} − √(${two(TRACK.straight)}² − (${two(rn)} − ${two(r1)})²).`}
                >
                  {cut.toFixed(2)}
                </Term>{" "}
              </>
            )}
            ={" "}
            <Term why={`How far ahead of lane 1 lane ${lane} starts, so that both run exactly ${race} m.`}>
              <strong>{metres(stagger)}</strong>
            </Term>
          </span>
        </p>
      </div>
    </figure>
  );
}
