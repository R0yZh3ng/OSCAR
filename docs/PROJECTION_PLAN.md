# OSCAR Projection: Image Transformation Per Wall

Status: plan (2026-10-21). Nothing built yet. Supersedes the "one CSS class per wall" idea in
`PLAN.md`, because the display is now a set of Chromium tabs switched by RFID (`display/tabs.py`),
not one page the daemon controls.

## The problem

When the turntable rotates the projector off-perpendicular to a wall, the image is a trapezoid
(keystone) and may be rotated and cropped by corners and edges. Each aim point ("wall", "closet")
needs a pre-distortion applied to the page so it lands as a clean rectangle on that surface.

Constraints that shape the design:
- The content is tracker pages in separate Chromium tabs, switched by tag. The warp must apply to
  **every** tab, and must change when the turntable moves, without reloading anything.
- Keep the router/hardware split: warp values live in `config/presets.json`, the display side only
  reads them. No hardware needed to test the math.
- The projector is low quality and the room bright (see the wall theme). Warping costs resolution
  and brightness at the edges; keep the usable rectangle as large as the surface allows.

## Options considered

| Option | Verdict |
|---|---|
| Projector's built-in keystone | Use first: free, no resolution cost for the vertical axis. Cheap projectors usually only correct vertical, rarely horizontal, and not per aim point. Not sufficient alone |
| Per-page CSS (`perspective/rotateX/rotateY`, as in PLAN.md) | Easy to hand-tune but needs the page to cooperate; only approximates a true homography |
| **`matrix3d` from 4 corner points (homography)** on a wrapper element | **Chosen.** Exact for a flat surface, works on any content, and the 4 corners are what a human drags during calibration |
| Compositor/GPU-level warp on the Pi (Wayland) | No clean path on this Pi (KMS); skip |
| Render-to-canvas/WebGL warp | Overkill unless the surface is curved; revisit if needed |

## Design

### 1. Where the warp is applied

**Wrapper page (recommended).** `display/` serves `/stage?u=<encoded url>`: a full-screen black
page with the target in an `<iframe>` inside a `<div id="stage">` that carries
`transform: matrix3d(...)` and `transform-origin: 0 0`. The RFID tag URLs in `config/preset.json`
are wrapped by `scripts/routine.py` (or `display/tabs.py`) so the tabs stay as before but go
through `/stage`. Works because OSCAR's own pages are same-origin, so framing is fine.

Fallback if a tag ever points at a site that refuses framing (X-Frame-Options): inject the same
`html { transform: matrix3d(...) }` into that tab over the Chromium DevTools websocket
(`Page.addScriptToEvaluateOnNewDocument` + `Runtime.evaluate`). `tabs.py` currently only uses the
`/json` HTTP endpoints, so this adds a websocket client dependency; defer until needed.

**Live updates.** The wrapper subscribes to `GET /warp` events (Server-Sent Events or a socket)
for the currently active wall; every tab re-warps instantly when the turntable moves, so inactive tabs
are already correct when switched to.

### 2. Math

A homography maps the unit screen rectangle to a quad `Q` (4 points, in screen pixels) where the
image should land on the projector's output. Solve the 8-unknown linear system (standard 4-point
DLT) in JS; no libraries needed. For the 3x3 homography with rows `[a b c; d e f; g h 1]`, the CSS
value is `matrix3d(a, d, 0, g,  b, e, 0, h,  0, 0, 1, 0,  c, f, 0, 1)` (column-major, z untouched).

A small `display/static/warp.js` function `homography(src[4], dst[4]) -> matrix3d string`, with a
Python mirror in `display/warp.py` for tests (same input corners, same matrix, checked against
known cases: identity, pure scale, a known trapezoid).

### 3. Config

Extends `config/presets.json` (the `warp` block becomes corners instead of rotate values):

