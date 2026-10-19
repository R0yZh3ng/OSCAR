"""Press the PC's power button: a GPIO pin drives an NPN transistor wired across the motherboard
power-button header pins. On a sleeping PC this wakes it; on a running PC it would toggle power,
so callers must check the PC is down first (see pc/control.py)."""

import time


def press(pin, seconds=0.3):
    from gpiozero import DigitalOutputDevice  # imported here so the module loads off the Pi

    out = DigitalOutputDevice(pin)
    try:
        out.on()
        time.sleep(seconds)
        out.off()
    finally:
        out.close()
