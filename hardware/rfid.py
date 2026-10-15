""" RC522 RFID reader: poll for tag scans and return UIDs as hex strings."""

import time

import mfrc522

def uid_to_str(uid):
    return "".join(f"{b:02X}" for b in uid)

class RFIDReader:
    def __init__(self):
        self._reader = mfrc522.MFRC522()

    def read_uid(self):
        status, _ = self._reader.MFRC522_Request(self._reader.PICC_REQIDL)
        if status != self._reader.MI_OK:
            return None
        status, uid = self._reader.MFRC522_Anticoll()
        if status != self._reader.MI_OK:
            return None
        return uid_to_str(uid[:4])

    def wait_for_scan(self, poll_interval=0.1, cooldown = 2.0):
        while True:
            uid = self.read_uid()
            if uid:
                time.sleep(cooldown)
                return uid
            time.sleep(poll_interval)
    
    def close(self):
        import RPi.GPIO as GPIO

        GPIO.cleanup()
