import argparse
from unittest.mock import patch
import shutil
import subprocess

import pytest

from night_shift_services.cli import register

NIGHT_SHIFT_XML = """<schemalist>
  <schema id="org.gnome.shell.extensions.night-shift"
          path="/org/gnome/shell/extensions/night-shift/">
    <key name="timestamp" type="s"><default>""</default></key>
  </schema>
</schemalist>"""

# Another app's schema: a folder holding only this is the wrong folder
OTHER_APP_XML = """<schemalist>
  <schema id="com.example.other" path="/com/example/other/">
    <key name="timestamp" type="s"><default>""</default></key>
  </schema>
</schemalist>"""


@pytest.fixture
def make_schemas(tmp_path):
    """make_schemas(folder, night_shift=True, other_app=False, compile=True)
    writes the chosen schemas into tmp_path/folder and compiles them."""
    if shutil.which("glib-compile-schemas") is None:
        pytest.skip("glib-compile-schemas is not installed")

    def make(folder, night_shift=True, other_app=False, compile=True):
        schemas = tmp_path / folder
        schemas.mkdir(parents=True)
        if night_shift:
            (
                schemas / "org.gnome.shell.extensions.night-shift.gschema.xml"
            ).write_text(NIGHT_SHIFT_XML)
        if other_app:
            (schemas / "com.example.other.gschema.xml").write_text(
                OTHER_APP_XML
            )
        if compile:
            subprocess.run(["glib-compile-schemas", str(schemas)], check=True)
        return schemas

    return make


@pytest.fixture
def schema_dir(make_schemas):
    """A folder with the Night Shift extension's compiled schema."""
    return make_schemas("schemas")


@pytest.fixture
def services_class():
    # run() does `from . import NightShiftServices`, so patch it on the package
    with patch("night_shift_services.NightShiftServices") as services_class:
        yield services_class


def run_services(*args):
    """Parse like nocturne-shift does, then call the handler register() returned."""
    parser = argparse.ArgumentParser(prog="nocturne-shift")
    handler = register(parser.add_subparsers(dest="command"))
    return handler(parser.parse_args(["services", *args]))


def test_setup_builds_units_for_the_schema(services_class, schema_dir):
    run_services("setup", str(schema_dir), "--build-only")

    services_class.assert_called_once_with()
    services_class.return_value.setup.assert_called_once_with(
        str(schema_dir), True
    )


@pytest.mark.parametrize(
    "subcommand, method",
    [
        ("start", "start"),
        ("stop", "stop"),
        ("run-once", "run_once"),
        ("teardown", "destroy"),
    ],
)
def test_subcommands(services_class, subcommand, method):
    run_services(subcommand)

    getattr(services_class.return_value, method).assert_called_once_with()


def test_bare_services_prints_help_and_does_nothing(services_class, capsys):
    result = run_services()

    assert "usage: nocturne-shift services" in capsys.readouterr().out
    assert result is None  # main() returns None
    services_class.assert_not_called()


# `gnome-night-shift ...`: the same actions as `nocturne-shift services ...`
def test_gnome_night_shift_setup(services_class, schema_dir):
    from night_shift_services.cli import main

    assert main(["setup", str(schema_dir), "--build-only"]) == 0

    services_class.return_value.setup.assert_called_once_with(
        str(schema_dir), True
    )


@pytest.mark.parametrize(
    "subcommand, method",
    [
        ("start", "start"),
        ("stop", "stop"),
        ("run-once", "run_once"),
        ("teardown", "destroy"),
    ],
)
def test_gnome_night_shift_subcommands(services_class, subcommand, method):
    from night_shift_services.cli import main

    assert main([subcommand]) == 0

    getattr(services_class.return_value, method).assert_called_once_with()


def test_bare_gnome_night_shift_prints_help_and_fails(services_class, capsys):
    from night_shift_services.cli import main

    assert main([]) == 2
    assert "usage: gnome-night-shift" in capsys.readouterr().out
    services_class.assert_not_called()


def test_gnome_night_shift_is_a_console_script():
    from importlib.metadata import distribution

    scripts = {
        ep.name: ep.value
        for ep in distribution("gnome-night-shift").entry_points
        if ep.group == "console_scripts"
    }
    assert scripts == {"gnome-night-shift": "night_shift_services.cli:main"}


def test_setup_with_a_bad_path_exits_with_a_message(
    services_class, make_schemas
):
    bad_schema = make_schemas("x\n")
    from night_shift_services.cli import main

    services_class.return_value.setup.side_effect = ValueError(
        "path contains a control character: '/x\\n'"
    )

    with pytest.raises(SystemExit) as exit_info:
        main(["setup", str(bad_schema)])

    assert exit_info.value.code == (
        "gnome-night-shift setup: path contains a control character: '/x\\n'"
    )


