# OSCAR v1 Weekend Build — Voice-Controlled Servo Aim + Display Warp

## Context

OSCAR is a personal assistant projected onto dorm walls from a Raspberry Pi 4B (2GB), which is
the primary hub (a separate PC stays in reserve for future heavy compute like local LLMs or
gesture vision). Long-term the system will have RFID mode-switching, a gesture glove, and
LLM-driven natural-language schedule editing — all deferred. This weekend's scope is the
foundational physical + voice control loop, built so later features slot in without rework:

- Say the wake word **"oscar"** (or snap) to start listening.
- While listening, single-stage commands **"wall"** / **"closet"** rotate the projector via a
  servo turntable to a calibrated preset angle and swap the display's perspective-warp CSS to
  match that surface.
- **"schedule"** / **"hide"** show/hide the projected content.
- No STT or LLM involved yet — this is pure local keyword-spotting. The fallback path for
  free-form commands (schedule edits, etc.) gets added later by routing unrecognized speech to
  an API call, without touching this v1 loop.

Hardware confirmed in hand: Pi 4B (OS already set up, SSH working), ReSpeaker 2-Mic HAT (mics +
onboard RGB LEDs), a servo, a small speaker, an RC522 RFID reader with two dedicated tags, and
the projector.

**RFID mode switching is in v1 scope.** Tapping the "work" or "daily" tag sets a mode that
controls both which wall the projector defaults to *and* what content shows — Work mode aims at
the desk wall and filters the schedule to work-only events; Daily mode aims at the closet and
shows everything. Voice wall commands ("wall"/"closet") still work as a manual override on top of
whatever mode is active — they change the aim, not the content filter.

## Physical Build: Servo Turntable

