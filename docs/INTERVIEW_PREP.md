# OSCAR: Interview Prep

Living document. **Update it at the end of every working session** (see "Session log" at the
bottom, and fix anything above that changed). Facts here come from the repo; anything not yet
verified on hardware is marked so you never claim more than is true.

Last updated: 2026-10-21.

---

## 1. The pitch

**30 seconds.** "OSCAR is a wall-projected personal assistant I built around a Raspberry Pi. You
tap an RFID tag and a servo turntable aims a projector at the right wall while it shows a habit
tracker I wrote from scratch. Voice, snaps, gestures and RFID all feed one command router, so
every input behaves the same. The heavy compute runs on my desktop and the Pi stays on 24/7 as the
hardware hub."

**2 minutes.** Add: the problem (Notion was slow and not glanceable on a wall; I wanted ambient,
hands-free control), the architecture (Pi = always-on hub, PC = compute, phone = mic/camera sensor),
the one design rule (every change is a named action through one dispatch function), and one
story about a real tradeoff (see section 6).

**Why it's interesting.** It is a small distributed system with real constraints: weak hardware,
flaky Wi-Fi, an unreliable projector, a bright room. Most of the engineering is deciding what runs
where and what fails gracefully.

**Be straight about how it was built.** If asked, say what you designed and directed versus what
you had AI assistance on, and make sure you can explain every file you mention. Interviewers ask
"why did you do it this way" far more than "what does this function do."

---

## 2. Honest status (what you can claim)

| Piece | State |
|---|---|
| Habit tracker (`tracker/`): actions, SQLite, stats, XP/levels, UI, wall theme | **Built, unit-tested (16 tests), used on the real projector** |
| Chromium tab switching on RFID tap (`display/tabs.py`, `scripts/routine.py`) | **Built, unit-tested, tab switching confirmed working by hand** |
| RFID reader + LCD + buzzer drivers (`hardware/*`) | Built earlier, used on the Pi |
| Phone sensor page (`sensor/`): HTTPS mic stream, WAV capture, keyword recorder | **Built, server tested (3 tests + smoke test); not tried on a real iPhone** |
| PC wake + SSH unlock (`pc/control.py`, `hardware/pc_power.py`) | **Built, logic unit-tested (4 tests); not wired or run on hardware** |
| Projector power | **Researched; HDMI approach tested and failed; IR blaster planned, parts not bought** |
| Keyword/wake-word model | **Designed only** (`docs/PLAN.md`); no model, no training data yet |
| Servo turntable, LEDs, command router/daemon | **Designed only**; `servo.py`, `leds.py`, `daemon.py` are empty stubs. Printed-base plan written (`TURNTABLE_PLAN.md`), nothing printed yet |
| Per-wall image warp | **Planned only** (`PROJECTION_PLAN.md`): matrix3d corner pinning; no code yet |
| Gestures, Bambu A1 printer link | Planned (`PHONE_SENSOR_PLAN.md`, `BAMBU_PLAN.md`); Bambu printer now in hand, no MQTT link built |

Total tests: 28, all passing (`python -m unittest discover -s tests`).

---

## 3. Architecture

### Evolution (a good story)
1. **v1 plan (PLAN.md):** the Pi does everything: keyword model, router, servo, display.
2. **Phone as sensor:** no ESP32 hardware on hand, so an iPhone web page becomes the mic/camera
   (`PHONE_SENSOR_PLAN.md`). It doubles as the training-data recorder.
3. **PC-compute / Pi-hub (current, `PI_HUB_PLAN.md`):** the desktop does heavy work, the Pi stays on
   as the hub, because the PC is much faster and the Pi is better as an always-on, low-power node.

### Current layout
```
iPhone page --mic/cam data--> PC (keyword model, vision, open-ended speech)   [planned]
                                | events
                                v
Pi (always on) <-- RFID taps, sensors
  |- command router + state machine (IDLE/AWAKE, mode, aim)                    [designed]
  |- Chromium kiosk, pages pre-loaded; a tap only switches tabs               [built]
  |- servo, LCD, LEDs, buzzer                                                  [partly]
  |- projector power (IR)                                                      [planned]
  |- PC power: GPIO presses the motherboard button, SSH unlocks                [built, untested on HW]
  '- habit tracker (Flask + SQLite, port 5001)                                 [built]
```

