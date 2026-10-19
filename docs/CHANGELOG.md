# Changelog

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
