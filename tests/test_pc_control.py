import unittest

from pc.control import wake_and_unlock

CFG = {"host": "pc", "user": "u", "power_gpio": 27, "pulse_seconds": 0.3,
       "boot_timeout": 5, "unlock_cmd": "loginctl unlock-sessions"}


class Clock:
    def __init__(self):
        self.t = 0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class WakeTest(unittest.TestCase):
    def run_wake(self, pings, ssh_results=(True,)):
        presses, ssh_calls, clock = [], [], Clock()
        pings, ssh_results = iter(pings), iter(ssh_results)
        out = wake_and_unlock(
            CFG, press=lambda pin, s: presses.append(pin),
            ping=lambda h: next(pings, True), ssh=lambda c, cmd: ssh_calls.append(cmd) or next(ssh_results, True),
            sleep=clock.sleep, now=clock.now)
        return out, presses, ssh_calls

    def test_sleeping_pc_is_pressed_then_unlocked(self):
        out, presses, ssh_calls = self.run_wake([False, False, False, True])
        self.assertEqual((out, presses, ssh_calls), ("unlocked", [27], ["loginctl unlock-sessions"]))

    def test_running_pc_is_never_pressed(self):
        out, presses, _ = self.run_wake([True])
        self.assertEqual((out, presses), ("unlocked", []))

    def test_no_response_after_timeout(self):
        out, presses, ssh_calls = self.run_wake([False] * 50)
        self.assertEqual((out, presses, ssh_calls), ("no_response", [27], []))

    def test_unlock_retries_then_gives_up(self):
        out, _, ssh_calls = self.run_wake([True], ssh_results=[False] * 20)
        self.assertEqual((out, len(ssh_calls)), ("unlock_failed", 10))


if __name__ == "__main__":
    unittest.main()