```
"walls": {
  "wall":   { "angle_deg": 40,
              "warp": { "corners": [[0.04,0.02],[0.97,0.06],[0.96,0.95],[0.02,0.91]] } },
  "closet": { "angle_deg": 140,
              "warp": { "corners": [ ... ] } } }
```

`angle_deg` is the turntable angle from the home switch (`TURNTABLE_PLAN.md`); the stepper
replaces the old `servo_angle`, and `hardware/turntable.py` converts it to steps. Corners are normalized 0..1 of the projector output, in order TL, TR, BR, BL, so the preset does
not depend on the screen's pixel size. Old `rotateX/rotateY/perspective` keys stay readable as a
migration path (`warp.py` converts them to the same corner form) so nothing already tuned is lost.

### 4. Calibration (`scripts/calibrate.py` + `/calibrate` page)

1. Move the turntable to the wall's angle; project a grid test pattern (`/calibrate?wall=closet`) with
   a drawn border and diagonals so error is visible.
2. Drag the four corner handles (mouse or phone over the LAN) until the border matches the real
   wall rectangle (or tape marks). Keys nudge by 1 px; the page previews live by sending the
   corners to `/warp`.
3. Save to `config/presets.json` (writes only that wall's block).

Also record the angle in the same step, so one tool tunes aim and warp together; they are
different pieces of state (aim vs mode, see `CLAUDE.md`) but for one physical wall they are tuned together.

### 5. Beyond two fixed presets (later)

Once the turntable exists, the distortion is a smooth function of turntable angle. Interpolate the four
corners between calibrated angles (linear in angle is enough over a small range) so intermediate
aim points work without a new calibration. A model-based version (homography from the projector's
rotation about a known axis) is possible but needs the wall geometry; calibration by hand wins at
two walls.

## Steps

1. Math + tests: `display/warp.py` (homography, corner <-> matrix3d, legacy-key conversion),
   `tests/test_warp.py`. No browser or hardware.
2. `/stage` wrapper + `warp.js` + `/warp` endpoint with live updates; wrap the tag URLs. Test on
   the laptop with a fake preset and a test grid.
3. Calibrate page and `scripts/calibrate.py` (manual corner drag, save).
4. On the Pi, with the projector on a real wall *before* the turntable is finished: use the
   projector's own keystone for the rough fix and OSCAR's corner warp for the rest. Calibrate one
   wall to prove the pipeline.
5. After the turntable is printed (`TURNTABLE_PLAN.md`): calibrate both walls with the real
   servo angles. Save to `presets.json`.
6. Wire the router: "wall"/"closet" and RFID mode move the turntable and push the new corners.
   (Requires the router from `PLAN.md`; until then `calibrate.py` can trigger it.)
7. Optional: angle interpolation; DevTools-injection fallback.

## Risks and checks

- **Resolution and brightness loss**: the warped quad is smaller than the full frame, so text gets
  softer. Mitigate with the wall theme (already large and high contrast) and by placing the
  turntable so the beam hits the wall as square as possible.
- Iframes and scroll: the wall theme already avoids scrolling; embedded page must fit one screen.
- Hash routes: `tabs.py` tells SPA tabs apart by URL hash, which changes when wrapped in `/stage?u=`.
  Matching must compare the inner URL. Cover with a test.
- Rolling shutter or flicker when updating transform on a large iframe: update only the wrapper
  `transform`, never re-layout the inner page.
- Curved or non-flat surface (a closet door with a seam): a single homography can't fix it. Accept
  or use a mesh warp later (WebGL).
- Test pattern + a phone photo of the wall is a good before/after for the write-up.

## Done when

- Tapping a tag shows the tracker as a clean rectangle on the wall, in the tab it was loaded in.
- Switching aim (turntable move) changes the warp within about a second on all tabs.
- Both walls are calibrated from the calibration page and survive a Pi reboot (stored in git-tracked
  `presets.json`).
- `tests/test_warp.py` passes without a browser or hardware.
