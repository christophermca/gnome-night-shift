import argparse
import sys
import importlib.metadata

try:
    __version__ = importlib.metadata.version("gnome-night-shift")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


def register(subparsers):
    """Entry point for nocturne-shift: add the `services` command, return its handler."""
    services_parser = setup_arguments(subparsers)

    def handler(args):
        if args.subcommand is None:  # bare `nocturne-shift services`
            services_parser.print_help()
            return None  # nothing was done
        return run(args)

    return handler


def run(args):
    from . import NightShiftServices

    services = NightShiftServices()
    if args.subcommand == "setup":
        try:
            return services.setup(args.schema, args.build_only)
        except ValueError as e:
            sys.exit(f"gnome-night-shift setup: {e}")
    elif args.subcommand == "start":
        return services.start()
    elif args.subcommand == "stop":
        return services.stop()
    elif args.subcommand == "teardown":
        return services.destroy()


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
