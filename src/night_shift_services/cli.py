import argparse
import sys
import importlib.metadata
from pathlib import Path

try:
    __version__ = importlib.metadata.version("gnome-night-shift")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

EXTENSION_UUID = "night-shift@christophermca.github.io"
EXTENSION_SCHEMA_ID = "org.gnome.shell.extensions.night-shift"


def extension_schema_dir() -> Path:
    return (
        Path.home()
        / ".local"
        / "share"
        / "gnome-shell"
        / "extensions"
        / EXTENSION_UUID
        / "schemas"
    )


def night_shift_schema(schema_dir):
    """The Night Shift extension's schema compiled in `schema_dir`, or None.

    Looked up by its ID, the way nocturne-shift (0.7.3+) finds it, so a
    folder of some other app's schemas is never mistaken for it.
    """
    from gi.repository import Gio, GLib

    try:
        source = Gio.SettingsSchemaSource.new_from_directory(
            str(schema_dir), None, False
        )
    except GLib.Error:
        return None  # not a folder, or no gschemas.compiled in it
    return source.lookup(EXTENSION_SCHEMA_ID, False)


def check_schema_path(schema_dir) -> None:
    """Raise ValueError unless `schema_dir` holds the extension's schema.

    Without it the timers would run but couldn't save anything, and only
    log "settings unavailable" every minute. Say so now instead.
    """
    if night_shift_schema(schema_dir) is None:
        raise ValueError(
            f"{schema_dir} doesn't contain the Night Shift extension's "
            f"compiled schema ({EXTENSION_SCHEMA_ID})"
        )


def check_extension_installed() -> None:
    """Raise ValueError unless the extension's compiled schema is there.

    Without it the timers still run, every minute, but have nowhere to read
    or save their settings, so they do nothing. Say so now instead.
    """

    schemas = extension_schema_dir()
    if night_shift_schema(schemas) is None:
        raise ValueError(
            "the Night Shift extension isn't installed "
            f"(no compiled schema in {schemas}). "
            "Install it from extensions.gnome.org first, then run setup again."
        )


def register(subparsers):
    """Entry point for nocturne-shift: add the `services` command, return its handler."""
    services_parser = setup_arguments(subparsers)

    def handler(args):
        if args.subcommand is None:  # bare `nocturne-shift services`
            services_parser.print_help()
            return None  # nothing was done
        return run(args)

    return handler


def forget_last_fetch() -> None:
    from gi.repository import Gio
    from nocturne_shift.bin.settings import Settings
    from nocturne_shift.data_store import DataStore

    settings = Settings(DataStore(str(extension_schema_dir())))
    if not settings.available:
        return
    settings.set("timestamp", "")
    Gio.Settings.sync()


def run(args):
    from . import NightShiftServices

    services = NightShiftServices()
    if args.subcommand == "setup":
        try:
            if args.schema is None:
                check_extension_installed()
            else:
                check_schema_path(args.schema)
            return services.setup(args.schema, args.build_only)
        except ValueError as e:
            sys.exit(f"gnome-night-shift setup: {e}")

    elif args.subcommand == "start":
        return services.start()

    elif args.subcommand == "stop":
        return services.stop()

    elif args.subcommand == "teardown":
        result = services.destroy()
        forget_last_fetch()
        return result


def main(argv=None):
    """The `gnome-night-shift` command: setup/start/stop/teardown on their own.

    gnome-night-shift needs a command of its own so `pipx install
    gnome-night-shift` links one onto PATH (pipx only links the commands of
    the package it installs, not those of its dependencies). It runs the same
    code as `nocturne-shift services ...`.
    """
    parser = argparse.ArgumentParser(
        prog="gnome-night-shift",
        description="Set up the systemd timers that run nocturne-shift",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    _add_actions(parser.add_subparsers(dest="subcommand"))

    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.print_help()
        return 2
    run(args)
    return 0


def setup_arguments(subparsers):
    services_parser = subparsers.add_parser(
        "services",
        prog="nocturne-shift services",
        help="Handle Night-Shift Service",
    )

    services_parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Prints more information",
    )

    _add_actions(
        services_parser.add_subparsers(
            dest="subcommand",
            prog="nocturne-shift services",
        )
    )

    return services_parser


def _add_actions(action_parser):
    """setup/start/stop/teardown, shared by both commands."""
    stop_action_parser = action_parser.add_parser(
        "stop", help="Stops night-shift services"
    )

    start_action_parser = action_parser.add_parser(
        "start", help="Starts night-shift services"
    )

    build_action_parser = action_parser.add_parser(
        "setup", help="Builds night-shift services"
    )

    build_action_parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only build service units",
    )

    build_action_parser.add_argument(
        "schema",
        type=str,
        action="store",
        nargs="?",
        help="Path to GObject schema",
    )

    teardown_action_parser = action_parser.add_parser(
        "teardown", help="Removes linked systemd units"
    )
