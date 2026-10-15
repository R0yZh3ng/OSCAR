"""Show a test message on the LCD."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hardware.lcd import LCD


def main():
    lcd = LCD(address=0x27)  # change to match i2cdetect (0x3F is common)
    try:
        lcd.show("Hello, Roy!", "Start Working?")
        time.sleep(5)
    finally:
        lcd.close()


if __name__ == "__main__":
    main()
