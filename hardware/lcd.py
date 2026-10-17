from RPLCD.i2c import CharLCD


class LCD:
    def __init__(self, address=0x27, cols=16, rows=2):
        self._cols = cols
        self._lcd = CharLCD("PCF8574", address, cols=cols, rows=rows)

    def show(self, line1="", line2=""):
        self._lcd.clear()
        self._lcd.cursor_pos = (0, 0)
        self._lcd.write_string(line1[: self._cols])
        self._lcd.cursor_pos = (1, 0)
        self._lcd.write_string(line2[: self._cols])

    def close(self):
        self._lcd.close(clear=True)
