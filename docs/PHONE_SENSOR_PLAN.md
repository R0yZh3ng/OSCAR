# OSCAR Phone Sensor — iPhone 12 as Mic + Camera

Status: draft (2026-10-18). Replaces the ESP32 cam/mic idea for now (no hardware on hand). Refines
US-20. Build order: this comes **before** the keyword-model work, because the sensor page doubles
as the training-data recorder.

## Goal

The iPhone sits on a stand next to the Pi, plugged in, running one web page. The page is the
sensor: it streams mic audio to the Pi and runs hand-gesture detection locally, sending only small
events. The Pi stays the brain (keyword model, router, servo, LEDs, display). RFID decides when
the mic/camera are live.

## Why a web page

The Pi cannot pull the iPhone's mic or camera over USB, and iOS has no remote control, so nothing
on the Pi can launch or drive Safari. A page using `getUserMedia` is the only no-native-app path,
and Safari only allows it on **HTTPS** (the localhost exemption does not apply from the phone).

## Pipeline

```
iPhone Safari  (sensor page, plugged into Pi USB, Personal Hotspot / or same Wi-Fi)
  ├─ mic ─ AudioWorklet ─ 16 kHz mono int16 chunks ──WebSocket /sensor/audio──▶ Pi
  │                                                       voice/audio_source.py (WebSocketSource)
  │                                                       → voice/kws.py + snap_detector.py (unchanged)
  └─ cam ─ MediaPipe Hands (WASM, in page) ─ gesture events ──socketio──▶ Pi router
                                                                         → servo / LEDs / display / tracker actions
Pi ──socketio "sensor_control" {mic: on|off, cam: on|off}──▶ page   (RFID privacy toggle)
```

- **Audio streams raw; the model stays on the Pi.** ~32 KB/s, trivial on a LAN. One model, one
  threshold/debounce path, and the phone is just a swappable `AudioSource`.
- **Vision runs on the phone.** The Pi 4B (2 GB) cannot decode video next to Chromium + KWS. Only
  gesture labels or landmarks cross the network.
- **Mic constraints:** request `echoCancellation: false`, `noiseSuppression: false`,
  `autoGainControl: false`. iOS processing otherwise changes the audio features and hurts
  keyword detection. Resample to 16 kHz in the worklet (iOS captures at 44.1/48 kHz).

## Pi side

| Piece | Notes |
|---|---|
| `display/app.py` (or a small `sensor/app.py`) | Serves `sensor.html`, owns the `/sensor/audio` WebSocket and the `sensor_control` / `gesture` socketio events. Runs with TLS. |
| `voice/audio_source.py` | `AudioSource` interface: `read(n_samples)`. Implementations: `MicSource` (sounddevice, ReSpeaker) and `WebSocketSource` (ring buffer fed by the socket). `kws.py` takes either. |
| Router handlers | `sensor.mic on/off/toggle`, `sensor.cam on/off/toggle`, and `gesture.<name>` mapped to actions in config (same pattern as `config/tracker_commands.json`). |
| Config | `config/sensor.json`: gesture-name -> action map, default sensor state on boot. |

### RFID as the privacy switch
- A dedicated tag (or the existing mode tags) toggles `mic`/`cam`. The router emits
  `sensor_control` to the page; the page stops/starts its streams. While off, no audio leaves the
  phone and the LEDs/page show a clear "mic off" state.
- Default on boot: mic **off** until a tag is tapped (tunable in `sensor.json`).
- Mic permission persists while the page stays loaded, so toggling needs **no** extra tap on the
  phone. Only a fresh page load needs one "Start" tap (AudioContext requires a gesture).

## HTTPS options

1. **Tailscale HTTPS certs** (recommended): real trusted cert, nothing to install on the phone, and
   it works even when dorm Wi-Fi isolates clients. Requires Tailscale on Pi and phone.
2. **mkcert / self-signed:** works on the LAN, but the root cert must be installed and trusted in
   iOS Settings.
3. Avoid public tunnels (Cloudflare, ngrok) for an always-on mic.

## USB cable: power and network only

- Gives power (phone stays awake and charged) and, with Personal Hotspot on, a Pi<->phone link via
  the `ipheth` driver. That path sidesteps dorm client isolation. **VERIFY** it works on the Pi OS
  version in use and that hotspot stays up with the screen on.
- Does **not** expose the iPhone mic/camera to the Pi. Media still goes through the page.
- Optional convenience: iOS Shortcuts personal automation, trigger "Charger connected" ->
  "Open URL" (the sensor page). **VERIFY** whether it runs without a prompt and without unlocking.

## iOS gotchas

- Page must stay foreground and the screen on: Screen Wake Lock API (iOS 16.4+) plus **Guided
  Access** to stop accidental exits. Keep the phone plugged in.
- Safari suspends the mic if the tab is hidden or the screen locks. The page needs a visible
  connected/streaming indicator and an auto-reconnect loop for the WebSocket.
- After a tab kill or reboot someone must tap "Start" once on the phone.
- Standalone (Add to Home Screen) mode may behave differently for permissions/wake lock. Test both.
- Hotspot or Wi-Fi hiccup -> page buffers nothing; it just drops and reconnects.

## Build order (tomorrow first)

1. **Sensor page skeleton:** HTTPS reachable from the phone, page loads, "Start" button, mic
   permission, shows input level meter. Wake lock on. *(Proves HTTPS + iOS permission path.)*
2. **Audio -> Pi:** AudioWorklet downsample to 16 kHz int16, WebSocket to the Pi, Pi writes a
   WAV to disk. Check quality by listening.
3. **Recorder mode:** the page prompts a keyword ("say: oscar", countdown, record 1 s), uploads
   labeled WAVs to `voice/model/data/raw/<keyword>/`. **This is the training-data collector** for
   the keyword model, so the data matches the phone-mic acoustics used in deployment. Include a
   "background" prompt (silence / room noise) and a few-seconds ambient capture.
4. **`AudioSource` abstraction** + `WebSocketSource` feeding `kws.py` (needs the trained model,
   so after the ML step).
5. **`sensor_control` + RFID toggle** and the on/off UI state.
6. **Camera + MediaPipe Hands**, gesture events, gesture -> action config. Last, since gestures
   are unspecified (US-18/19).

## Open questions

- Which keyword set is final (6 words, or add "printer")? Decide before recording data in step 3.
- Do you still want the ReSpeaker as a second source, or retire it? Plan keeps it as an option via
  the `AudioSource` interface.
- Gesture vocabulary (swipe, thumbs-up, open palm...) and which actions they map to.
- Latency budget: phone -> Pi -> keyword -> action should stay well under ~1 s total.