### Two ideas that run through everything
- **Input-agnostic router.** Voice, snap, RFID and gesture are just callers. Adding an input
  means adding a caller, not changing behavior.
- **Hardware behind `hardware/*`.** Hardware libraries (`pigpio`, `mfrc522`, `gpiozero`) can't import
  on a laptop, so they are imported lazily or isolated. Everything with logic (router, tracker,
  tab switcher, PC wake) takes injected dependencies and is tested on any machine.

---

## 4. Components in depth

### 4.1 Habit tracker (`tracker/`)
- **Stack:** Flask + flask-socketio + SQLite, no front-end build step (plain JS/CSS, SVG for rings
  and charts). Chosen to match the rest of the stack and to run comfortably on a Pi.
- **The seam: `actions.dispatch(conn, name, args, source)`.** Every mutation is a named action
  (`habit.complete`, `habit.undo`, `mood.set` ...) registered with a decorator. The web UI,
  voice, RFID and gestures all call it. Each call runs in one transaction, writes an audit row to
  the `events` table with its `source` (ui/voice/rfid/gesture/api), then returns the result plus
  `xp_delta`, `level_up` and `unlocked` so any client can react (toasts, level-up overlay, later LEDs).
- **Data model** (`tracker/db.py`): `habits`, `entries` (primary key `(habit_id, date)`: one row
  per habit per day), `skips`, `bonus_xp`, `achievements`, `moods`, `events`. Everything else
  (streaks, charts, strength) is a derived query. Note: the plan called for an append-only event log
  as the source of truth; the build uses one entry per habit-day plus an audit log, which is
  simpler for undo and backfill. Good tradeoff to be able to discuss.
- **Day rollover at 4 am** (`DAY_ROLLOVER_HOUR`): late-night habits count toward the day you think
  of them as.
- **Progression** (`progression.py`, pure functions): XP 10/20/35 by difficulty; streak multiplier
  up to +50% at 30 days; +25% perfect-day bonus; level N needs `100*(N-1)^1.6` XP (level 2 at 100,
  level 10 ~3,400); titles Newcomer to Legend; 11 achievements. Undo removes XP and the perfect-day
  bonus so it can't be farmed. Partial credit for count/duration habits is capped at the target.
- **Habit strength** (`stats.strength_series`): an exponential moving average over scheduled days,
  `score = score*d + frac*(1-d)` with `d = 0.5**(1/9)`, like the Loop Habit Tracker. One missed day
  after a long run barely moves it, unlike a raw streak, which resets.
- **Streaks** are forgiving: skips and unscheduled days don't break them.
- **Wall mode** (`?wall=1`, section 4.4).
- **Tests** (`tests/test_tracker.py`, 16): actions, XP, undo, streaks, strength.

### 4.2 Display: tab switching
- **Problem:** tapping an RFID tag used to kill Chromium and relaunch a Notion URL. On a 2 GB Pi
  that took seconds, while the same page on the PC was instant. HDMI wasn't the bottleneck; loading
  a heavy web app was.
- **Fix:** keep Chromium running with `--remote-debugging-port=9222` and have a tap *activate an
  already-loaded tab* via Chromium's DevTools HTTP endpoint (`/json/list`, `/json/activate/<id>`).
  Pages are preloaded at startup, so even the first tap is a switch. (`display/tabs.py`.)
- **Subtleties solved:** the tracker is a single-page app with hash routes (`/#/year`), so tabs that
  differ only by `#fragment` must be told apart; `urllib` silently drops `#...` from a request URL,
  so it's escaped as `%23` when opening a tab. Matching tries exact URL first, then same page.
- **Dependency injection:** `TabSwitcher(http=...)` takes the HTTP function, so tests use a fake
  Chromium (5 tests).
- **Limits:** memory (2-3 tabs max on 2 GB), stale background tabs (refresh timer is a later step).

