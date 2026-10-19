# OSCAR x Bambu Lab A1 — Connection Pipeline

Status: draft (planning day, 2026-10-18). Printer ordered, not yet in hand. Items marked **VERIFY**
depend on the A1's firmware and must be checked once it arrives.

## Goal

Treat the printer as one more OSCAR peripheral: OSCAR can *see* it (state, progress, errors) and,
later, *tell* it things (pause, light, start a stored job). Same rule as everywhere else: every
input goes through the command router / action dispatch, and hardware access hides behind a
`hardware/*` module so the router and display can be tested on a laptop.

## How the A1 can be reached

| Channel | Port | Auth | Use |
|---|---|---|---|
| MQTT over TLS | 8883 | user `bblp`, password = LAN access code | Status reports (push, continuous) + commands (pause/resume/stop, light, speed, `pushall`) |
| FTPS | 990 | `bblp` + access code | Upload `.3mf` to the SD card |
| Camera (A1/P1 family) | 6000 (TLS, JPEG frame stream; not RTSP like the X1) | access code | Optional wall-projected live view |
| Discovery (SSDP) | UDP 1990/2021 | none | Optional; a static IP / DHCP reservation is simpler |

Constraints to design around:
- **LAN Only mode is the path.** While the printer is bound to Bambu Cloud, Bambu restricts local
  MQTT control. LAN mode (or Developer Mode, which runs under LAN mode) allows it, at the cost of
  no Cloud/Bambu Handy features. **VERIFY** which of LAN / Developer Mode the current A1 firmware
  needs for *control* commands; read-only status may work either way.
- **Same subnet** as the Pi, or the connection fails. The dorm network may isolate clients
  (AP/client isolation). **VERIFY on day one**: if it is isolated, plan B is a direct Ethernet-less
  option: put the Pi and printer on a small travel router, or have the Pi host a hotspot.
- Firmware auto-updates have changed third-party auth before. Pin the printer firmware (disable
  auto-update) once things work.
- The access code and serial live in env vars / a git-ignored file, never in `presets.json`.

## Architecture: where it plugs in

```
 A1 printer ──MQTT/TLS 8883──▶ hardware/printer.py  (BambuPrinter: connect, state(), command())
                                   │  normalized PrinterState
                                   ▼
                          printer/monitor.py  (thread in control daemon, owns reconnect + edge detection)
                                   │  events: print_started / progress / paused / finished / failed / filament_out
                                   ▼
                          voice/daemon.py command router  ◀── voice "printer", RFID tag, snap
                                   │
          ┌────────────────────────┼─────────────────────────┐
          ▼                        ▼                         ▼
   hardware/leds.py        aplay clip / chime         display app (socketio "printer" event)
   (amber/green flash)     "Print finished"           → wall widget: progress, ETA, camera
```

Why a monitor with edge detection rather than polling in the router: MQTT reports arrive every
~1s as full-ish JSON blobs. Only *transitions* (idle→running, running→finish, any→error, HMS error
code new) should reach the router, otherwise LEDs and audio fire constantly.

### Module breakdown

1. `hardware/printer.py`: thin wrapper. Candidates: `bambulabs_api` (PyPI, MQTT control + state) or
   plain `paho-mqtt` against `device/<serial>/report` and `device/<serial>/request`. **Recommendation:
   start with raw `paho-mqtt`.** The protocol is small (documented in the community
   OpenBambuAPI repo), it avoids a library that lags firmware changes, and only a dozen fields matter.
   - `connect()` with TLS (the printer cert is self-signed: use `tls_insecure_set(True)` or pin the
     Bambu CA), auto-reconnect with backoff.
   - On connect, publish `{"pushing": {"sequence_id": "0", "command": "pushall"}}` to get a full
     state snapshot (the printer otherwise sends deltas).
   - `PrinterState` dataclass: `gcode_state` (IDLE/RUNNING/PAUSE/FINISH/FAILED), `percent`,
     `remaining_min`, `layer`/`total_layers`, `nozzle_temp`/`bed_temp` (+ targets), `subtask_name`,
     `hms_errors`, `ams_filament` (A1 has no AMS unless AMS lite is added), `online`.
   - `command(name, **args)`: `pause`, `resume`, `stop`, `light_on/off`, `speed`. Fire-and-forget
     with the response read back from the report topic.
   - A `FakePrinter` with the same interface that replays a recorded JSON trace, for laptop dev and
     tests (matches the repo rule of keeping hardware behind `hardware/*`).
