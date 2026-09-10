# OSCAR — User Stories & Feature Backlog

Status legend: **v1** = this weekend's build ([PLAN.md](PLAN.md)) · **Next** = near-term, planned
but not yet designed in detail · **Backlog** = longer-term roadmap idea, not yet committed.

---

## Epic 1 — Wake & Attention

### US-1 · Wake by voice — `v1`
As the user, I want to say "oscar" to wake the system, so that it starts listening for a command
without me touching anything.
- **Acceptance criteria:** Saying "oscar" transitions the system from idle to listening within
  ~1s; LEDs change from idle color to a pulsing "listening" state.
- **Tasks:** Picovoice account + custom `.ppn` for "oscar"; control daemon `IDLE → AWAKE`
  transition; LED pulse state.

### US-2 · Wake by snap — `v1`
As the user, I want a finger snap to work as an alternate wake trigger, so that I can get the
system's attention even when my hands are full or speaking isn't convenient.
- **Acceptance criteria:** A snap produces the same `IDLE → AWAKE` transition and LED feedback as
  saying "oscar."
- **Tasks:** Onset/energy-spike detector (`voice/snap_detector.py`) running on the same audio
  stream as keyword spotting.

### US-3 · Return to idle — `v1`
As the user, I want the system to stop actively listening for commands after I'm done or after a
pause, so that it doesn't sit in an active state indefinitely.
- **Acceptance criteria:** Saying "sleep," or a period of silence (inactivity timeout), returns
  the system to `IDLE` and LEDs return to the mode-colored idle state.
- **Tasks:** Inactivity timer in the control daemon's state machine; "sleep" keyword file.

---

## Epic 2 — Physical Projection Control

### US-4 · Aim the projector by voice — `v1`
As the user, I want to say "wall" or "closet" while the system is listening, so that the
projector physically rotates to face that surface without me touching it.
- **Acceptance criteria:** Command triggers a servo move to that wall's calibrated angle; display
  content re-warps to match within a couple seconds.
- **Tasks:** `hardware/servo.py` (pigpio angle control); keyword files for "wall"/"closet";
  command router wiring.

### US-5 · Per-wall image correction — `v1`
As the user, I want the projected image to look properly rectangular on each wall regardless of
the projector's angle to that surface, so that content is readable and not visibly skewed.
- **Acceptance criteria:** Each wall preset has its own saved CSS perspective-warp values;
  switching walls swaps the warp instantly along with the servo move.
- **Tasks:** CSS `perspective`/`rotateX`/`rotateY` warp classes; `scripts/calibrate.py` for
  live tuning; values stored in `config/presets.json`.

### US-6 · One-time calibration workflow — `v1`
As the user, I want a simple way to dial in each wall's servo angle and warp once, so that I
don't have to guess values or edit raw config by hand.
- **Acceptance criteria:** Running `scripts/calibrate.py` lets me nudge servo angle and warp
  parameters live while looking at the wall, then save to config.
- **Tasks:** Interactive CLI reading/writing `config/presets.json`.

### US-7 · Reliable turntable hardware — `v1`
As the user, I want the servo turntable to support the projector's weight and rotate smoothly
between presets, so that the mechanism doesn't strain or degrade over repeated use.
- **Acceptance criteria:** Bearing carries the projector's weight (not the servo); servo powered
  from a separate 5V supply; cabling has enough slack for the full rotation range.
- **Tasks:** Build bearing + servo turntable; wire dedicated servo power.

---

## Epic 3 — RFID Mode Switching

### US-8 · Switch mode by tapping a tag — `v1`
As the user, I want to tap a "work" or "daily" RFID tag, so that the system switches context
without needing a voice command.
- **Acceptance criteria:** Tapping a known tag sets the active mode; unknown tags are ignored.
- **Tasks:** `hardware/rfid.py` (RC522 polling thread); `scripts/scan_uid.py` to read tag UIDs;
  `rfid_tags` map in `config/presets.json`.

### US-9 · Mode-driven default wall — `v1`
As the user, I want each mode to have its own default wall, so that tapping "work" automatically
points the projector at my desk and "daily" points it at the closet.
- **Acceptance criteria:** Mode switch triggers the same servo-move path as a voice wall command,
  using that mode's `default_wall`.
- **Tasks:** `default_wall` field per mode in config; command router calls shared servo-move logic
  from both RFID and voice paths.

### US-10 · Mode-filtered schedule content — `v1`
As the user, I want Work mode to show only work-related events and Daily mode to show everything,
so that the display is relevant to what I'm currently doing.
- **Acceptance criteria:** Schedule events are tagged with a `category`; Work mode filters to
  `category == "work"`, Daily mode shows all events.
- **Tasks:** `category` field in `config/schedule.json`; filtering logic in the display app.

### US-11 · Voice override without losing mode — `v1`
As the user, I want to manually redirect the projector with a voice command while a mode is
active, so that I can look at the other wall temporarily without changing what content mode I'm
in.
- **Acceptance criteria:** A voice "wall"/"closet" command after a mode is set changes aim only;
  the content filter stays on the active mode until the next RFID tap.
