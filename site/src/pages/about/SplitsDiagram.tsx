// Filling the gaps between splits, on a real run: Letsile Tebogo's Olympic 200 m final, timed
// every 10 m. Keep only some of his splits and compare two ways of filling the gaps: joining
// them with straight lines (an even pace from each split to the next) and the race model. Both
// are shown as speed along the race, beside the speeds his 10 m splits actually give.

import { use, useMemo, useState } from "react";
import { useWidth } from "../../components/charts/useWidth";
import { Segmented } from "../../components/ui";
import { fetchJson, useIndex } from "../../data/load";
import type { RaceData } from "../../data/types";
import { motion, type Motion } from "../../track/geometry";

const RACE = "og-2024-paris/200m-men/final";
const RUNNER = "letsile-tebogo";
const PRESETS = {
  fifty: { label: "Every 50 m", keep: (d: number) => d % 50 === 0 },
  hundred: { label: "100 m only", keep: (d: number) => d === 100 },
  none: { label: "Finish only", keep: () => false },
} as const;
type Preset = keyof typeof PRESETS;

/** When ``m`` reached ``d`` (it never runs backwards, so bisect). */
function when(m: Motion, d: number): number {
  let [lo, hi] = [0, m.end];
  for (let k = 0; k < 50; k++) {
    const mid = (lo + hi) / 2;
    if ((m.at(mid) ?? 0) < d) lo = mid;
    else hi = mid;
  }
  return hi;
}

export function SplitsDiagram() {
  const index = useIndex();
  const race = use(fetchJson<RaceData>(`races/${RACE}.json`));
  const shape = index.events.find((e) => e.id === "200m-men")?.shape?.points ?? null;
  const perf = race.performances.find((p) => p.athlete === RUNNER)!;
  const reaction = perf.reactionTime?.v ?? 0;
  const finish = perf.time!.v;
  const splits = perf.splits
    .map((s) => ({ d: race.points[s.point]!.distance, t: s.time.v }))
    .filter((s) => s.d < 200)
    .sort((a, b) => a.d - b.d);
  const [preset, setPreset] = useState<Preset>("fifty");
  const kept = splits.filter((s) => PRESETS[preset].keep(s.d));
  // The points the gaps are filled between: leaving the blocks, the splits kept, the finish.
  const known = [{ d: 0, t: reaction }, ...kept, { d: 200, t: finish }];

  const model = useMemo(() => motion([{ t: 0, d: 0 }, { t: reaction, d: 0 }, ...kept, { t: finish, d: 200 }], true, shape), [preset, shape]); // eslint-disable-line react-hooks/exhaustive-deps
  // Speed every metre: the race model's, and joining the splits with straight lines.
  const modelSpeed = useMemo(() => {
    const at = (d: number) => (d === 0 ? reaction : when(model, d));
    return Array.from({ length: 200 }, (_, d) => ({ d: d + 0.5, v: 1 / (at(d + 1) - at(d)) }));
  }, [model, reaction]);
  const straight = known.slice(1).map((k, i) => ({ from: known[i]!.d, to: k.d, v: (k.d - known[i]!.d) / (k.t - known[i]!.t) }));
  // What he actually ran: his speed over each 10 m.
  const actual = [{ d: 0, t: reaction }, ...splits, { d: 200, t: finish }].slice(1).map((s, i, all) => {
    const before = i === 0 ? { d: 0, t: reaction } : all[i - 1]!;
    return { d: (before.d + s.d) / 2, v: (s.d - before.d) / (s.t - before.t) };
  });
  // How far each way of filling the gaps puts him from where he was, at the splits it wasn't given.
  const hidden = splits.filter((s) => !PRESETS[preset].keep(s.d));
  const straightAt = (t: number) => {
    const i = known.findIndex((k) => k.t >= t);
    const [a, b] = [known[i - 1]!, known[i]!];
    return a.d + ((b.d - a.d) * (t - a.t)) / (b.t - a.t);
  };
  const miss = (at: (t: number) => number) => hidden.reduce((sum, s) => sum + Math.abs(at(s.t) - s.d), 0) / hidden.length;
  const missModel = miss((t) => model.at(t) ?? 0);
  const missStraight = miss(straightAt);

  const [box, width] = useWidth<HTMLDivElement>(640);
  const h = Math.min(300, Math.max(220, width * 0.5));
  const m = { left: 44, right: 18, top: 14, bottom: 40 };
  const top = 12;
  const x = (d: number) => m.left + (d / 200) * (width - m.left - m.right);
  const y = (v: number) => h - m.bottom - (Math.min(v, top) / top) * (h - m.top - m.bottom);
  const steps = straight.map((s) => `M${x(s.from).toFixed(1)},${y(s.v).toFixed(1)}H${x(s.to).toFixed(1)}`).join("");
  const smooth = modelSpeed.map((p) => `${x(p.d).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const cm = (metres: number) => (metres < 1 ? `${Math.round(metres * 100)} cm` : `${metres.toFixed(1)} m`);

  return (
    <figure className="about-figure">
      <div className="about-controls">
        <Segmented
          label="Splits kept"
          value={preset}
          onChange={setPreset}
          options={(Object.keys(PRESETS) as Preset[]).map((key) => ({ value: key, label: PRESETS[key].label }))}
        />
        <span className="about-legend">
          <span>
            <span className="about-key actual" /> Measured
          </span>
          <span>
            <span className="about-key even" /> Straight lines
          </span>
          <span>
            <span className="about-key typical" /> Race model
          </span>
        </span>
      </div>
      <div ref={box} className="about-track">
        <svg width={width} height={h} role="img" aria-label="Tebogo's speed along the race: measured, by straight lines between the splits kept, and by the race model">
          {[2, 4, 6, 8, 10, 12].map((v) => (
            <g key={v}>
              <line x1={m.left} x2={width - m.right} y1={y(v)} y2={y(v)} className="about-grid" />
              <text x={m.left - 6} y={y(v) + 4} className="about-tick" textAnchor="end">
                {v}
              </text>
            </g>
          ))}
          <text x={12} y={(m.top + h - m.bottom) / 2} className="about-tick" textAnchor="middle" transform={`rotate(-90 12 ${(m.top + h - m.bottom) / 2})`}>
            m/s
          </text>
          <line x1={m.left} x2={width - m.right} y1={h - m.bottom} y2={h - m.bottom} className="about-axis" />
          {[0, 50, 100, 150, 200].map((d) => (
            <text key={d} x={x(d)} y={h - m.bottom + 15} className="about-tick" textAnchor="middle">
              {d}m
            </text>
          ))}
          <text x={(m.left + width - m.right) / 2} y={h - 4} className="about-tick" textAnchor="middle">
            Distance
          </text>
          {kept.map((s) => (
            <line key={s.d} x1={x(s.d)} x2={x(s.d)} y1={m.top} y2={h - m.bottom} className="about-split" />
          ))}
          <path d={steps} className="about-steps" />
          <polyline points={smooth} className="about-curve" />
          {actual.map((p) => (
            <circle key={p.d} cx={x(p.d)} cy={y(p.v)} r={3} className="about-actual" />
          ))}
        </svg>
      </div>
      <figcaption>
        Keeping {kept.length === 0 ? "only his finishing time" : kept.length === 1 ? "only his 100 m split" : `his splits every 50 m (the faint lines)`}, straight lines between them
        put him on average {cm(missStraight)} from where he really was at the {hidden.length} splits they weren't given; the race model,{" "}
        {cm(missModel)}.
      </figcaption>
    </figure>
  );
}
