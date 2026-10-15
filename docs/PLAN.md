# OSCAR v1 Build — Voice-Controlled Servo Aim + Display Warp

## Context

OSCAR is a personal assistant projected onto dorm walls from a Raspberry Pi 4B (2GB), which is
the primary hub (a separate PC stays in reserve for future heavy compute like local LLMs or
gesture vision). Long-term the system will have RFID mode-switching, a gesture glove, and
LLM-driven natural-language schedule editing — all deferred. This build's scope is the
foundational physical + voice control loop, built so later features slot in without rework. The
keyword-spotting model is self-trained rather than a paid wake-word service, which stretches the
timeline past a single weekend (see "Wake Word / Keyword Model" below):

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
- Uses a **self-trained keyword-spotting model** (no paid wake-word service) for: `oscar`, `wall`,
  `closet`, `schedule`, `hide`, `sleep`. A small CNN (depthwise-separable convs, same family as
  Google's Speech Commands reference model) classifies log-mel spectrogram windows into one of the
  six keywords or a `background`/`unknown` class, trained on recordings of yourself saying each
  keyword plus negative data from the public Speech Commands dataset and ambient room noise.
  Exported to **TFLite (int8 quantized)** so inference runs continuously on the Pi 4B. See
  "Wake Word / Keyword Model" below for the data + training pipeline.
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
  voice/daemon.py, voice/snap_detector.py, voice/kws.py
  voice/model/train.py, voice/model/data/, voice/model/keyword_model.tflite
  display/app.py, display/templates/index.html, display/static/{style.css,app.js}
  hardware/servo.py, hardware/leds.py, hardware/rfid.py
  config/presets.json, config/schedule.json
  scripts/calibrate.py, scripts/scan_uid.py
  systemd/oscar-control.service, systemd/oscar-display.service
  requirements.txt
```
Dependencies: `tflite-runtime` (on-device inference), `numpy`, `librosa` (feature extraction —
training side only), `pigpio` (jitter-free servo PWM — daemon must be enabled), `flask`,
`flask-socketio`, `sounddevice` or `pyaudio` (mic capture), `mfrc522` + `spidev` (RFID), Seeed's
`pixel_ring` (LEDs). Training itself happens off-Pi (laptop/desktop) using `tensorflow` — only the
exported `.tflite` model and `tflite-runtime` ship to the Pi.

## Wake Word / Keyword Model (self-trained, replaces a paid wake-word engine)

Framed as small-footprint keyword spotting (KWS), not general speech recognition: a sliding ~1s
audio window → log-mel spectrogram → small CNN → softmax over the 6 keywords + a
`background`/`unknown` class. Same architecture family as Google's Speech Commands reference
model — small enough to run continuously on a Pi 4B.

**Data collection**
- Record yourself (and ideally a couple other voices) saying each of the 6 keywords 100+ times,
  varied tone/distance/background, using the actual ReSpeaker mic in the actual dorm room —
  training acoustics should match deployment acoustics.
- Negative/`background` class: public **Speech Commands dataset** (free, 30 common words, built
  for exactly this) plus a chunk of recorded ambient room noise (fan, hallway chatter, silence).
- Augmentation script (pitch/speed shift, add noise, reverb) to stretch a modest recording session
  into a usable training set.

**Training**
- Train the CNN on spectrogram features in Keras/TensorFlow (runs fine on a laptop CPU/GPU, not
  the Pi).
- Export to **TFLite, int8 quantized**, for Pi inference.
- Iterate: first model will likely have false triggers or miss quiet speech — expect a few
  cycles of "record more data for the failure cases → retrain → test live in the room" before
  it's reliable. This loop is the main time sink, not the initial training run.

**Pi-side inference loop**
- Continuous ring buffer of mic audio → run inference every ~100-200ms on the trailing window →
  threshold + debounce to avoid re-triggering → emit the recognized keyword into the same command
  router `daemon.py` already uses, so the rest of the architecture (state machine, LED feedback,
  router dispatch) is unaffected by this swap.

**Added project paths:** `voice/model/train.py` (training script), `voice/model/data/` (raw +
augmented recordings, not committed), `voice/model/keyword_model.tflite` (exported model),
`voice/kws.py` (Pi-side ring buffer + inference, replaces the Porcupine wrapper).

**Time cost:** budget roughly 1.5-3 focused days for this piece specifically (data collection,
learning the pipeline if new to it, training, and — the unpredictable part — iterating against
real false positives/negatives in the actual room), on top of the hardware bring-up and
integration work below. Realistically this pushes the build past a single weekend; the schedule
below treats keyword-model work as its own phase rather than squeezing it into Day 2.

## Build Schedule

**Day 1 — Hardware bring-up (assemble + verify each piece in isolation, no integration yet)**
1. Mount ReSpeaker HAT, install `seeed-voicecard` drivers, confirm mic capture (`arecord`) and
   LED control (Seeed's example script) work.
2. Build the bearing + servo turntable, mount the projector, wire servo to its own 5V supply,
   confirm rotation with a throwaway `pigpio` sweep script; note two rough target angles.
3. Wire the speaker, confirm playback (`aplay` a test clip).
4. Wire the RC522 reader over SPI, run `scripts/scan_uid.py` against both tags to get their UIDs.

**Day 2 — Keyword model (its own phase, off-Pi)**
1. Record 100+ samples per keyword (6 words) with the ReSpeaker mic, in the actual room.
2. Pull Speech Commands dataset + record ambient room noise for the `background` class; run the
   augmentation script.
3. Train the CNN in TensorFlow on a laptop/desktop; export to int8-quantized TFLite.
4. Test the exported model live against the mic; iterate on data for whatever false triggers or
   misses show up. Budget this as the open-ended part of the schedule.

**Day 3 — Software integration**
1. Write `voice/kws.py` (ring buffer + TFLite inference loop) and the control daemon's state
   machine + snap detector + RFID polling + LED feedback (mode-colored idle state, listening
   pulse, recognized/error flashes).
2. Write the Flask display app + kiosk page with the CSS warp classes and schedule-category
   filtering; wire it to the control daemon via HTTP/WebSocket.
3. Calibrate both wall presets for real against your actual walls using `scripts/calibrate.py`;
   drop the two tag UIDs from Day 1 into `rfid_tags`.
4. Set up `systemd` services so kiosk browser, display app, control daemon, and `pigpiod` all
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