Recommended design (simplest to build and reason about in a weekend, works regardless of servo
torque since the bearing — not the servo — carries the projector's weight):

- A **lazy-susan bearing** (flat ball-bearing ring, cheap at any hardware store) sandwiched
  between a stationary base plate (fixed to the desk/shelf) and a rotating top plate that the
  projector sits on/is strapped to.
- The servo mounts to the base, coaxial with the bearing's center hole, with its horn bolted
  directly to the underside of the rotating top plate. Servo angle = plate angle, 1:1, no linkage
  math needed.
- Power the servo from a **separate 5V supply (or UBEC)**, not the Pi's own rail — servo current
  spikes can brown out the Pi otherwise.
- Sweep the servo through its range with a throwaway test script first to find the two rough
  target angles for "wall" and "closet" before fine calibration.

## Software Architecture

Two small services plus shared config, all on the Pi. Voice keywords, snap detection, and RFID
taps are all just different inputs feeding the same command router inside the control daemon, so
adding RFID doesn't create a parallel system — it's one more input source.

**1. Control daemon** (`voice/daemon.py`) — voice + RFID + snap, one process
- Runs the audio-based inputs (keyword spotting, snap detection) on one thread and RFID polling
  on another; both call into the same internal command router so behavior stays consistent
  regardless of input source.
- Uses **Porcupine** (`pvporcupine`) for keyword spotting — free Picovoice account needed to
  generate custom `.ppn` keyword files for: `oscar`, `wall`, `closet`, `schedule`, `hide`, `sleep`.
- Simple state machine: `IDLE` → (hear "oscar" **or** snap detected) → `AWAKE` → command keywords
  act immediately (no need to repeat "oscar") → inactivity timeout or "sleep" keyword returns to
  `IDLE`.
- Snap detection (`voice/snap_detector.py`): lightweight energy/onset spike detector run in
  parallel on the same audio stream, treated as equivalent to hearing "oscar".
- LED feedback via the ReSpeaker HAT's onboard RGB LEDs (`hardware/leds.py`, using Seeed's
  `pixel_ring` library): the base/idle color reflects current **mode** (blue = daily, red = work),
  pulsing = awake/listening, a quick white flash = command recognized, amber flash = unrecognized
  (kept distinct from red/blue so it's never confused with a mode color).
- RFID (`hardware/rfid.py`, RC522 over SPI via the `mfrc522` library): polls for a tag scan on its
  own thread. Each of the two tag UIDs is mapped in config to a mode (`work`/`daily`). A scan sets
  the active mode, moves the servo to that mode's default wall preset, and tells the display app
  to re-filter the schedule — same router call a voice command would make, just triggered by a
  tag instead of a keyword.
- Spoken confirmations: **pre-recorded short audio clips** ("Switching to closet", "Showing
  schedule", etc.) played via `aplay` — no TTS engine needed for a fixed, tiny phrase set. Real
  TTS becomes worthwhile later when responses are LLM-generated and open-ended.
- On a recognized command, calls into `hardware/servo.py` (move to preset angle) and hits the
  display app's local HTTP endpoint (swap warp + show/hide).

**2. Display app** (`display/app.py`)
- Small Flask app serving one page, shown full-screen via `chromium-browser --kiosk` pointed at
  `localhost`.
- Each wall preset is a CSS class using `transform: perspective(...) rotateX(...) rotateY(...)`
  (simpler to hand-tune than a full 4-point homography matrix; upgrade to matrix3d corner-pinning
  later only if a flat perspective tilt isn't enough for a given surface).
- A WebSocket (`flask-socketio` or plain `websockets`) pushes preset-switch / show-hide / mode
  events from the control daemon to the already-open kiosk page instantly, instead of reloading.
- Schedule content for v1 is a static/hand-edited JSON list of events, each tagged with a
  `category` (e.g. `"work"`). Daily mode shows everything; Work mode shows only `category ==
  "work"` events. Voice-driven editing is explicitly deferred to the future LLM-backed phase.

**3. Shared config**

`config/presets.json` — walls, modes, and tag-to-mode mapping in one place:
```
{ "walls": {
    "wall":   { "servo_angle": <int>, "warp": { "rotateX": .., "rotateY": .., "perspective": .. } },
    "closet": { "servo_angle": <int>, "warp": { ... } } },
  "modes": {
    "work":  { "default_wall": "wall",   "schedule_filter": "work" },
    "daily": { "default_wall": "closet", "schedule_filter": null } },
  "rfid_tags": { "<uid-1>": "work", "<uid-2>": "daily" } }
```
`config/schedule.json` — list of `{title, time, category}` events.

Both services read these files; a small `scripts/calibrate.py` CLI lets you nudge servo angle and
warp values live while looking at the actual wall, then save. A `scripts/scan_uid.py` throwaway
script reads and prints a tag's UID so you can copy it into `rfid_tags`.

### Project structure
```
OSCAR/
  voice/daemon.py, voice/snap_detector.py, voice/keywords/*.ppn
  display/app.py, display/templates/index.html, display/static/{style.css,app.js}
  hardware/servo.py, hardware/leds.py, hardware/rfid.py
  config/presets.json, config/schedule.json
  scripts/calibrate.py, scripts/scan_uid.py
  systemd/oscar-control.service, systemd/oscar-display.service
  requirements.txt
```
Dependencies: `pvporcupine`, `pigpio` (jitter-free servo PWM — daemon must be enabled), `flask`,
`flask-socketio`, `sounddevice` or `pyaudio` (mic capture for Porcupine), `mfrc522` + `spidev`
(RFID), Seeed's `pixel_ring` (LEDs).

## Weekend Schedule

**Day 1 — Hardware bring-up (assemble + verify each piece in isolation, no integration yet)**
1. Mount ReSpeaker HAT, install `seeed-voicecard` drivers, confirm mic capture (`arecord`) and
   LED control (Seeed's example script) work.
2. Build the bearing + servo turntable, mount the projector, wire servo to its own 5V supply,
   confirm rotation with a throwaway `pigpio` sweep script; note two rough target angles.
3. Wire the speaker, confirm playback (`aplay` a test clip).
4. Wire the RC522 reader over SPI, run `scripts/scan_uid.py` against both tags to get their UIDs.

**Day 2 — Software integration**
1. Create Picovoice account + custom keyword files for all six words.
2. Write the control daemon's state machine + snap detector + RFID polling + LED feedback
   (mode-colored idle state, listening pulse, recognized/error flashes).
3. Write the Flask display app + kiosk page with the CSS warp classes and schedule-category
   filtering; wire it to the control daemon via HTTP/WebSocket.
4. Calibrate both wall presets for real against your actual walls using `scripts/calibrate.py`;
   drop the two tag UIDs from Day 1 into `rfid_tags`.
5. Set up `systemd` services so kiosk browser, display app, control daemon, and `pigpiod` all
   auto-start on boot.

## Verification

- Manual end-to-end pass: say "oscar" → LEDs pulse (in current mode's color) → say "closet" →
  servo rotates, display re-warps for that wall within a second or two → say "schedule" → content
  appears → say "hide" → content disappears → say "sleep" → LEDs return to idle mode color.
- Tap the "work" tag → servo moves to the desk wall, display filters to work-only events, LED
  base color switches to red. Tap "daily" → closet wall, full schedule, LED switches to blue.
  Confirm a voice "wall"/"closet" override afterward changes aim without changing the content
  filter.
- Confirm the loop survives a reboot (all services come up via `systemd` with no manual steps).
- Test snap-to-wake as an alternate trigger for the same "oscar" transition.
