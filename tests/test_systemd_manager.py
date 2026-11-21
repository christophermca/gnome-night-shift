# SystemdManager against a fake systemd on a private D-Bus daemon.
#
# Mocks can't tell whether a method name or a D-Bus signature is right:
# a real bus refuses a call whose arguments don't match the interface. So
# these tests start their own dbus-daemon (never your session bus), put a
# small fake org.freedesktop.systemd1.Manager on it, and check what it got.
import shutil
import subprocess
import threading

import pytest
from gi.repository import Gio, GLib

from night_shift_services.systemd_manager import (
    BUS_NAME,
    MANAGER,
    OBJECT_PATH,
    SystemdError,
    SystemdManager,
)

pytestmark = pytest.mark.skipif(
    shutil.which("dbus-daemon") is None, reason="dbus-daemon is not installed"
)

# The methods SystemdManager calls, with systemd's real signatures
INTERFACE = f"""
<node>
  <interface name="{MANAGER}">
    <method name="Reload"/>
    <method name="EnableUnitFiles">
      <arg type="as" direction="in"/><arg type="b" direction="in"/>
      <arg type="b" direction="in"/>
      <arg type="b" direction="out"/><arg type="a(sss)" direction="out"/>
    </method>
    <method name="DisableUnitFiles">
      <arg type="as" direction="in"/><arg type="b" direction="in"/>
      <arg type="a(sss)" direction="out"/>
    </method>
    <method name="StartUnit">
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="o" direction="out"/>
    </method>
    <method name="StopUnit">
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="o" direction="out"/>
    </method>
    <method name="RestartUnit">
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="o" direction="out"/>
    </method>
  </interface>
</node>
"""

REPLIES = {
    "Reload": None,
    "EnableUnitFiles": GLib.Variant("(ba(sss))", (False, [])),
    "DisableUnitFiles": GLib.Variant("(a(sss))", ([],)),
    "StartUnit": GLib.Variant("(o)", ("/org/freedesktop/systemd1/job/1",)),
    "StopUnit": GLib.Variant("(o)", ("/org/freedesktop/systemd1/job/2",)),
    "RestartUnit": GLib.Variant("(o)", ("/org/freedesktop/systemd1/job/3",)),
}


class FakeSystemd:
    """Serves the interface above from its own thread and records each call."""

    def __init__(self, address):
        self.calls = []
        self.missing_units = set()  # units that answer NoSuchUnit
        self._address = address
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        assert self._ready.wait(10), "fake systemd didn't start"

    def _serve(self):
        context = GLib.MainContext()
        context.push_thread_default()  # handlers run in this thread
        self._loop = GLib.MainLoop(context)
        bus = _connect(self._address)
        node = Gio.DBusNodeInfo.new_for_xml(INTERFACE)
        bus.register_object(
            OBJECT_PATH, node.interfaces[0], self._on_call, None, None
        )
        reply = bus.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "RequestName",
            GLib.Variant("(su)", (BUS_NAME, 0)),
            GLib.VariantType("(u)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        assert reply.unpack() == (1,)  # primary owner
        self._ready.set()
        self._loop.run()
        bus.close_sync(None)
        context.pop_thread_default()

    def _on_call(self, conn, sender, path, iface, method, params, invocation):
        args = params.unpack()
        self.calls.append((method, args))
        unit = args[0] if args and isinstance(args[0], str) else None
        if unit in self.missing_units:
            invocation.return_dbus_error(
                "org.freedesktop.systemd1.NoSuchUnit",
                f"Unit {args[0]} not found.",
            )
        else:
            invocation.return_value(REPLIES[method])

    def stop(self):
        self._loop.quit()
        self._thread.join(10)


def _connect(address):
    return Gio.DBusConnection.new_for_address_sync(
        address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None,
        None,
    )


@pytest.fixture
def bus_address():
    daemon = subprocess.Popen(
        ["dbus-daemon", "--session", "--nofork", "--print-address=1"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        yield daemon.stdout.readline().strip()
    finally:
        daemon.terminate()
        daemon.wait(10)


@pytest.fixture
def systemd(bus_address):
    fake = FakeSystemd(bus_address)
    yield fake
    fake.stop()


@pytest.fixture
def manager(bus_address, systemd):
    bus = _connect(bus_address)
    yield SystemdManager(bus=bus)
    bus.close_sync(None)


def test_reload(manager, systemd):
    manager.reload()

    assert systemd.calls == [("Reload", ())]


def test_enable_sends_the_units_not_runtime_not_forced(manager, systemd):
    manager.enable(["a.timer", "b.timer"])

    assert systemd.calls == [
        ("EnableUnitFiles", (["a.timer", "b.timer"], False, False))
    ]


def test_disable_sends_the_units_not_runtime(manager, systemd):
    manager.disable(["a.timer"])

    assert systemd.calls == [("DisableUnitFiles", (["a.timer"], False))]


@pytest.mark.parametrize(
    "method, dbus_method, job",
    [
        ("start", "StartUnit", "/org/freedesktop/systemd1/job/1"),
        ("stop", "StopUnit", "/org/freedesktop/systemd1/job/2"),
        ("restart", "RestartUnit", "/org/freedesktop/systemd1/job/3"),
    ],
)
def test_unit_jobs_use_replace_mode_and_return_the_job(
    manager, systemd, method, dbus_method, job
):
    assert getattr(manager, method)("a.timer") == job

    assert systemd.calls == [(dbus_method, ("a.timer", "replace"))]


def test_a_systemd_error_becomes_a_readable_systemd_error(manager, systemd):
    systemd.missing_units.add("x.service")

    with pytest.raises(SystemdError) as raised:
        manager.restart("x.service")

    # without the "GDBus.Error:org.freedesktop.systemd1.NoSuchUnit:" prefix
    assert str(raised.value) == "RestartUnit failed: Unit x.service not found."


def test_no_systemd_on_the_bus_is_a_systemd_error(bus_address):
    bus = _connect(bus_address)  # a bus with nothing called systemd1 on it
    try:
        with pytest.raises(SystemdError, match="Reload failed"):
            SystemdManager(bus=bus).reload()
    finally:
        bus.close_sync(None)


def test_creating_one_does_not_connect(monkeypatch):
    def fail(*args):
        raise AssertionError("connected to the session bus")

    monkeypatch.setattr(Gio, "bus_get_sync", fail)

    SystemdManager()  # connects on the first call, not here


def test_no_session_bus_is_a_systemd_error(monkeypatch):
    def no_bus(*args):
        raise GLib.Error("Cannot autolaunch D-Bus without X11 $DISPLAY")

    monkeypatch.setattr(Gio, "bus_get_sync", no_bus)

    with pytest.raises(SystemdError, match="can't connect to the session bus"):
        SystemdManager().reload()
