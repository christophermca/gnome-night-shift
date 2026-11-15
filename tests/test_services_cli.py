import argparse
from unittest.mock import patch

import pytest

from night_shift_services.cli import register


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


def test_setup_builds_units_for_the_schema(services_class):
    run_services("setup", "/path/to/schemas", "--build-only")

    services_class.assert_called_once_with()
    services_class.return_value.setup.assert_called_once_with(
        "/path/to/schemas", True
    )


@pytest.mark.parametrize(
    "subcommand, method",
    [("start", "start"), ("stop", "stop"), ("teardown", "destroy")],
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
def test_gnome_night_shift_setup(services_class):
    from night_shift_services.cli import main

    assert main(["setup", "/path/to/schemas", "--build-only"]) == 0

    services_class.return_value.setup.assert_called_once_with(
        "/path/to/schemas", True
    )


@pytest.mark.parametrize(
    "subcommand, method",
    [("start", "start"), ("stop", "stop"), ("teardown", "destroy")],
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


def test_setup_with_a_bad_path_exits_with_a_message(services_class):
    from night_shift_services.cli import main

    services_class.return_value.setup.side_effect = ValueError(
        "path contains a control character: '/x\\n'"
    )

    with pytest.raises(SystemExit) as exit_info:
        main(["setup", "/x\n"])

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
    ).write_text("<schemalist/>")
    if compiled:
        (schemas / "gschemas.compiled").write_bytes(b"")
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


def test_setup_with_an_explicit_path_skips_the_check(services_class, home):
    """For system-wide installs and testing: no extension in $HOME needed."""
    from night_shift_services.cli import main

    assert main(["setup", "/path/to/schemas"]) == 0

    services_class.return_value.setup.assert_called_once_with(
        "/path/to/schemas", False
    )


def test_nocturne_shift_services_setup_checks_too(services_class, home):
    with pytest.raises(SystemExit):
        run_services("setup")

    services_class.return_value.setup.assert_not_called()
