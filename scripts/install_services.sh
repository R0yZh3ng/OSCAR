#!/bin/sh
# Install the OSCAR systemd user units so everything starts at boot, with no terminals.
# Run once on the Pi (as the desktop user, not root): scripts/install_services.sh
# Then: systemctl --user status oscar.target     (restart all: systemctl --user restart oscar.target)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HOME/.config/systemd/user"
mkdir -p "$DEST"
for unit in "$ROOT"/systemd/*; do
  sed "s|@ROOT@|$ROOT|g" "$unit" > "$DEST/$(basename "$unit")"
done
systemctl --user daemon-reload
systemctl --user enable oscar.target oscar-tracker oscar-display oscar-kiosk oscar-rfid
# keep user services running from boot, even before anyone logs in
loginctl enable-linger "$USER"
echo "Installed from $ROOT. Start now with: systemctl --user start oscar.target"
echo "Logs: journalctl --user -u oscar-tracker -u oscar-display -u oscar-kiosk -u oscar-rfid -f"