- **Tasks:** Keep "current aim" and "current mode" as independent state variables in the control
  daemon.

---

## Epic 4 — Display & Feedback

### US-12 · Show/hide projected content by voice — `v1`
As the user, I want to say "schedule" or "hide," so that I can bring up or clear the display
without walking over to a device.
- **Acceptance criteria:** "schedule" shows the current mode's filtered content; "hide" blanks
  the projected page.
- **Tasks:** Flask endpoints + WebSocket push for show/hide; keyword files.

### US-13 · At-a-glance mode/status via LEDs — `v1`
As the user, I want the ReSpeaker HAT's LEDs to reflect what the system is doing, so that I get
feedback without needing to look at the wall.
- **Acceptance criteria:** Idle color reflects active mode (blue = daily, red = work); pulsing =
  listening; white flash = command recognized; amber flash = unrecognized command.
- **Tasks:** `hardware/leds.py` using Seeed's `pixel_ring` library; state-to-color mapping.

### US-14 · Spoken confirmation of actions — `v1`
As the user, I want to hear a short spoken confirmation when a command is executed, so that I
know it registered even if I'm not looking at the wall.
- **Acceptance criteria:** Each recognized command plays a matching pre-recorded audio clip
  through the speaker.
- **Tasks:** Record/generate short clips for each command; playback via `aplay`.

### US-15 · Survives reboots unattended — `v1`
As the user, I want the whole system to come back up on its own after a power cycle or reboot, so
that I never have to SSH in and manually start services.
- **Acceptance criteria:** Kiosk browser, display app, control daemon, and `pigpiod` all
  auto-start with no manual steps after boot.
- **Tasks:** `systemd/oscar-control.service`, `systemd/oscar-display.service`, kiosk autostart.

---

## Epic 5 — Natural-Language Control (Next)

### US-16 · Free-form voice commands beyond the fixed vocabulary
As the user, I want to say something that isn't one of the fixed keywords and still have it
understood, so that I'm not limited to a small memorized command list.
- **Acceptance criteria:** An utterance that doesn't match a known keyword is recorded and sent
  to a cloud LLM/STT for intent parsing, falling back gracefully if the network is unavailable.
- **Tasks:** Design the "unrecognized → record → send to API" fallback path in the control
  daemon; choose STT approach (cloud API vs. on-device).

### US-17 · Edit the schedule by voice
As the user, I want to add, move, or remove schedule events by speaking naturally (e.g. "move my
2pm to 4pm"), so that I don't have to manually edit a config file.
- **Acceptance criteria:** A natural-language edit request updates `config/schedule.json`
  (or its successor data store) and the display reflects the change immediately.
- **Tasks:** Intent parsing via LLM API; schedule data store with edit operations; likely needs a
  real database instead of static JSON once edits are in scope.

---

## Epic 6 — Sensing & Gesture (Backlog)

### US-18 · Gesture control via sensor glove
As the user, I want to control OSCAR with hand gestures using a sensor-equipped glove, so that I
have a hands-free, voice-free input option.
- **Acceptance criteria:** TBD — depends on glove sensor choice (flex sensors, IMU) and BLE
  pairing with the Pi.
- **Tasks:** Not yet designed. Pi 4B's onboard Bluetooth is the planned receiver.

### US-19 · Camera-based gesture recognition
As the user, I want the system to recognize hand gestures via camera instead of (or in addition
to) the glove, so that gesture control doesn't require wearing hardware.
- **Acceptance criteria:** TBD — depends on camera source (iPhone vs. future Pi Camera Module)
  and vision pipeline (e.g. Mediapipe), likely offloaded to the reserve PC.
- **Tasks:** Not yet designed.

### US-20 · iPhone as a camera/mic control panel
As the user, I want to optionally use my iPhone as an additional mic and camera input, so that I
have a mobile control surface beyond the fixed Pi-mounted hardware.
- **Acceptance criteria:** TBD — needs either a native companion app or a web app; web app
  requires HTTPS for iOS camera/mic access via `getUserMedia`.
- **Tasks:** Not yet designed; deprioritized since the ReSpeaker HAT now covers always-on mic
  duty locally.

### US-21 · Additional RFID interaction patterns
As the user, I want to explore more uses for RFID beyond mode switching, so that tagging becomes
a more general-purpose input.
- **Ideas (not yet committed):** location tags mounted at the closet/desk that redirect the
  projector on tap (complementing voice); additional scene tags beyond work/daily (e.g. movie,
  sleep) since the reader can distinguish unlimited unique UIDs; a door-mounted tag for
  entry/exit automation (arrive = wake to daily mode, leave = sleep).
- **Tasks:** Not yet designed.

---

## Epic 7 — Infrastructure (Backlog)

### US-22 · Offload heavy compute to the reserve PC
As the user, I want a way to route compute-heavy tasks (local LLM inference, real-time gesture
vision) to my PC instead of the Pi, so that the Pi stays responsive for its core orchestration
role.
- **Acceptance criteria:** TBD — needs a defined protocol (HTTP/MQTT) between Pi and PC and a
  clear boundary for what runs where.
- **Tasks:** Not yet designed; PC currently idle/reserved with no integration built.
