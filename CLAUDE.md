# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

OSCAR is a voice/RFID-controlled wall projector assistant running on a Raspberry Pi 4B (2GB). **All source files are currently empty stubs**; the only real content is `docs/PLAN.md` (the authoritative design, build schedule, and verification checklist) and `docs/USER_STORIES.md` (feature backlog, US-1..US-22). Read PLAN.md before implementing anything. There is no build system, linter, or test suite yet; `requirements.txt` is the only tooling file.

**Architecture update (2026-10-19):** the PC does heavy compute and the Pi is an always-on hub (tab-switching display, servo, RFID, tracker, PC/projector power). See `docs/PI_HUB_PLAN.md`, which overrides PLAN.md where they conflict.

**Interview prep (standing rule):** the user may need to discuss this project in interviews. At the end of every working session, update `docs/INTERVIEW_PREP.md` (status table, design decisions, problems solved, talking points, session log) and add the day's entry to `docs/CHANGELOG.md`. Keep "built / tested / planned" claims honest.

**Physical/projection plans (2026-10-21):** `docs/TURNTABLE_PLAN.md` (3D-printed turntable base on the Bambu A1; **driven by a stepper (28BYJ-48 + ULN2003 from the kit), not a servo**: open-loop, needs a homing switch; planned `hardware/turntable.py` replaces `servo.py`, and `presets.json` uses `angle_deg` instead of `servo_angle`) and `docs/PROJECTION_PLAN.md` (per-wall `matrix3d` corner warp via a `/stage` wrapper page; replaces PLAN.md's CSS-class warp).

The wake-word approach is a self-trained TFLite keyword model (not Picovoice); PLAN.md wins on any conflict with USER_STORIES.md.

## Architecture (from PLAN.md)

Two processes on the Pi plus shared JSON config. Every input source feeds one command router, so voice, snap and RFID behave identically.

- **Control daemon** (`voice/daemon.py`): audio thread (keyword spotting + snap detection on the same mic stream) and an RFID polling thread, both calling the same router. State machine: `IDLE` -> ("oscar" or snap) -> `AWAKE` -> commands act immediately -> inactivity timeout or "sleep" -> `IDLE`. The router drives `hardware/servo.py` (pigpio), `hardware/leds.py` (ReSpeaker `pixel_ring`), `aplay` clips for spoken confirmation, and HTTP calls to the display app.
- **Display app** (`display/app.py`): Flask + WebSocket (flask-socketio) page shown by `chromium-browser --kiosk` on localhost. Wall presets are CSS `perspective/rotateX/rotateY` classes. The daemon pushes preset/show-hide/mode events over the socket instead of reloading the page.
- **Keyword model** (planned `voice/kws.py`, `voice/model/train.py`): log-mel spectrogram of a ~1s sliding window, small CNN, softmax over `oscar, wall, closet, schedule, hide, sleep` plus `background/unknown`. Trained off-Pi with TensorFlow, exported as int8 TFLite, and run on the Pi with `tflite-runtime` every ~100-200ms with threshold + debounce. Only the `.tflite` and `tflite-runtime` ship to the Pi. `voice/model/data/` is raw/augmented recordings and is not committed.

### Design constraints to preserve

- **Aim and mode are independent state.** RFID taps set mode, which sets both the default wall (servo) and the schedule filter. Voice "wall"/"closet" changes only the aim, never the mode or content filter (US-11).
- Mode colors: LED idle blue = daily, red = work. Amber is reserved for "unrecognized", so never use it for a mode.
- The servo needs its own 5V supply, and the `pigpiod` daemon must be running for jitter-free PWM.
- Keep the router input-agnostic: the deferred LLM/STT fallback (US-16/17) is meant to be added by routing unrecognized speech to an API call without changing the v1 loop.

### Config

- `config/presets.json`: `walls` (servo_angle + warp params), `modes` (default_wall, schedule_filter), `rfid_tags` (UID -> mode). Schema is in PLAN.md.
- `config/schedule.json` (not yet created): `{title, time, category}` events; work mode shows only `category == "work"`.
- `scripts/calibrate.py` live-tunes servo angle and warp and saves to presets.json. `scripts/scan_uid.py` prints an RFID tag UID to copy into `rfid_tags`.

## Environment

Target is Raspberry Pi OS with the `seeed-voicecard` driver (ReSpeaker 2-Mic HAT), SPI enabled for the RC522, and `pigpiod` enabled. Hardware modules (`pigpio`, `mfrc522`, `spidev`, `pixel_ring`) will not import or work on a dev laptop, so keep hardware access behind `hardware/*` so the router and display can be tested without it. Planned `systemd` units: `oscar-control.service`, `oscar-display.service`.

Install: `pip install -r requirements.txt` (training-side `tensorflow` is intentionally excluded).

## Habit tracker (`tracker/`)

Separate Flask + SQLite service (port 5001), planned in `docs/HABIT_TRACKER_PLAN.md`. All state changes go through `tracker/actions.py` (`dispatch`), which the web UI, voice, RFID and gestures all share. `progression.py` holds the XP/level constants and `stats.py` the streak/strength/chart queries; neither touches Flask or hardware. Run: `python -m tracker.app`; tests: `python -m unittest discover -s tests`; demo data: `OSCAR_TRACKER_DB=data/demo.db python scripts/seed_demo.py`.