# `setup` with no path relies on the extension's installed schemas, because
# that's where nocturne-shift reads its settings from by default.
EXTENSION_SCHEMAS = ".local/share/gnome-shell/extensions/night-shift@christophermca.github.io/schemas"


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An empty home folder: Path.home() reads $HOME."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def install_extension(home, compiled=True):
    """Lay out the extension's schemas the way GNOME Shell installs them."""
    schemas = home / EXTENSION_SCHEMAS
    schemas.mkdir(parents=True)
    (
        schemas / "org.gnome.shell.extensions.night-shift.gschema.xml"
    ).write_text(NIGHT_SHIFT_XML)
    if compiled:
        if shutil.which("glib-compile-schemas") is None:
            pytest.skip("glib-compile-schemas is not installed")
        subprocess.run(["glib-compile-schemas", str(schemas)], check=True)
    return schemas


def test_setup_without_the_extension_exits_with_a_message(
    services_class, home
):
    from night_shift_services.cli import main

    with pytest.raises(SystemExit) as exit_info:
        main(["setup"])

    message = exit_info.value.code
    assert message.startswith(
        "gnome-night-shift setup: the Night Shift extension isn't installed"
    )
    assert str(home / EXTENSION_SCHEMAS) in message  # says where it looked
    services_class.return_value.setup.assert_not_called()  # no timers made


def test_setup_with_an_uncompiled_schema_exits(services_class, home):
    """The XML alone isn't enough: nocturne-shift reads gschemas.compiled."""
    from night_shift_services.cli import main

    install_extension(home, compiled=False)

    with pytest.raises(SystemExit):
        main(["setup"])

    services_class.return_value.setup.assert_not_called()


def test_setup_with_the_extension_installed_runs(services_class, home):
    from night_shift_services.cli import main

    install_extension(home)

    assert main(["setup"]) == 0

    services_class.return_value.setup.assert_called_once_with(None, False)


def test_setup_with_an_explicit_schema_path(services_class, home, schema_dir):
    """For system-wide extension installs: no extension in $HOME needed."""
    from night_shift_services.cli import main

    assert main(["setup", str(schema_dir)]) == 0

    services_class.return_value.setup.assert_called_once_with(
        str(schema_dir), False
    )


@pytest.mark.parametrize(
    "folder_kwargs, why",
    [
        (dict(night_shift=False, other_app=True), "another app's schema"),
        (dict(night_shift=True, compile=False), "not compiled"),
        (dict(night_shift=False, other_app=False), "empty folder"),
    ],
)
def test_setup_refuses_a_path_without_the_night_shift_schema(
    services_class, make_schemas, folder_kwargs, why
):
    from night_shift_services.cli import main

    wrong = make_schemas("wrong", **folder_kwargs)

    with pytest.raises(SystemExit) as exit_info:
        main(["setup", str(wrong)])

    message = exit_info.value.code
    assert message == (
        f"gnome-night-shift setup: {wrong} doesn't contain the Night Shift "
        "extension's compiled schema (org.gnome.shell.extensions.night-shift)"
    ), why
    services_class.return_value.setup.assert_not_called()  # no timers made


def test_setup_refuses_a_path_that_does_not_exist(services_class, tmp_path):
    from night_shift_services.cli import main

    with pytest.raises(SystemExit):
        main(["setup", str(tmp_path / "no-such-folder")])

    services_class.return_value.setup.assert_not_called()


def test_setup_accepts_a_shared_folder_with_the_night_shift_schema(
    services_class, make_schemas
):
    """Like /usr/share/glib-2.0/schemas: many schemas, found by ID (as
    nocturne-shift 0.7.3+ finds it too)."""
    from night_shift_services.cli import main

    shared = make_schemas("shared", night_shift=True, other_app=True)

    assert main(["setup", str(shared)]) == 0


def test_nocturne_shift_services_setup_checks_too(services_class, home):
    with pytest.raises(SystemExit):
        run_services("setup")

    services_class.return_value.setup.assert_not_called()


# teardown also clears the extension's `timestamp`, so the extension can tell
# the timers are gone (it shows its setup reminder when `timestamp` is empty)
@pytest.fixture
def extension_settings():
    """nocturne-shift's Settings, as forget_last_fetch() imports it."""
    with patch(
        "nocturne_shift.bin.settings.Settings"
    ) as settings_class, patch("gi.repository.Gio.Settings.sync") as sync:
        settings_class.return_value.available = True
        yield settings_class.return_value, sync


def test_teardown_clears_the_extension_timestamp(
    services_class, extension_settings
):
    settings, sync = extension_settings

    run_services("teardown")

    services_class.return_value.destroy.assert_called_once_with()
    settings.set.assert_called_once_with("timestamp", "")
    sync.assert_called_once_with()  # the write finishes before the command exits


def test_teardown_without_the_extension_leaves_settings_alone(
    services_class, extension_settings
):
    settings, sync = extension_settings
    settings.available = False  # extension not installed

    run_services("teardown")

    services_class.return_value.destroy.assert_called_once_with()  # still removed
    settings.set.assert_not_called()
    sync.assert_not_called()


def test_stop_keeps_the_timestamp(services_class, extension_settings):
    """Only teardown removes the timers for good; stop can be started again."""
    settings, _ = extension_settings

    run_services("stop")

    settings.set.assert_not_called()
