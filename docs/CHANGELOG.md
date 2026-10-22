# Changelog

## 2026-10-22

### Added
- **Per-wall projection warp** (`docs/PROJECTION_PLAN.md` steps 1-3, plus wrapping):
  - `display/warp.py`: 4-point homography (pure Python), `matrix3d` CSS output, legacy
    `rotateX/rotateY/perspective` conversion to corners. `tests/test_warp.py` (13).
  - `display/app.py` (Flask, port 5000): `/stage?u=` wrapper page, `GET`/`POST /warp`, SSE
    `/warp/stream` so every open tab re-warps live, `/walls` listing, `POST /walls/<name>` to
    save one wall's corners (and optional `angle_deg`) into `config/presets.json`. Static:
    `warp.js` (mirror of the Python math, checked to match), `stage.html`, `grid.html` test
    pattern, `calibrate.html` (draggable corner handles, arrow-key nudge, save).
  - `scripts/calibrate.py <wall>`: aims at a wall and prints the calibration URL.
  - `TabSwitcher(stage=...)` opens pages inside `/stage` and matches tabs by their inner URL, so
    hash routes still work; `scripts/routine.py` uses it by default (`--no-warp` to skip).
- Tests: 63 total (was 29), all passing.

- **Start everything at boot:** `systemd/` user units (`oscar-tracker`, `oscar-display`,
  `oscar-kiosk`, `oscar-rfid`) grouped under `oscar.target`, and `scripts/install_services.sh` to
  install and enable them. The RFID unit waits for the tracker, display app and Chromium to answer
  before starting. Units pass `systemd-analyze verify`; **not yet installed or run on the Pi**.

- `README.md` (new): project description, status table, what each part does, boot-at-startup
  commands, running by hand, calibration steps, ports, doc index.

### Fixed
- `POST /warp` with invalid JSON (e.g. a stray character after the body) returned a misleading
  "unknown wall None"; it now returns a 400 explaining the expected body.

### Verified / not verified
- Verified by hand in a browser: `/stage` warps a page and a `curl` to `/warp` re-warps it live.
- Not yet tried: the calibration page, the wrapped tag URLs, anything on the Pi or projector.
  `config/presets.json` is still empty, so no wall is calibrated.

## 2026-10-21

### Planned (docs only, no code)
- `docs/TURNTABLE_PLAN.md`: 3D-printed base for the projector rotation platform (Bambu A1 now in
  hand): lazy-susan bearing + printed plates, PETG, printed travel stops, measurements needed,
  print and test steps.
- `docs/PROJECTION_PLAN.md`: per-wall image transformation. 4-corner `matrix3d` homography on a
  `/stage` wrapper page so it applies to every Chromium tab, corners stored per wall in
  `presets.json`, drag-the-corners calibration, live updates when the servo moves.
- Turntable motor changed from servo to the kit's stepper (28BYJ-48 + ULN2003): plan now covers
  homing switch, step-skip and backlash risks, and a NEMA 17 upgrade path. `servo_angle` in the
  preset schema becomes `angle_deg`.
- Cross-references added in `PLAN.md`, `BAMBU_PLAN.md` and `CLAUDE.md`.

## 2026-10-19

### Architecture
- Decided the desktop PC does heavy compute and the Pi is an always-on hub: tab-switching display,
  servo/RFID/LCD, tracker host, PC and projector power. Documented in `PI_HUB_PLAN.md`;
  `CLAUDE.md` points to it and it overrides `PLAN.md` where they conflict. (`aac7e57`)

### Added
- **Phone sensor page** (`sensor/`, `config/sensor.json`, `scripts/make_sensor_cert.sh`): HTTPS
  page that streams the iPhone mic to the server as 16 kHz int16, saves test WAVs, and records
  labeled keyword clips into `voice/model/data/raw/<label>/`. Plan steps 1-3 of
  `PHONE_SENSOR_PLAN.md`. Not yet tried on a real iPhone. (`769659d`)
- **Chromium tab switching** (`display/tabs.py`, `scripts/start_kiosk.sh`): an RFID tap activates
  an already-loaded tab instead of relaunching Chromium. `scripts/routine.py` preloads all tag
  URLs at start. Tab matching tells SPA hash routes apart and escapes `#` when opening. (`bf1ada6`, `c0b8049`)
- **PC wake and unlock** (`hardware/pc_power.py`, `pc/control.py`, `config/pc.json`): a GPIO
  pulse presses the motherboard power button to wake a sleeping PC; then SSH runs
  `loginctl unlock-sessions`. Never presses if the PC already answers ping. Not tested on
  hardware; `host` in `config/pc.json` is a placeholder. (`21cf3f5`)
- **Tracker wall theme** (`?wall=1`, optional `&theme=light`, `&zoom=N`): 1.8x scale, bold
  white-on-black (or black-on-white), thick borders, brightened rings, no animations, no weekday
  strip, dashboard trimmed to one screen. Built for the low-quality projector in a bright room;
  confirmed "a lot better" on the real projector. (`0eba8d0`, `b7aa7d7`)
- Tests: `tests/test_sensor.py`, `test_tabs.py`, `test_pc_control.py` (28 total, all passing).

### Changed
- `config/preset.json`: RFID tags now open tracker pages instead of Notion:
  `3DE50207` -> `http://localhost:5001/?wall=1`, `E3121706` -> `.../?wall=1#/year`.
- `scripts/start_kiosk.sh` passes `--password-store=basic` so Chromium stops asking for the locked
  keyring. (`9baa4aa`)
- `.gitignore` excludes `voice/model/data/`.

### Findings (hardware, tested on the Pi)
- `vcgencmd display_power 0` does nothing on this Pi (KMS graphics driver): it still reads `1`.
- `wlr-randr` works over SSH with `XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0`;
  the projector is `HDMI-A-1` ("WSX SGD SX8").
- **The projector does not sleep when the HDMI signal is cut**; it stays on "No signal". So HDMI
  can't switch it off or on.
- **Do not run `wlr-randr --output HDMI-A-1 --off` on the kiosk Pi.** `--on` afterwards failed
  with "failed to apply configuration" and a reboot was needed to get the picture back.
- The projector has a screensaver option (minimum 5 min); not yet tested whether it powers
  anything down. Its menu may also have an auto-power-off setting.

### Docs
- Added `docs/INTERVIEW_PREP.md`: pitch, honest status table, architecture, design decisions,
  problems solved, talking points, likely questions, session log. Must be updated every session
  (rule added to `CLAUDE.md`).

### Open / next
- Projector power needs an IR blaster (VS1838B receiver to learn the remote, 940nm IR LED; kit
  transistor and resistors drive it; planned GPIO 22 TX, 23 RX with `gpio-ir` overlays and
  `ir-ctl`). Parts not yet bought; software not written.
- Wire the PC power-button transistor, set `host` in `config/pc.json`, verify wake and SSH unlock
  (polkit may refuse remote `unlock-sessions`).
- Choose dark vs `&theme=light` for the tags; both are on dark for now.
- Not started: Pi-side wake word (no mic or speaker in the kit), `pc/agent.py` to open work apps,
  router/daemon per `PLAN.md`, camera and gestures.
- The parts photo `List_RFID_RPi_Kit copy.jpg` stays untracked on purpose.
