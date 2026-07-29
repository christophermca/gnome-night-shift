#!/bin/python

from pathlib import Path
from datetime import datetime
import subprocess

STATE_FOLDER = "~/.local/state/gnome-night-shift/"
SCHEMA = "org.gnome.desktop.interface"
KEY = "color-scheme"


def is_day_or_night():
    # read values from file
    try:
        state_file = Path.expanduser(Path(STATE_FOLDER, "times"))
        with state_file.open("r", encoding="utf-8") as file:
            times = file.read()
            start, stop = times.split(",")

        current_time = datetime.now().time()
        is_day = current_time > datetime.strptime(stop, "%H:%M").time()
        is_night = current_time > datetime.strptime(start, "%H:%M").time()

        if is_day and not is_night:
            current = "day"

        elif is_night:
            current = "night"

        day_or_night = Path.expanduser(Path(STATE_FOLDER, "is-day-or-night"))
        with day_or_night.open("w", encoding="utf-8") as file:
            file.write(current)
        return current

    except OSError:
        print(
            "[night-shift] Something went wrong when setting colorscheme preference"
        )
        return None


if __name__ == "__main__":
    is_day_or_night()