### 4.3 RFID, LCD, buzzer (`hardware/`)
- RC522 over SPI via `mfrc522`; `wait_for_scan` polls with a cooldown to debounce re-reads.
- Tags map UID to a URL in `config/preset.json`. The earlier PLAN.md schema maps UID to a *mode*
  instead (daily/work); the current build maps to pages, and mode logic belongs to the router
  (not built yet). Know this difference if asked.

### 4.4 Wall display theme (the "bright room" problem)
- **Problem:** a low-end projector in a bright room. Dark greys, thin lines and card backgrounds
  vanish, because projected black can't be darker than the ambient light.
- **Approach:** a `?wall=1` mode: pure black background, bold white text, thick borders, brightened
  rings, no animations; `zoom` scales the whole page 1.8x (it also scales the px-sized SVG charts,
  which a font-size change would not). Optional `&theme=light` (black on white), `&zoom=N`.
- **Constraint-driven design:** the wall has no mouse or scroll, so the dashboard shows only what
  fits one screen (habits, level, streaks) and the charts live on other tag pages. The weekday
  strip is hidden because the wall can't switch days.
- **Verified** by rendering headless Chromium screenshots before and after, then on the real projector.

### 4.5 Phone sensor page (`sensor/`)
- **Why a web page:** the Pi can't pull an iPhone's mic or camera over USB, and a native app is a
  lot more work. `getUserMedia` needs **HTTPS** on iOS, so the plan uses Tailscale certs.
- **Audio pipeline:** an `AudioWorklet` downsamples 44.1/48 kHz to 16 kHz mono int16 (box-average
  before decimation as cheap anti-aliasing) and posts ~100 ms chunks. Echo cancellation, noise
  suppression and auto-gain are turned **off**, because iOS processing changes the audio features
  and would hurt keyword detection.
- **Transport:** socket.io binary events on a `/sensor` namespace. Server can save a stream to a
  WAV (quality check) or save labeled 1 s clips into `voice/model/data/raw/<label>/`.
- **Recorder doubles as the training-data collector,** so training audio matches deployment
  acoustics (phone mic). Labels are validated against `config/sensor.json` to prevent path
  traversal (a test covers `../evil`).
- **Privacy design:** the Pi/PC can send `sensor_control` to gate the mic; default off at boot.
- **iOS gotchas:** page must stay foreground (Wake Lock API), tab suspension, one "Start" tap after
  a reload. Not yet tested on a real phone.

### 4.6 Waking the PC (`pc/control.py`)
- **Constraints:** the PC only ever sleeps (never shuts down) and is on Wi-Fi.
- **Why not Wake-on-LAN:** the Wi-Fi NIC is off while the PC sleeps, so magic packets don't arrive.
- **Design:** a Pi GPIO pin drives an NPN transistor across the motherboard power-button header
  (acts as a button press, which wakes from sleep). Then SSH with a key runs
  `loginctl unlock-sessions`. No password is stored or typed on the Pi, which was a deliberate
  security choice over faking a keyboard.
- **Safety:** pings first and **never presses if the PC is up**, because a press on a running PC
  toggles it. Logic is injected (`press`, `ping`, `ssh`, `sleep`, `now`) and tested with a fake clock.
- **Unverified:** polkit may refuse `unlock-sessions` from a remote SSH session; some lock screens
  ignore it.

### 4.7 Projector power
- **Tried:** cutting the HDMI signal. Result: this projector stays on "No signal"; it never sleeps.
  `vcgencmd display_power` is a no-op on the Pi's KMS graphics driver, and `wlr-randr --off` then
  `--on` left the display broken until a reboot.
- **Plan:** IR blaster. A VS1838B receiver learns the remote's power code once; a 940 nm IR LED
  driven by a transistor on a GPIO pin replays it (`gpio-ir` overlays + `ir-ctl`). Not built.

### 4.8 Not built yet (designed)
- **Keyword model:** log-mel spectrogram of a ~1 s window, small depthwise-separable CNN, softmax
  over `oscar, wall, closet, schedule, hide, sleep` + background; trained off the Pi in TensorFlow,
  exported int8 TFLite, threshold + debounce at inference. Chosen over a paid wake-word engine to
  avoid a license and to own the data.
- **Servo turntable:** bearing carries the load, servo only rotates (1:1 angle); separate 5 V
  supply; `pigpio` for jitter-free PWM.
