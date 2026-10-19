"""Wake the desktop PC from sleep and unlock its session, from the Pi.

The PC only ever sleeps and is on Wi-Fi, so Wake-on-LAN is out; instead a GPIO pulse presses its
power button (hardware/pc_power.py). Once it answers on the network, the Pi SSHes in with a key
and runs the unlock command, so no password is stored or typed.
"""

import json
import subprocess
import time
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "pc.json"


def load_config(path=CONFIG):
    return json.loads(Path(path).read_text())


def ping(host):
    return subprocess.run(["ping", "-c", "1", "-W", "1", host], capture_output=True).returncode == 0


def ssh(cfg, cmd):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
                        f"{cfg['user']}@{cfg['host']}", cmd], capture_output=True, text=True)
    return r.returncode == 0


def wake_and_unlock(cfg, press, ping=ping, ssh=ssh, sleep=time.sleep, now=time.monotonic):
    """Returns 'unlocked', 'unlock_failed' or 'no_response'. Never presses the button if the PC is up."""
    if not ping(cfg["host"]):
        press(cfg["power_gpio"], cfg["pulse_seconds"])
        deadline = now() + cfg["boot_timeout"]
        while not ping(cfg["host"]):
            if now() > deadline:
                return "no_response"
            sleep(1)
    for _ in range(10):  # sshd can lag behind the network coming back
        if ssh(cfg, cfg["unlock_cmd"]):
            return "unlocked"
        sleep(1)
    return "unlock_failed"


if __name__ == "__main__":
    from hardware.pc_power import press as gpio_press

    print(wake_and_unlock(load_config(), gpio_press))
