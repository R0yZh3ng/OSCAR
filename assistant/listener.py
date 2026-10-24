"""Always-listening front end: audio -> utterances -> Whisper -> wake word -> assistant.

No keyword model is trained. An energy VAD cuts the stream into utterances, Whisper (on the PC's
GPU) transcribes each one, `wake.split_wake` checks it was addressed to OSCAR, and the command goes
to `Assistant.ask`. If you say only "Oscar", the next utterance within `arm_seconds` is the command.
"""

import array
import math
import time

from .wake import split_wake

RATE = 16000
FRAME = 320  # 20 ms


def rms(frame):
    return math.sqrt(sum(s * s for s in frame) / len(frame)) / 32768 if len(frame) else 0.0


class Segmenter:
    """Energy VAD with an adaptive noise floor. feed() returns finished utterances (int16 bytes)."""

    def __init__(self, min_speech=0.25, max_speech=12.0, hangover=0.7, preroll=0.3, margin=3.0, floor=0.006):
        self.min_f, self.max_f = int(min_speech * RATE / FRAME), int(max_speech * RATE / FRAME)
        self.hang_f, self.pre_f = int(hangover * RATE / FRAME), int(preroll * RATE / FRAME)
        self.margin, self.min_floor = margin, floor
        self.noise = floor
        self._buf = array.array("h")
        self._pre, self._utt = [], []
        self._speech_f = self._quiet_f = 0
        self._active = False

    def feed(self, pcm):
        out = []
        self._buf.frombytes(pcm)
        while len(self._buf) >= FRAME:
            frame, self._buf = self._buf[:FRAME], self._buf[FRAME:]
            level = rms(frame)
            loud = level > max(self.noise * self.margin, self.min_floor * 2)
            if not self._active:
                if not loud:  # the noise floor only follows silence
                    self.noise = 0.98 * self.noise + 0.02 * level
                self._pre.append(frame)
                self._pre = self._pre[-self.pre_f:]
                if loud:
                    self._active, self._utt = True, list(self._pre)
                    self._speech_f, self._quiet_f = 1, 0
                continue
            self._utt.append(frame)
            self._speech_f += loud
            self._quiet_f = 0 if loud else self._quiet_f + 1
            if self._quiet_f >= self.hang_f or len(self._utt) >= self.max_f:
                if self._speech_f >= self.min_f:
                    out.append(b"".join(f.tobytes() for f in self._utt))
                self._active, self._utt, self._pre = False, [], []
        return out


class Listener:
    def __init__(self, transcribe, ask, arm_seconds=8.0, clock=time.monotonic, on_heard=None):
        """transcribe(pcm_bytes) -> str; ask(text) -> reply str. on_heard(transcript) is optional logging."""
        self.seg, self.transcribe, self.ask = Segmenter(), transcribe, ask
        self.arm_seconds, self._clock, self.on_heard = arm_seconds, clock, on_heard
        self._armed_until = 0.0

    def feed(self, pcm):
        """Returns a list of (heard, reply) for every command completed by this audio."""
        results = []
        for utt in self.seg.feed(pcm):
            heard = self.transcribe(utt).strip()
            if self.on_heard:
                self.on_heard(heard)
            cmd = split_wake(heard)
            if cmd is None and heard and self._clock() < self._armed_until:
                cmd = heard  # follow-up after a bare "Oscar"
            if cmd is None:
                continue
            if not cmd:
                self._armed_until = self._clock() + self.arm_seconds
                results.append((heard, "Yes?"))
                continue
            self._armed_until = 0.0
            results.append((heard, self.ask(cmd)))
        return results


def whisper_transcriber(model="small.en", device="auto"):
    """faster-whisper, loaded on first use. Prefers the GPU, falls back to CPU int8."""
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel(model, device=device, compute_type="float16" if device != "cpu" else "int8")
    except Exception:
        m = WhisperModel(model, device="cpu", compute_type="int8")

    def transcribe(pcm):
        audio = array.array("h", pcm)
        import numpy as np
        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768
        segs, _ = m.transcribe(samples, language="en", beam_size=1, vad_filter=False,
                               condition_on_previous_text=False,
                               initial_prompt="Oscar, show the dashboard. Oscar, log my habits.")
        return " ".join(s.text for s in segs)

    return transcribe
