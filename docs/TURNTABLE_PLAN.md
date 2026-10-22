# OSCAR Turntable: 3D-Printed Base

Status: plan (2026-10-21). The Bambu Lab A1 is in hand, so the turntable base can be printed.
Servo code (`hardware/servo.py`) and calibration (`scripts/calibrate.py`) are still to be written;
this doc covers the physical part. Items marked **MEASURE** need a real number before CAD.

Supersedes the "Physical Build: Servo Turntable" section of `PLAN.md` only in detail; the concept
is unchanged: a bearing carries the weight, the servo only steers, plate angle = servo angle 1:1.

## Goal

A base that lets the Pi rotate the projector between the "wall" and "closet" aim points
repeatably, quietly, and without the servo carrying the projector's weight. Printed on the A1,
iterated cheaply, and parametric so a changed projector or servo means editing a number, not
redrawing.

## Mechanical concept

```
        projector
   ┌─────────────────┐
   │   top plate     │  rotates; servo horn bolted underneath
   ├───── bearing ───┤  lazy-susan ring (or printed ball race, see Options)
   │   base plate    │  fixed to desk/shelf; servo pocket in the centre
   └──── servo ──────┘  coaxial with the bearing, 5V from its own supply
```

- Servo axis = bearing axis, so there is no linkage and no angle math.
- The servo is *not* a structural part: side load goes through the bearing.
- A printed **mechanical stop** (a post on the base and a tab on the top plate) limits travel to
  just beyond the two aim angles, so a software bug cannot drive the servo into its end stops or
  tear the cable.

## Options (decide before printing)

| Option | Pros | Cons |
|---|---|---|
| Buy a lazy-susan ring (hardware store, 4-6 in) and print both plates | Smooth, cheap, strong, no print-quality risk in the bearing | Need to measure the bolt circle; wait for the part |
| Print a ball/roller race (PLA/PETG + 6-8 mm steel balls or 608 bearings) | Fully printed, all in one afternoon | Rougher; more tuning; ball retention is fiddly |
| Print a plain bushing/thrust washer pair | Simplest | Stiction at low angles; wears; only OK for a light projector |

**Recommendation:** lazy-susan ring + printed plates. Start with a plain-bushing prototype only
if the ring has not arrived and a first fit check is wanted.

## Measurements needed first (MEASURE)

- Projector: weight, footprint (L x W), foot positions, lens height and offset from the centre of
  the footprint (the lens should sit near the rotation axis, otherwise the beam swings sideways
  as well as turning; keep the centre of mass over the bearing).
- Servo: model (SG90 is plastic-geared and 180 degrees; check it is enough for the wall-closet
  angle; an MG90S or MG996R is the upgrade if the plate stalls or jitters). Case dimensions and
  horn spline.
- Angle between "wall" and "closet" aim points. If it exceeds ~170 degrees the SG90 range is not
  enough; a continuous-rotation or geared setup is a different design.
- Shelf/desk area available, and where the 5V supply and Pi sit.

## Print plan (Bambu A1)

- Bed 256 x 256 x 256 mm, so a plate up to ~250 mm fits in one piece.
- Material: **PETG** for plates (projector exhaust runs warm; PLA softens around 55-60 C).
  PLA is fine for fit-check coupons.
- Settings starting point: 0.2 mm layers, 4 walls, 30-40% gyroid infill for plates; 100% around
  bolt holes (or add heat-set inserts). Print plates flat so layers are not under tension.
- Add a thin rubber or TPU pad (or printed TPU feet) on the top plate so the projector does not
  slide, plus strap slots for a velcro strap.
- Cable path: through a central hole; slack for the rotation range, so no slip ring is needed.

## Steps

1. **A1 first print**: run the A1 calibration and a benchy-class test. Confirm it prints PETG
   cleanly (this is also the first real use of the printer).
2. **Measure** the projector, servo, bearing, and the two aim angles (above).
3. **Fit-check coupon** (~20 min print): servo pocket + horn bolt pattern + bearing bolt circle on a
   small plate. Adjust tolerances (start with 0.2 mm clearance per side).
4. **CAD**, parametric, kept in `hardware/cad/` (OpenSCAD or build123d so the source diffs in git;
   export `.3mf`/STL to `hardware/cad/out/`, not committed if large). Parameters: bearing bolt
   circle, servo case size, plate diameter, stop angles.
5. **Prototype print** in draft quality, assemble with the projector off the shelf, sweep the servo
   by hand with a throwaway test script.
6. **Final print** in PETG, mount the projector, supply, and Pi; run `scripts/calibrate.py` to find
   the real servo angles for "wall" and "closet".
7. **Hardening**: add the printed stops, cable retention, and a power-on position (servo should not
   snap to an arbitrary angle at boot; start `pigpiod`, then move to the last saved angle slowly).

## Risks and checks

- Servo stalls or jitters: check plate friction (bearing preload), weight, and supply current before
  blaming the servo. Servo gets its own 5V supply; common ground with the Pi.
- Wobble on the bearing makes the image shake on the wall; the plate must be stiff and the bolts
  tight. Test by projecting a grid and tapping the shelf.
- Repeatability: a servo is not a stepper; hitting the same angle each time is fine to about a
  degree, which is ~1-2 cm on the wall. The warp calibration (see `PROJECTION_PLAN.md`) absorbs a
  small residual, but not a big one.
- Heat: keep the projector's vents clear of the printed plate.

## Done when

- The projector sits on the plate and turns between both aim points on a servo command, with no
  grinding and no visible image shake once settled.
- Both angles are saved in `config/presets.json` and reproduce within about a degree on repeated moves.

## Open questions

- Which projector exactly (weight/footprint)? Which servo is on hand?
- Lazy-susan ring on hand, or print the race?
- Is a third aim point (for example the ceiling) wanted later? It would change the stop design.