- **Router/state machine:** IDLE -> AWAKE -> commands -> timeout/"sleep" -> IDLE; aim and mode are
  independent state (voice "wall" changes aim, not the content filter).

---

## 5. Design decisions (with the tradeoff)

| Decision | Alternatives | Why this | Cost |
|---|---|---|---|
| One `dispatch` for all changes | Separate handlers per input | Voice/RFID/gesture get every feature free; audit log; one place to test | An indirection layer |
| SQLite, one row per habit-day + audit log | Pure event sourcing | Simple undo/backfill; stats are plain queries | Less history than full event sourcing |
| Flask + vanilla JS, no build step | React/Vue + bundler | Runs on a Pi, nothing to compile, one stack across services | Hand-written rendering |
| Keep tabs open and switch | Relaunch per tap; faster hardware | Instant taps on the weak Pi; found by measuring the real bottleneck | Memory limit, stale pages |
| PC compute + Pi hub | Pi-only; PC-only; ESP32 | PC is faster for models; Pi is always on, low power, drives the wall | PC is a dependency for voice/vision; more moving parts |
| Phone page as mic/camera | ESP32 mic, USB mic | No hardware on hand; one page doubles as data recorder | iOS foreground/HTTPS constraints |
| Power button pulse + SSH unlock | WoL; typing the password via a fake keyboard | WoL fails on Wi-Fi sleep; no password stored on the Pi | Needs wiring; polkit risk |
| Self-trained keyword model | Picovoice or cloud STT | No licence, no cloud audio, owned data | Time to collect data and iterate |
| Inject dependencies (http, ping, clock) | Mock with patch | Pure-Python tests on any laptop, no hardware | Slightly more verbose signatures |
| Wall mode via CSS `zoom` and theme class | Separate wall page | One codebase, phone view unchanged, tunable by URL | `zoom` is a Chromium-ism (fine for a kiosk) |

---

## 6. Problems hit and how they were solved (best interview stories)

1. **"Slow" display (measure before you optimize).** The Notion tabs lagged on RFID taps. The
   obvious fix was faster hardware or HDMI tuning; the actual cause was page load, so the fix was
   preloading and switching tabs. Lesson: find the real bottleneck.
2. **Projector unreadable in a bright room.** Treated it as a constraint, not a style issue:
   thick, bright, scaled-up wall mode, fit to one screen because nothing can scroll. Verified with
   before/after renders, then on the real device.
3. **`#` lost in a URL.** Two tracker pages differed only by hash route. Tab matching had to learn
   fragments, and `urllib` was silently dropping `#...` when opening a tab. Found by reasoning
   about the failure, fixed, covered by a test.
4. **Wake-on-LAN doesn't work on Wi-Fi.** Changed the design to a physical power-button pulse and
   an SSH unlock rather than storing a password.
5. **Projector ignores "no signal".** Tested the cheap option first (HDMI), got a clear negative
   result, then moved to IR. Also learned `vcgencmd display_power` is a no-op on KMS, and that
   `wlr-randr --off` can wedge a kiosk: now documented in the changelog.
6. **Locked keyring prompt on boot.** Chromium wanted the GNOME keyring on an auto-login Pi.
   `--password-store=basic` removes it, which is fine for a kiosk showing only local pages.
7. **The 4 am day boundary.** Late-night habits shouldn't count for "tomorrow".

---

## 7. Talking points by theme

- **System design:** decide what runs where; design for the component that can disappear (PC off,
  Wi-Fi down). RFID, display and tracker stay up without the PC.
- **Separation of concerns:** pure logic (`progression.py`, `stats.py`, `actions.py`) has no Flask
  or hardware imports; hardware sits behind `hardware/*`.
- **Testability:** dependency injection and fake clocks; 28 tests run on any laptop. Honest limit:
  hardware paths (GPIO, DevTools against real Chromium, iPhone) are verified by hand.
- **Security and privacy:** no stored passwords, a mic that defaults to off and can be gated, label
  validation against path traversal, LAN-only by default, no public tunnels for an always-on mic.
- **Product thinking:** wall mode is designed around how it is used (glanceable, no input).
  Forgiving streaks and capped XP are deliberate behavior design.