2. `printer/monitor.py`: owns the thread, diffs consecutive `PrinterState`s, emits events to a
   callback (the router). Debounce flapping, mark `online=False` after N seconds with no report.
3. Router handlers (daemon): `printer.status`, `printer.pause`, `printer.resume`, `printer.light`.
4. Display: new socketio event `printer_state`; a wall widget (progress ring, ETA, nozzle/bed temps,
   optional camera frame). Reuses the tracker's widget/ring styling where possible.
5. Config: `config/printer.json` for non-secret settings (ip or hostname, serial, poll/notify
   rules, which events should chime). Secret: `OSCAR_BAMBU_ACCESS_CODE` env var.

### Reconciling with the existing design rules

- **Aim vs. mode independence (US-11)** is untouched. The printer is *content*, not aim or mode.
- **LED colors**: amber is reserved for "unrecognized", blue/red for mode. Do **not** use them for
  printer events. Proposed: green pulse = print finished, magenta/violet flash = printer error
  or filament runout; fall back to an `aplay` clip for anything needing attention.
- **Habit tracker tie-in** (optional, cheap): `print.finished` could call
  `POST :5001/api/actions` with `source: "api"` for a "make something" habit; a failed print could
  be logged to the tracker journal. Keep it as a router subscriber, not coupled into the monitor.
- **Where the printer physically sits**: the projector turntable rotates to "wall"/"closet". A third
  preset (`"printer"` wall) is possible if the printer is in view of a projectable surface;
  otherwise the status widget just appears on whichever wall is active.

## Phased rollout

| Phase | Needs printer? | Deliverable | Done when |
|---|---|---|---|
| 0. Network | yes (day 1) | Printer in LAN mode, static IP / DHCP reservation, access code + serial noted, `nc -vz <ip> 8883` from the Pi works | Pi can reach 8883 across the dorm network |
| 1. Read-only status | yes | `scripts/printer_probe.py`: connect, `pushall`, pretty-print live state | Live % / temps match the printer screen |
| 2. Trace capture | yes | Record a real print's MQTT stream to `tests/fixtures/a1_print.jsonl` | Fixture exists |
| 3. Wrapper + monitor | no (uses fixture) | `hardware/printer.py`, `FakePrinter`, `printer/monitor.py`, unit tests for edge detection | `python -m unittest` green on a laptop |
| 4. Router + feedback | partial | Events drive LED/chime/display widget | Print finish triggers the cue end to end |
| 5. Control | yes | Voice/RFID pause, resume, light | Command takes effect on the printer |
| 6. Camera | yes | JPEG stream proxy endpoint on the display app -> wall widget | Live frame on the wall at a few fps (watch Pi CPU/RAM, it has 2 GB) |
| 7. Job start (stretch) | yes | FTPS upload + `project_file` command; an RFID tag per stored model | Tap tag, print starts (**confirm-before-start**: LED prompt plus a "yes" keyword, never start motion unattended on one tap) |

Phases 0-2 are the only ones that block on the hardware arriving; 3-4 can start before it does
(against a synthetic trace) if there is spare time.

## Risks / open questions

- Dorm Wi-Fi client isolation or captive portal (biggest unknown, **VERIFY** first).
- Firmware changes breaking third-party auth. Pin firmware; keep the wrapper small and isolated.
- Pi 4B 2 GB load: keyword model inference + Chromium kiosk + Flask + MQTT + camera stream. The
  camera view is the first thing to cut if CPU is tight.
- Safety: remote *control* of a heated printer from a voice keyword. Keep pause/stop only (no
  start, no temperature or motion commands) until the confirm flow in phase 7 exists. Never leave
  the printer unattended running on a first-time unproven setup.
- Keyword vocabulary: "printer" would be a 7th class in the KWS model. Adding it later means
  retraining. **Decide tomorrow before collecting data** (see below), or accept RFID-tag/tracker-UI
  control for the printer and leave the model at 6 words.

## Suggested user stories to add to `USER_STORIES.md`

- **US-23 · Print status on the wall** (Next): progress/ETA widget on the projected display.
- **US-24 · Print finished / failed alert** (Next): LED + chime when the print ends or errors.
- **US-25 · Pause/resume the print by voice or tag** (Backlog).
- **US-26 · Start a stored print by RFID tag with confirmation** (Backlog).
- **US-27 · Printer camera on the wall** (Backlog).
