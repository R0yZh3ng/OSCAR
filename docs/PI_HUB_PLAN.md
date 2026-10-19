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

## Powering the PC on (Wi-Fi)

Wake-on-LAN does not work over Wi-Fi: the NIC is off while the PC sleeps or is shut down.
Plan: a Pi GPIO pin drives an NPN transistor (or the kit's relay) wired across the motherboard
power-button header pins, pulsing it ~0.3 s. The Pi pings the PC first and does nothing if it is
already up, since the pulse toggles power. Ethernet + WoL is the alternative. After the PC boots,
a small agent on it (`pc/agent.py`, later step) opens the work apps; the Pi calls it once the PC
answers.

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
pulse + `pc/agent.py`. 4. Projector power (after the IR parts arrive or the HDMI test).
5. Router/daemon per PLAN.md, with the PC delivering keyword/gesture events. 6. Phone sensor
page recorder/streaming (built; see PHONE_SENSOR_PLAN.md) now runs on the PC.