- **Iterating with evidence:** tried HDMI power control, measured it, dropped it; compared render
  screenshots before shipping the theme.
- **Scoping and honesty:** a clear line between built, tested, and planned (section 2).

---

## 8. Likely questions and answer sketches

- **Why a Pi *and* a PC?** Compute versus availability. The PC is fast but sleeps; the Pi is slow
  but always on and owns the physical hardware. Each does what it's best at.
- **Why not an ESP32?** For the pure hardware (servo, RFID, LCD) it would work. The Pi earns its
  place by driving the projector, running Chromium and hosting the tracker. If the PC drove the
  projector, an ESP32 would be a fair replacement; that tradeoff is worth naming.
- **How does a voice command become an action?** Audio -> keyword model -> router -> either a
  hardware action (servo, display) or `actions.dispatch` for the tracker. (Router and model not
  built yet; say so.)
- **How would you scale / add a user?** `user_id` on each table; tokens/PIN before leaving the LAN.
  Not needed now.
- **What would break first?** Chromium memory on a 2 GB Pi with many tabs; the phone page being
  suspended by iOS; Wi-Fi drops between phone and PC.
- **How did you test hardware code?** Injected dependencies for unit tests, plus manual
  checklists (`PLAN.md` Verification) for the parts that need real hardware.
- **How does undo work without exploiting XP?** XP is stored on the entry, so deleting the entry
  removes its XP, and the perfect-day bonus is recomputed.
- **What would you do differently?** Start with measurements earlier (display, projector), and
  write the router before peripherals so each new input was only a caller.
- **What's the hardest part left?** The keyword model: data collection and iterating on false
  triggers in a real room.

---

## 9. Facts and numbers

- Hardware: Raspberry Pi 4B (2 GB), RC522 RFID, micro servo (from the kit), LCD1602, buzzers, ultrasonic ranger,
  starter kit parts; WSX "SGD SX8" projector (1080p preferred); iPhone 12 as a sensor; Linux desktop.
- Ports: tracker 5001, sensor server 5002, Chromium DevTools 9222.
- Audio: 16 kHz mono int16, ~100 ms chunks (1600 samples), 1 s keyword clips, 6 keywords + background.
- Habit strength decay `0.5**(1/9)`; XP 10/20/35; streak bonus cap +50% at 30 days; perfect day +25%.
- Wall theme zoom 1.8x; tab switching via DevTools `/json/list` and `/json/activate/<id>`.
- Tests: 28 (tracker 16, tabs 5, PC control 4, sensor 3).
- Key docs: `PLAN.md` (v1 design), `PI_HUB_PLAN.md` (current architecture), `PHONE_SENSOR_PLAN.md`,
  `HABIT_TRACKER_PLAN.md`, `BAMBU_PLAN.md`, `USER_STORIES.md` (US-1..22), `CHANGELOG.md`.

---

## 10. Known limits and next steps (say these before they are asked)

- Voice, router, servo and LEDs are designed but not built; the demo is RFID -> tracker on the wall.
- The PC wake, phone page and IR projector control are unverified on real hardware.
- Chromium tab memory and stale tabs; no offline/PWA queue for the tracker yet.
- Next: IR projector control, the router/state machine, keyword data collection via the phone page,
  then the PC-side model.

---

## Session log

### 2026-10-21
- Planning only, no code. Printer arrived; wrote the turntable-base plan (`TURNTABLE_PLAN.md`) and
  the per-wall projection warp plan (`PROJECTION_PLAN.md`).
- Design decision to remember: the old plan warped one page with CSS classes, but tab switching
  means many pages, so the warp moves to a wrapper page applying a 4-corner homography (`matrix3d`)
  that every tab inherits. Calibration is dragging the four corners on the real wall.

### 2026-10-19
- Chose PC-compute / Pi-hub architecture; documented it.
- Built the phone sensor page, Chromium tab switching, PC wake + SSH unlock, tracker wall theme.
- Pointed RFID tags at tracker pages; removed the keyring prompt.
- Tested HDMI power control on the projector: failed; IR blaster is the plan.
- Added `CHANGELOG.md` and this document.
