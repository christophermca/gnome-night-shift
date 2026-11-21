"""This user's systemd, over the session bus: what `systemctl --user` does.

systemctl is itself a client of systemd's D-Bus API (org.freedesktop.systemd1.Manager
on the session bus for --user). Calling that API with Gio does the same work
without starting a process, and errors come back as exceptions instead of exit codes.
"""

import re

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

BUS_NAME = "org.freedesktop.systemd1"
OBJECT_PATH = "/org/freedesktop/systemd1"
MANAGER = "org.freedesktop.systemd1.Manager"

# "replace": queue the job, replacing a conflicting one, as systemctl does
JOB_MODE = "replace"

# "GDBus.Error:org.freedesktop.systemd1.NoSuchUnit: Unit x.timer not found."
_REMOTE_ERROR_PREFIX = re.compile(r"^GDBus\.Error:[\w.]+:\s*")


class SystemdError(Exception):
    """systemd refused a call, or the session bus couldn't be reached."""


class SystemdManager:
    """Calls org.freedesktop.systemd1.Manager on the session bus.

    `bus` is for tests: a Gio.DBusConnection to use instead of the session bus.
    The session bus is only connected on the first call, so creating a
    SystemdManager never fails.
    """

    def __init__(self, bus: Gio.DBusConnection | None = None):
        self._bus = bus

    @property
    def bus(self) -> Gio.DBusConnection:
        if self._bus is None:
            try:
                self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            except GLib.Error as e:
                raise SystemdError(
                    f"can't connect to the session bus: {e.message}"
                ) from e
        return self._bus

    def _call(self, method: str, params: GLib.Variant | None, reply: str):
        try:
            return self.bus.call_sync(
                BUS_NAME,
                OBJECT_PATH,
                MANAGER,
                method,
                params,
                GLib.VariantType(reply),
                Gio.DBusCallFlags.NONE,
                -1,  # the bus default (25 s)
                None,
            ).unpack()
        except GLib.Error as e:
            message = _REMOTE_ERROR_PREFIX.sub("", e.message)
            raise SystemdError(f"{method} failed: {message}") from e

    # systemctl --user daemon-reload
    def reload(self) -> None:
        self._call("Reload", None, "()")

    # systemctl --user enable UNIT...  (runtime=False: survives a reboot,
    # force=False: don't overwrite links that point somewhere else)
    def enable(self, units: list[str]) -> None:
        self._call(
            "EnableUnitFiles",
            GLib.Variant("(asbb)", (list(units), False, False)),
            "(ba(sss))",
        )

    # systemctl --user disable UNIT...
    def disable(self, units: list[str]) -> None:
        self._call(
            "DisableUnitFiles",
            GLib.Variant("(asb)", (list(units), False)),
            "(a(sss))",
        )

    # systemctl --user start / stop / restart UNIT. Each returns the queued
    # job's object path; systemd runs the job after the call returns.
    def start(self, unit: str) -> str:
        return self._unit_job("StartUnit", unit)

    def stop(self, unit: str) -> str:
        return self._unit_job("StopUnit", unit)

    def restart(self, unit: str) -> str:
        return self._unit_job("RestartUnit", unit)

    def _unit_job(self, method: str, unit: str) -> str:
        (job,) = self._call(
            method, GLib.Variant("(ss)", (unit, JOB_MODE)), "(o)"
        )
        return job
