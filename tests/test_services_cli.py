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
