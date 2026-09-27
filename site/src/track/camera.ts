// The follow camera: a view of the drawing framing the runners who matter at each moment (the
// leaders and the pack around them, or one runner being followed), with room ahead of them.
// Each shot is averaged over the moments either side of it, so the camera glides through the
// bends instead of jerking with every change in the pack, and scrubbing to a moment finds the
// same view as playing up to it.

import type { Point } from "./geometry";

/** A rectangle of the drawing, in SVG units. */
export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Shot {
  centre: Point;
  /** SVG units across. */
  width: number;
}

/** Metres: the narrowest view (never closer than this)... */
export const CLOSEST = 48;
/** ...the room left around the runners framed... */
const ROOM = 8;
/** ...and the extra room ahead of them, where they are going. */
const LEAD = 8;
/** Seconds either side of a moment that its shot is averaged over, and the spread of the
 * weights. */
const WINDOW = 1.5;
const SPREAD = 0.7;
const SAMPLES = 6;

/** The shot framing ``points`` (SVG units), with room ahead along ``heading`` (a unit vector),
 * at ``scale`` SVG units per metre, for a view ``aspect`` times as wide as it is high. */
export function frameShot(points: Point[], heading: Point, scale: number, aspect: number): Shot {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const [room, lead] = [ROOM * scale, LEAD * scale];
  const width = Math.max(
    CLOSEST * scale,
    x1 - x0 + 2 * room + lead * Math.abs(heading.x),
    (y1 - y0 + 2 * room + lead * Math.abs(heading.y)) * aspect,
  );
  return { centre: { x: (x0 + x1 + heading.x * lead) / 2, y: (y0 + y1 + heading.y * lead) / 2 }, width };
}

/** The shot at ``t``: the shots from ``WINDOW`` seconds before to after it (within the race,
 * 0 to ``end``), averaged with Gaussian weights. */
export function smoothShot(shot: (t: number) => Shot | null, t: number, end: number): Shot | null {
  let [x, y, width, total] = [0, 0, 0, 0];
  for (let k = -SAMPLES; k <= SAMPLES; k++) {
    const offset = (k / SAMPLES) * WINDOW;
    const at = shot(Math.min(Math.max(t + offset, 0), end));
    if (!at) continue;
    const weight = Math.exp(-0.5 * (offset / SPREAD) ** 2);
    x += at.centre.x * weight;
    y += at.centre.y * weight;
    width += at.width * weight;
    total += weight;
  }
  return total ? { centre: { x: x / total, y: y / total }, width: width / total } : null;
}

/** The rectangle a shot shows of a drawing ``width`` by ``height``, kept within it. */
export function shotRect(shot: Shot, width: number, height: number): Rect {
  const w = Math.min(shot.width, width);
  const h = (w * height) / width;
  return {
    x: Math.min(Math.max(shot.centre.x - w / 2, 0), width - w),
    y: Math.min(Math.max(shot.centre.y - h / 2, 0), height - h),
    w,
    h,
  };
}

/** Part way from rectangle ``a`` to ``b``. */
export function mixRects(a: Rect, b: Rect, f: number): Rect {
  const mix = (p: number, q: number) => p + (q - p) * f;
  return { x: mix(a.x, b.x), y: mix(a.y, b.y), w: mix(a.w, b.w), h: mix(a.h, b.h) };
}
