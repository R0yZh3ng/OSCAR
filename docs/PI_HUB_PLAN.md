# OSCAR Architecture Update — PC compute, Pi hub

Status: draft (2026-10-19). Supersedes the "Pi runs everything" layout in PLAN.md where they
conflict; PLAN.md's router, state machine, config schema and servo/display design still apply.

## Decision

The desktop PC (Linux, on Wi-Fi) does the heavy compute. The Pi stays on 24/7 as the hub: it owns
the wall's hardware, keeps the display pages loaded, and can power the PC and projector on.

```
iPhone page ──mic/cam data──▶ PC  (keyword model, vision, open-ended speech; sensor/app.py)
                               │ events (wake word, command, gesture)
                               ▼
Pi (always on) ◀── RFID taps, ultrasonic, buttons
  ├─ router + state machine (IDLE/AWAKE, mode, aim)
  ├─ Chromium kiosk, pages pre-loaded; a tap only switches tabs  (display/tabs.py)
  ├─ servo, LCD, LEDs, buzzer
  ├─ projector power (IR blaster or HDMI signal)
  ├─ PC power: GPIO "presses" the motherboard power button
  └─ habit tracker (SQLite, port 5001) so it works with the PC off
```

## Why

- The PC is far faster for models and vision; the Pi 4B (2 GB) is not.
- The Pi is slow at loading heavy web apps (Notion), but showing an *already loaded* page is
  instant. So the Pi keeps the tabs open and switches between them.
- The Pi stays available when the PC is off or asleep: RFID, servo, tracker and display still work.

## Parts reality (as of 2026-10-19)

Only the RFID/RPi starter kit is on hand (see the list image, not committed): RC522 + card + fob,
SG90 servo, LCD1602, buzzers, ultrasonic ranger, photoresistor, DHT11, joystick, keypad, buttons,
relay, NPN/PNP transistors, resistors, LEDs, breadboard, power module. **No mic, speaker or camera
on the Pi**, so the phone page is the only mic for now and the Pi-side wake word is deferred until
a USB mic exists.

## Display: tab switching

Chromium runs permanently with `--remote-debugging-port=9222`. An RFID tap maps a tag to a URL;
`display/tabs.py` activates the tab already showing it (via Chromium's `/json/activate/<id>`), and
opens one only on first use. Keep the tab count low (2-3) on 2 GB RAM. Background tabs go stale, so
they are refreshed on a timer (later step).

## Waking the PC (Wi-Fi, sleep only)

The PC is only ever put to sleep, never shut down, and is on Wi-Fi. Wake-on-LAN does not work over
Wi-Fi, so `hardware/pc_power.py` pulses a GPIO pin (BCM 27 by default) into an NPN transistor wired
across the motherboard power-button header, which wakes it from sleep. `pc/control.py` then:

1. pings the PC; if it already answers, the button is **never** pressed (a pulse on a running PC
   would toggle it);
2. otherwise pulses, and waits up to `boot_timeout` s for it to answer;
3. SSHes in with a key and runs `unlock_cmd` (default `loginctl unlock-sessions`). No password is
   stored on the Pi or typed.

Settings are in `config/pc.json` (set `host`). Run by hand: `python -m pc.control`.

Wiring (kit parts): GPIO 27 -> 1 kOhm -> NPN base, emitter -> Pi GND and motherboard power-switch
pin (-), collector -> motherboard power-switch pin (+). Check the board manual for the PWR_SW pins.
Do not connect anything to mains.

Things to verify on the real machine (not testable here):
- A short press wakes the PC from sleep (BIOS may need power-button wake enabled).
- `ssh user@pc loginctl unlock-sessions` works by hand with a key. Remote SSH sessions are not
  "active local", so polkit may refuse; if so, change `unlock_cmd` or add a polkit rule.
- The lock screen honours logind unlock (GNOME/KDE do; i3lock/swaylock may not).
- After resume, Wi-Fi may take a few seconds; `boot_timeout` covers it.

Opening the work apps after unlock (`pc/agent.py`) is a later step; it needs the PC's desktop
session and the list of apps/URLs.

## Projector power

Cheap Amazon projectors have no network control. Options, in order of preference:
1. **IR blaster:** a VS1838B receiver to learn the remote's power code, an IR LED on a GPIO pin to
   replay it (kit transistors/resistors drive the LED). Needs ~$2 of parts.
2. **HDMI signal:** test whether the projector sleeps without signal and wakes with it
   (`vcgencmd display_power 0/1`). Free if it works.
3. **Smart plug:** only if the projector powers on by itself when mains returns; skips fan
   cooldown. The kit relay is not to be wired to mains.

## Build order

1. This doc. 2. `display/tabs.py` + RFID script using it (tab switching). 3. PC power-button
pulse + SSH unlock (done, unverified on hardware); `pc/agent.py` for work apps later. 4. Projector power (after the IR parts arrive or the HDMI test).
5. Router/daemon per PLAN.md, with the PC delivering keyword/gesture events. 6. Phone sensor
page recorder/streaming (built; see PHONE_SENSOR_PLAN.md) now runs on the PC.

## Running the tab switcher (on the Pi)

```
python -m tracker.app &         # the tracker pages the tags point at (port 5001)
scripts/start_kiosk.sh &        # once; Chromium with remote debugging on :9222
python scripts/routine.py       # preloads every URL in config/preset.json, then tap tags
```
`tests/test_tabs.py` covers `display/tabs.py` with a fake Chromium, so it runs on any machine.

Tag pages (`config/preset.json`): `3DE50207` -> tracker dashboard (`/`), `E3121706` -> year heatmap
(`/#/year`). Any tracker hash route works (`#/habits`, `#/trend`, `#/streaks`, ...). Tabs on the
same SPA are told apart by their hash.
