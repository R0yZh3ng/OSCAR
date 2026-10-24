"""The brain: text in, Claude decides which tools to run, text out.

Input-agnostic by design: the typed REPL, the voice listener and later RFID/gesture triggers all
call `Assistant.ask(text)`. History is append-only (required by thinking blocks) and starts fresh
after `idle_reset` seconds of silence, so a new request never drags old context along.
"""

import time

import anthropic

MODEL = "claude-opus-5-5"
SYSTEM = """You are OSCAR, a wall-projector assistant in the user's room. You carry out their \
requests by calling tools; you do not just talk about doing things.

Replies are spoken aloud, so answer in one or two short plain sentences, with no markdown, lists or \
emoji. After acting, confirm what you did. If a tool fails, say so briefly. If a request needs \
something you have no tool for, say that in one sentence rather than pretending. If a habit name is \
ambiguous, call list_habits first instead of guessing."""

MAX_TURNS = 8


class Assistant:
    def __init__(self, tools, client=None, model=MODEL, effort="low", idle_reset=300, clock=time.monotonic):
        self.tools, self.model, self.effort = tools, model, effort
        self.client = client or anthropic.Anthropic()
        self.idle_reset, self._clock = idle_reset, clock
        self.messages, self._last = [], None

    def ask(self, text):
        now = self._clock()
        if self._last is not None and now - self._last > self.idle_reset:
            self.messages = []
        self._last = now
        self.messages.append({"role": "user", "content": text})
        for _ in range(MAX_TURNS):
            resp = self.client.messages.create(
                model=self.model, max_tokens=2000, system=SYSTEM, tools=self.tools.schemas(),
                output_config={"effort": self.effort}, messages=self.messages)
            self.messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "refusal":
                return "Sorry, I can't help with that."
            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:
                return " ".join(b.text for b in resp.content if b.type == "text").strip()
            results = []
            for c in calls:
                out, is_err = self.tools.call(c.name, c.input)
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": is_err})
            self.messages.append({"role": "user", "content": results})
        return "Sorry, that took too many steps."
