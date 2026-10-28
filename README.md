# OSCAR

A wall-projected personal assistant built around a Raspberry Pi 4B (2 GB). Tap an RFID tag and the
projector shows the matching page (a habit tracker I wrote) on the wall, warped so it lands as a
clean rectangle. The long-term plan adds voice and gesture control and a motorised turntable that
aims the projector at different walls.

The design is a small distributed system: the **Pi is an always-on hub** (display, RFID, tracker,
power control) and the **desktop PC does the heavy compute** (voice model, vision) when it is awake.
Every input source (RFID, voice, gesture) is meant to feed one command router, so they all behave
the same.

## Status

| Part | State |
|---|---|
| Habit tracker (`tracker/`) | Built, tested, used on the real projector |
| RFID tap switches Chromium tabs (`display/tabs.py`, `scripts/routine.py`) | Built, tested |
| Per-wall projection warp (`display/warp.py`, `display/app.py`) | Built and unit-tested; `/stage` warp seen working in a browser. Not yet calibrated on the Pi or projector |
| Start everything at boot (`systemd/`) | Written, syntax-checked; not yet run on the Pi |
| Phone mic/camera page (`sensor/`), PC wake over SSH (`pc/`) | Built; not tried on real hardware |
| Assistant (`assistant/`): Claude tool-use loop, transcript-based wake word, phone mic streaming | Built and unit-tested; not started at boot and not yet run end to end on a phone |
| Local open models (Hunyuan3D image->3D, Qwen3 assistant) and 3D-print handoff | Planned (`docs/LOCAL_AI_PLAN.md`) |
| Trained keyword model, command router, stepper turntable, LEDs, projector power (IR) | Designed only |

See `docs/` for the plans and `docs/CHANGELOG.md` for what changed when.

## What each part does

- **`tracker/`**: Flask + SQLite habit tracker on port 5001 (XP, levels, streaks, charts). Every
  change goes through one function, `tracker/actions.py` `dispatch`, so the web UI, RFID and later
  voice/gestures share it. `?wall=1` is a high-contrast theme for the projector.
- **`display/`**: the display service on port 5000.
  - `tabs.py` keeps Chromium tabs open and switches between them over its debugging port, so a tag
    tap is instant.
  - `app.py` + `warp.py` + `static/` pin a page's four corners to the quad you calibrated, so an
    off-axis projector still gives a rectangle. Every open tab re-warps live.
- **`hardware/`**: drivers for the RFID reader, LCD, buzzer and PC power-button relay. Imports of
  hardware libraries stay in here so the rest runs on a laptop.
- **`pc/`**: wakes the sleeping desktop (GPIO power-button pulse) and unlocks it over SSH.
- **`assistant/`**: the brain. `agent.py` runs a tool-use loop over habit, page and PC tools;
  `listener.py` cuts audio into utterances, transcribes them with Whisper and `wake.py` checks for
  "Oscar". `python -m assistant` is a typed version. Run the phone-driven version with
  `OSCAR_ASSISTANT=1 python -m sensor.app` (needs `ANTHROPIC_API_KEY`); then tap "Start mic" and
  "Start assistant" on the phone page.
- **`sensor/`**: HTTPS page that streams an iPhone's mic to the server, for recording keyword
  training data.
- **`scripts/`**: `routine.py` (RFID loop), `calibrate.py` (warp calibration), `scan_uid.py` (read a
  tag's UID), `start_kiosk.sh`, `install_services.sh`, `seed_demo.py`.
- **`config/`**: `preset.json` maps RFID tag UIDs to page URLs; `presets.json` holds per-wall warp
  corners (written by the calibration page).

## Running everything at boot (on the Pi)

One-time setup, as the normal desktop user (not root):

```
cd ~/OSCAR
scripts/install_services.sh
systemctl --user start oscar.target
```

This installs systemd user units for the tracker, the display app, the Chromium kiosk and the RFID
loop, and enables them so they start at boot with no terminals. Day to day:

```
systemctl --user status oscar.target       # what is running
systemctl --user restart oscar.target      # restart everything
journalctl --user -u oscar-rfid -f         # follow one service's log (oscar-tracker, oscar-display, oscar-kiosk)
```

The RFID unit waits for the tracker, display app and Chromium to answer before it starts. The kiosk
unit assumes the Pi auto-logs into its desktop; it retries until the display exists.

On a laptop (no RFID hardware), start only what you need:
`systemctl --user start oscar-tracker oscar-display`.

## Running pieces by hand

```
pip install -r requirements.txt       # use the repo's venv
python -m tracker.app                 # tracker, port 5001
python -m display.app                 # display + warp, port 5000
scripts/start_kiosk.sh                # Chromium with remote debugging
python scripts/routine.py             # RFID loop (add --no-warp to skip the warp wrapper)
python -m unittest discover -s tests  # tests, no hardware needed
```

Demo data for the tracker: `OSCAR_TRACKER_DB=data/demo.db python scripts/seed_demo.py`.

## Calibrating a wall's warp

1. Run the display app, then `python scripts/calibrate.py wall` (use any wall name).
2. Open the URL it prints (a laptop, or a phone on the same network).
3. Drag the four corner handles until the grid on the real wall is a clean rectangle. Arrow keys
   nudge the selected corner (keys 1-4 pick it).
4. Enter the wall name (and the turntable angle if you know it) and press Save. The corners are
   written to `config/presets.json`.

To preview any page through the warp by hand:
`http://localhost:5000/stage?u=http://localhost:5001/?wall=1`.

## Ports

| Port | Service |
|---|---|
| 5000 | display app (`/stage`, `/warp`, `/calibrate`) |
| 5001 | habit tracker |
| 5002 | phone sensor server |
| 9222 | Chromium remote debugging |

## Docs

`docs/PLAN.md` (original design), `docs/PI_HUB_PLAN.md` (current architecture, wins on conflicts),
`docs/PROJECTION_PLAN.md`, `docs/TURNTABLE_PLAN.md`, `docs/HABIT_TRACKER_PLAN.md`,
`docs/PHONE_SENSOR_PLAN.md`, `docs/USER_STORIES.md`, and `docs/INTERVIEW_PREP.md` (for discussing the
project honestly: what is built versus planned).
