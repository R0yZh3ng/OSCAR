#!/bin/sh
# Start Chromium once, fullscreen, with remote debugging so taps can switch tabs (display/tabs.py).
# Run under systemd with Restart=always so it comes back after a crash.
export DISPLAY="${DISPLAY:-:0}"
exec chromium --start-fullscreen --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.config/oscar-kiosk" --noerrdialogs --disable-infobars \
  --no-first-run "$@"
