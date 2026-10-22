# OSCAR Turntable: 3D-Printed Base

Status: plan (2026-10-21, updated same day: **stepper motor instead of servo**). The Bambu Lab A1 is
in hand, so the base can be printed. Motor code (`hardware/turntable.py`) and calibration
(`scripts/calibrate.py`) are still to be written; this doc covers the physical part. Items marked **MEASURE** need a real number before CAD.

Supersedes the "Physical Build: Servo Turntable" section of `PLAN.md` only in detail; the concept
is unchanged: a bearing carries the weight and the motor only turns the plate. What changes with a
stepper: it is open-loop (no idea where it is at power-up, so it needs a homing switch) and has no
180 degree limit.

## Goal

A base that lets the Pi rotate the projector between the "wall" and "closet" aim points
repeatably, quietly, and without the motor carrying the projector's weight. Printed on the A1,
iterated cheaply, and parametric so a changed projector or motor means editing a number, not
redrawing.

## Motor choice

The kit's **28BYJ-48 (5V, geared) + ULN2003 driver board** is the starting point: already owned,
4 GPIO pins, no extra supply voltage.

| | 28BYJ-48 (kit) | NEMA 17 + A4988/DRV8825 (upgrade) |
|---|---|---|
| Resolution | 2048 steps/rev (4096 half-steps), ~0.09 deg | 200 steps/rev (1.8 deg), 1/16 microstep ~0.11 deg, needs a gear or belt for finer |
| Speed | slow, ~10-15 RPM max (a 90 degree turn in a few seconds; fine for a wall) | fast |
| Torque | low, ~0.3 kg-cm after the gearbox; enough with a bearing and a light projector | high |
| Backlash | some in the gearbox (~1 deg); calibrate by always approaching a target from the same side | little |
| Power | 5V, its own supply; ~240 mA when energized | 12V supply + driver; current limit to set |
| Cost | free | new parts |

Plan: build with the 28BYJ-48; switch to NEMA 17 (printed motor mount is parametric) only if the
plate stalls or skips steps with the real projector. Do not drive the motor from the Pi's 5V pin.

## Mechanical concept

```
        projector
   ┌─────────────────┐
   │   top plate     │  rotates; driven by the motor (see Drive options)
   ├───── bearing ───┤  lazy-susan ring (or printed ball race, see Options)
   │   base plate    │  fixed to desk/shelf; motor pocket + homing switch
   └── stepper ──────┘  5V from its own supply, ULN2003 board on the Pi's GPIO
```

- The motor is *not* a structural part: side load goes through the bearing.
- **Drive options**: (a) direct: the 28BYJ-48's output shaft is off-centre of its body, so a
  coaxial mount means the body hangs off-axis; the shaft goes straight into a printed hub on the
  plate underside (1:1, simplest, uses the full 4096 half-steps/rev as the angle resolution);
  (b) a printed gear ring or friction wheel on the plate edge with the motor beside the bearing
  (needs a ratio in software; gives more torque and frees the centre for the cable). Start with (a).
- **Homing**: a stepper has no absolute position. Fix a small switch (the kit has push buttons
  and a vibration switch; a limit microswitch or hall sensor + magnet is nicer) at a known
  angle and print a flag on the plate that trips it. On boot the motor turns slowly toward the
  switch, sets angle 0 at the trigger, then goes to the wall or closet angle. Hard stops
  (printed post + tab) remain as a safety limit if homing ever fails.
- **No servo-style limit**: travel is not limited to 180 degrees, so the wall and closet can be any
  angle apart; the cable still limits it to under one full turn unless a slip ring is added later.

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
- Motor: 28BYJ-48 body dimensions, shaft (5 mm with two flats) and mounting-ear spacing, from
  calipers, not a datasheet.
- Angle between "wall" and "closet" aim points (any value works now, but it sets the cable slack
  needed and where the homing flag goes).
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
2. **Measure** the projector, motor, bearing, and the two aim angles (above).
3. **Fit-check coupon** (~20 min print): motor pocket + shaft hub + bearing bolt circle + homing switch seat on a
   small plate. Adjust tolerances (start with 0.2 mm clearance per side).
4. **CAD**, parametric, kept in `hardware/cad/` (OpenSCAD or build123d so the source diffs in git;
   export `.3mf`/STL to `hardware/cad/out/`, not committed if large). Parameters: bearing bolt
   circle, motor body/ear dimensions, hub size, plate diameter, homing-flag and stop angles.
5. **Prototype print** in draft quality, assemble with the projector off the shelf, spin the motor
   by hand with a throwaway test script (half-step sequence on the 4 ULN2003 pins).
6. **Final print** in PETG, mount the projector, supply, and Pi; run `scripts/calibrate.py` to find
   the real angles for "wall" and "closet" (measured from the home switch).
7. **Hardening**: add the printed stops, cable retention, and a power-on position (home on boot, then go to the last aim; release the coils after each move so the
   28BYJ-48 and driver do not sit hot).

## Risks and checks

- Skipped steps: open-loop motors lose steps silently if overloaded or driven too fast. Keep the
  step rate low (start ~1-2 ms per half-step), add acceleration if needed, and re-home on every boot
  and whenever the homing switch is passed. A stalled plate means check friction, weight and supply
  current before blaming the motor. The motor gets its own 5V supply with common ground to the Pi.
- Backlash and repeatability: the 28BYJ-48's gearbox has about 1 degree of slop (~1-2 cm on the
  wall). Always approach each target from the same direction. The warp calibration (see
  `PROJECTION_PLAN.md`) absorbs a small residual, not a big one.
- Wobble on the bearing makes the image shake on the wall; the plate must be stiff and the bolts
  tight. Test by projecting a grid and tapping the shelf.
- Heat: coils energized at rest get warm; release them when idle (the plate stays put because of
  bearing friction and the gearbox). Keep the projector's vents clear of the printed plate.
- Mains/other loads: the ULN2003 board drives the coils from 5V only; never connect it to the
  kit's 9V battery cable.

## Done when

- The projector sits on the plate and turns between both aim points on a command, with no
  grinding and no visible image shake once settled.
- Homing works from cold, and both angles saved in `config/presets.json` reproduce within about a
  degree on repeated moves with no accumulating drift after 50 back-and-forth runs.

## Open questions

- Which projector exactly (weight/footprint)? Is the kit's 28BYJ-48 strong enough, or is a NEMA 17 needed?
- Lazy-susan ring on hand, or print the race?
- Is a third aim point (for example the ceiling) wanted later? It would change the stop design.
