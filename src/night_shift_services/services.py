#!/usr/bin/python
import sys
import re
import os
import shlex
import subprocess
import shutil
from pathlib import Path

WATCH_OPTION = "-w"
COMMAND = "nocturne-shift"
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _systemd_escape(value: str) -> str:
    """Make a path safe to write into an ExecStart= line.

    systemd expands `%h`-style specifiers and `$VAR` in ExecStart=, even
    inside quotes, so a literal % or $ must be doubled. Control characters
    can't be written safely at all, so refuse them.
    """
    if _CONTROL_CHARS.search(value):
        raise ValueError(f"path contains a control character: {value!r}")
    return value.replace("%", "%%").replace("$", "$$")


def find_command(name: str = COMMAND) -> str | None:
    """Absolute path of the `nocturne-shift` that belongs to this install.

    pip puts a package's commands next to the Python that runs it: a pipx
    venv's bin/ (per-user or --global), a plain venv's bin/. Look there
    first, so the units call the same install that wrote them, whatever
    PATH systemd uses. Fall back to PATH (e.g. `pip install --user`).
    """
    beside_python = Path(sys.executable).parent / name
    if beside_python.is_file() and os.access(beside_python, os.X_OK):
        return str(beside_python)
    return shutil.which(name)


def units_dir() -> Path:
    """Where setup writes its unit files: ~/.local/share/gnome-night-shift/units.

    Not inside the installed package: with `pipx install --global` that
    folder is owned by root, and a reinstall replaces it, which would leave
    the systemd links pointing at nothing.
    """
    data_home = (
        os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    )
    return Path(data_home) / "gnome-night-shift" / "units"


class Services:
    def __init__(self, source_dir="", target_dir=""):
        self.source_dir = source_dir
        self.target_dir = target_dir

        if sys.platform != "linux":
            sys.exit("Error: Systemd units can ony be deployed on linux")

        list_of_units = []
        with os.scandir(self.source_dir) as units:
            for unit in units:
                list_of_units.append(unit)

        self.all_units = list_of_units
        self.timers = [
            unit for unit in list_of_units if unit.name.endswith(".timer")
        ]

    def _symlink(self, source: str | None = None):
        source = source if source is not None else self.source_dir
        Path(self.target_dir).mkdir(parents=True, exist_ok=True)
        for unit in self.all_units:
            print(f"UNIT_PATH: {unit.name}, {source}")
            if unit.is_file():
                try:
                    src = f"{source}/{unit.name}"
                    target = f"{self.target_dir}/{unit.name}"
                    os.symlink(src, target)
                except FileExistsError:
                    if os.path.islink(target):
                        print(f"is link, target:{target}, src: {unit.path}")
                        os.remove(target)
                        os.symlink(src, target)
                    else:
                        print(f"skipping {unit.name} :: file exists")
                finally:
                    print("+++++")
                    print(f"SYMLINKED {unit.name}\n")

    def _create_units(self, schema=None, tmp_dir=None):
        self.target_dir.mkdir(parents=True, exist_ok=True)

        # progromatically write systemd units vs copy/pasting

        # Always write copies, so ExecStart gets the real command path even
        # without a schema. Fall back to the packaged units if that fails.
        program = find_command()
        for value in (program, schema):
            if value:
                _systemd_escape(value)

        tmp_dir = Path(tmp_dir) if tmp_dir else units_dir()
        tmp_dir.mkdir(parents=True, exist_ok=True)

        self._make_copy_of_unit(self.all_units, schema, tmp_dir, program)

        if any(tmp_dir.iterdir()):  # if directory is not empty
            self._symlink(tmp_dir)
        else:
            self._symlink(self.source_dir)

    def _daemon_reload(self) -> None:
        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"], check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")

    def _start_services(self):
        try:
            self._daemon_reload()

            for timer in self.timers:
                print(f"Starting timer: {timer.name}")

                subprocess.run(
                    ["systemctl", "--user", "enable", "--now", timer.name],
                    check=True,
                )
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")
        finally:
            print("\n")

    def _stop_services(self):
        try:
            self._daemon_reload()

            for timer in self.timers:
                print(f"stopping timer: {timer.name}")

                subprocess.run(
                    ["systemctl", "--user", "disable", "--now", timer.name],
                    check=True,
                )

        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")

    def _remove_generated_units(self, units: Path | None = None):
        """Delete the unit files setup wrote. Only ours, by name."""
        units = Path(units) if units else units_dir()
        for unit in self.all_units:
            (units / unit.name).unlink(missing_ok=True)
        try:
            units.rmdir()  # only if now empty
        except OSError:
            pass

    def _remove_symlink(self):
        for unit in self.all_units:
            if unit.is_file():
                try:
                    target = f"{self.target_dir}/{unit.name}"
                    if os.path.islink(target):
                        os.remove(target)
                except FileNotFoundError:
                    print(f"{unit.name} was not found")
                    pass
                finally:
                    print("-----")
                    print(f"Removed {unit.name}\n")

        self._daemon_reload()

    def _make_copy_of_unit(
        self,
        units: list[str],
        schema_path: str | None,
        save_to_path: str | None,
        program: str | None = None,
    ) -> str | None:
        try:
            # Makes copy with changes to EXECSTART then save to save_to_path
            for unit in units:
                if unit.is_file():
                    file_copy = shutil.copy2(unit, save_to_path)
                    with open(unit, "r", encoding="utf-8") as file:
                        lines = file.readlines()

                        for i, line in enumerate(lines):
                            if line.startswith("ExecStart="):
                                lines[i] = _exec_start(
                                    line, program, schema_path
                                )

                        with open(file_copy, "w") as file:
                            file.writelines(
                                lines
                            )  # overwrites files in save_to_path

        except Exception:
            return None

    # PUBLIC API
    def setup(
        self,
        schema_path=None,
        build_only=False,
    ):
        self._create_units(schema_path)
        if build_only is False:
            self.start()

    def start(self):
        self._start_services()

    def stop(self):
        self._stop_services()

    def destroy(self):
        self.stop()
        self._remove_symlink()
        self._remove_generated_units()


def _exec_start(
    line: str, program: str | None, schema_path: str | None
) -> str:
    """Rebuild one ExecStart= line: swap in `program`, append the schema."""
    unit_program, *args = shlex.split(line.removeprefix("ExecStart="))
    if schema_path:
        # -c and -w take the schema path themselves; otherwise watch it
        if not args or args[-1] not in ("-c", WATCH_OPTION):
            args.append(WATCH_OPTION)

        args.append(_systemd_escape(schema_path))
    # Escape only the paths we insert: the unit's own %h is meant for systemd
    program = _systemd_escape(program) if program else unit_program
    # shlex.join quotes a path with spaces; systemd accepts '...' quoting
    return "ExecStart=" + shlex.join([program, *args]) + "\n"
