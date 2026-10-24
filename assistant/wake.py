"""Wake word by transcript, so no keyword model or recordings are needed.

Every spoken utterance is transcribed (assistant/listener.py); this decides whether it was
addressed to OSCAR and what the command part is. Whisper often mishears the name, so a set of
close variants is accepted. Pure text in, text out: tested without audio.
"""

import re
from difflib import SequenceMatcher

NAME = "oscar"
# common Whisper mishearings of "Oscar"
VARIANTS = {"oscar", "oskar", "oscor", "osker", "ozcar", "oscare", "oska", "oscarr", "os car", "ask her", "ask car"}
LEAD_IN = {"hey", "hi", "ok", "okay", "yo", "hello"}


def _norm(word):
    return re.sub(r"[^a-z]", "", word.lower())


def _is_name(word):
    w = _norm(word)
    if not w or w in VARIANTS:
        return bool(w)
    # fuzzy, but "oscars" / "oscarson" are other words, not mishearings
    return not w.startswith(NAME) and SequenceMatcher(None, w, NAME).ratio() >= 0.8


def split_wake(transcript):
    """Returns None if OSCAR wasn't addressed, '' if only the name was said, else the command.

    The name must open the utterance (after an optional 'hey'), or close it ('...oscar'), so a
    sentence that merely mentions Oscar in conversation does not trigger.
    """
    words = transcript.split()
    i = 0
    while i < len(words) and _norm(words[i]) in LEAD_IN:
        i += 1
    if i < len(words) and _is_name(words[i]):
        return " ".join(words[i + 1:]).strip(" ,.!?")
    if len(words) > 1 and _is_name(words[-1]):
        return " ".join(words[:-1]).strip(" ,.!?")
    return None
