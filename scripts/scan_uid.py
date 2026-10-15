import sys

from pathlib import Path

# let this script import from the repo root (hardware/ ...) when run as 
# 'python scripts/scan_uid.py'


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hardware.rfid import RFIDReader

def main():
    reader = RFIDReader()

    print("scan a tag (CTRL-C to exit)... ")
    try:
        while True:
            uid = reader.wait_for_scan()
            print(uid)

    except KeyboardInterrupt:
            print("\nDone.")

    finally:
            reader.close()

if __name__ == "__main__":
    main()
