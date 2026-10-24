"""Typed OSCAR: `python -m assistant`. Same brain the voice listener uses, no mic needed."""


from tracker.db import connect
from display.tabs import STAGE, TabSwitcher

from .agent import Assistant
from .tools import Tools


def build(db_path=None):
    tools = Tools(connect(db_path), tabs=TabSwitcher(stage=STAGE))
    return Assistant(tools)


def main():
    bot = build()
    print("OSCAR ready. Type a request (Ctrl+D to quit).")
    try:
        while True:
            line = input("> ").strip()
            if line:
                print(bot.ask(line))
    except (EOFError, KeyboardInterrupt):
        print()


if __name__ == "__main__":
    main()
