# `Services` creates symlinks in ~/.local/share/systemd/user and runs
# `systemctl`. Running that for real in a test would change your actual
# machine, so we split it two ways:
#   - filesystem: use a REAL temp directory, since symlinks are cheap and
#                 checking real files is more convincing than mocking `os`
#   - systemctl:  MOCK it, since it has side effects we can't undo or run in CI
# Picking "real where it's cheap and safe, fake where it isn't" is the core
# judgment call in unit testing.
import os
from pathlib import Path
import pytest

from unittest.mock import patch, call
from night_shift_services import Services, NightShiftServices

UNITS = ["a.timer", "a.service", "b.timer"]


# tmp_path` is a built-in fixture that gives each test its own
# fresh temp directory as a `pathlib.Path`. pytest creates it and cleans up
# old ones for you.
#
# `tmp_path / "systemd" / "user"` is `path.join(tmp, "systemd", "user")`.
@pytest.fixture
def dirs(tmp_path):
    source = tmp_path / "services" / "systemd" / "user"
    source.mkdir(parents=True)  # like `mkdir -p`
    for name in UNITS:
        (source / name).write_text(f"[Unit]\nDescription={name}\n")

    target = tmp_path / "target"
    return source, target


@pytest.fixture
def mock_run():
    with patch("subprocess.run") as run:
        yield run


def test_init_collects_units_and_timers(dirs):
    source, target = dirs
    services = Services(source, target)

    assert sorted(u.name for u in services.all_units) == sorted(UNITS)
    assert sorted(u.name for u in services.timers) == ["a.timer", "b.timer"]


def test_init_refuses_non_linux(dirs, monkeypatch):
    # mock using macOS
    import sys

    monkeypatch.setattr(sys, "platform", "darwin")

    with pytest.raises(SystemExit):
        Services()


def test_symlink_links_every_unit(dirs):
    source, target = dirs

    Services(source, target)._symlink()

    for name in UNITS:
        link = target / name
        assert link.is_symlink()
        assert os.readlink(link) == str(source / name)


def test_symlink_replaces_stale_symlink(dirs, tmp_path):
    source, target = dirs
    target.mkdir()
    (target / "a.timer").symlink_to(tmp_path / "old")

    Services(source, target)._symlink()

    assert os.readlink(target / "a.timer") == str(source / "a.timer")


def test_symlink_skips_regular_file(dirs, capsys):
    _, target = dirs
    target.mkdir()
    (target / "a.timer").write_text("user's own unit")

    Services(_, target)._symlink()

    assert not (target / "a.timer").is_symlink()
    assert (target / "a.timer").read_text() == "user's own unit"
    assert "skipping a.timer :: file exists" in capsys.readouterr().out


def test_setup_links_then_reloads_daemon(dirs, mock_run):
    _, target = dirs

    Services(_, target).setup()

    assert (target / "a.timer").is_symlink()
    assert mock_run.call_args_list[0] == call(
        ["systemctl", "--user", "daemon-reload"], check=True
    )


def test_start_services_enables_every_timer(dirs, mock_run):
    source, target = dirs
    Services(source, target)._start_services()

    for timer in ["a.timer", "b.timer"]:
        mock_run.assert_any_call(
            ["systemctl", "--user", "enable", "--now", timer], check=True
        )


def test_stop_services_disables_every_timer(dirs, mock_run):
    source, target = dirs
    Services(source, target)._stop_services()

    for timer in ["a.timer", "b.timer"]:
        mock_run.assert_any_call(
            ["systemctl", "--user", "disable", "--now", timer], check=True
        )


def test_stop_services_reloads_daemon(dirs, mock_run):
    source, target = dirs
    Services(source, target)._stop_services()

    assert mock_run.call_args_list[0] == call(
        ["systemctl", "--user", "daemon-reload"], check=True
    )


def test_start_services_catches_systemctl_failure(dirs, mock_run, capsys):
    source, target = dirs

    import subprocess

    mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")

    Services(source, target)._start_services()

    assert "Error:" in capsys.readouterr().out


# Test method: destroy()
def test_destroy_removes_symlinks(dirs, mock_run):
    _, target = dirs
    services = Services(_, target)
    services._symlink()

    services.destroy()

    assert list(target.iterdir()) == []


def test_destroy_keeps_custom_user_unit_files(dirs, mock_run):
    source, target = dirs
    target.mkdir()
    (target / "a.timer").write_text("new custom user unit")

    Services(source, target).destroy()

    assert (target / "a.timer").read_text() == "new custom user unit"


def test_destroy_removes_dangling_symlinks(dirs, mock_run, tmp_path):
    source, target = dirs
    target.mkdir()
    (target / "a.timer").symlink_to(tmp_path / "gone")  # points at nothing

    Services(source, target).destroy()

    assert not (target / "a.timer").is_symlink()


def test_destroy_disables_timers(dirs, mock_run):
    source, target = dirs
    Services(source, target).destroy()

    for timer in ["a.timer", "b.timer"]:
        mock_run.assert_any_call(
            ["systemctl", "--user", "disable", "--now", timer], check=True
        )


def test_night_shift_services_setup_passes_schema_and_build_only(dirs):

    source, target = dirs
    services = NightShiftServices(source, target)

    with patch.object(Services, "_create_units") as create_units, patch.object(
        Services, "start"
    ) as start:
        services.setup("/path/to/schemas", True)  # what cli.py passes

    create_units.assert_called_once_with("/path/to/schemas")
    start.assert_not_called()  # --build-only


def test_make_copy_appends_schema_to_exec_start(dirs, tmp_path):
    UNIT = "[Service]\nType=oneshot\nExecStart=/bin/night-shift\nRestart=no\n"
    source, target = dirs
    (source / "x.service").write_text(UNIT)
    out = tmp_path / "out"
    out.mkdir()

    Services(source, target)._make_copy_of_unit(
        [source / "x.service"], "/x/schemas", out
    )

    assert (out / "x.service").read_text() == (
        "[Service]\nType=oneshot\n"
        "ExecStart=/bin/night-shift -w /x/schemas\n"
        "Restart=no\n"
    )


@pytest.mark.parametrize("flag", ["-c", "-w"])
def test_make_copy_reuses_a_trailing_schema_flag(dirs, tmp_path, flag):
    # -c and -w both take the schema path, so append only the path, not a 2nd flag
    unit = f"[Service]\nExecStart=/bin/night-shift {flag}\n"
    source, target = dirs
    (source / "x.service").write_text(unit)
    out = tmp_path / "out"
    out.mkdir()

    Services(source, target)._make_copy_of_unit(
        [source / "x.service"], "/x/schemas", out
    )

    assert (out / "x.service").read_text() == (
        f"[Service]\nExecStart=/bin/night-shift {flag} /x/schemas\n"
    )


def test_make_copy_swaps_in_the_real_command_path(dirs, tmp_path):
    source, target = dirs
    (source / "x.service").write_text(
        "[Service]\nExecStart=%h/.local/bin/nocturne-shift -c\n"
    )
    out = tmp_path / "out"
    out.mkdir()

    Services(source, target)._make_copy_of_unit(
        [source / "x.service"], "/x/schemas", out, "/opt/pipx/bin/nocturne-shift"
    )

    assert (out / "x.service").read_text() == (
        "[Service]\nExecStart=/opt/pipx/bin/nocturne-shift -c /x/schemas\n"
    )


def test_make_copy_quotes_a_path_with_spaces(dirs, tmp_path):
    source, target = dirs
    (source / "x.service").write_text("[Service]\nExecStart=/bin/nocturne-shift -w\n")
    out = tmp_path / "out"
    out.mkdir()

    Services(source, target)._make_copy_of_unit(
        [source / "x.service"], "/my schemas", out, "/home/a b/bin/nocturne-shift"
    )

    assert (out / "x.service").read_text() == (
        "[Service]\nExecStart='/home/a b/bin/nocturne-shift' -w '/my schemas'\n"
    )


def test_setup_without_schema_still_uses_the_real_path(dirs, mock_run, tmp_path):
    source, target = dirs
    (source / "x.service").write_text("[Service]\nExecStart=%h/.local/bin/nocturne-shift -c\n")

    with patch(
        "night_shift_services.services.find_command", return_value="/real/nocturne-shift"
    ):
        Services(source, target)._create_units(tmp_dir=tmp_path / "gen")

    assert (target / "x.service").read_text() == (
        "[Service]\nExecStart=/real/nocturne-shift -c\n"
    )


def test_find_command_prefers_the_one_next_to_python(tmp_path, monkeypatch):
    from night_shift_services.services import find_command

    script = tmp_path / "nocturne-shift"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    monkeypatch.setattr("sys.executable", str(tmp_path / "python"))
    monkeypatch.setenv("PATH", "/nowhere")

    assert find_command() == str(script)


def test_find_command_falls_back_to_path(tmp_path, monkeypatch):
    from night_shift_services.services import find_command

    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "nocturne-shift"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    monkeypatch.setattr("sys.executable", str(tmp_path / "venv" / "python"))
    monkeypatch.setenv("PATH", str(bindir))

    assert find_command() == str(script)


def test_units_dir_follows_xdg_data_home(tmp_path, monkeypatch):
    from night_shift_services.services import units_dir

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    assert units_dir() == tmp_path / "data" / "gnome-night-shift" / "units"


def test_units_dir_defaults_to_local_share(tmp_path, monkeypatch):
    from night_shift_services.services import units_dir

    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert units_dir() == tmp_path / ".local" / "share" / "gnome-night-shift" / "units"


def test_setup_writes_units_outside_the_package(dirs, mock_run, tmp_path):
    import night_shift_services

    source, target = dirs
    Services(source, target).setup("/x/schemas", build_only=True)

    units = tmp_path / "xdg" / "gnome-night-shift" / "units"
    assert sorted(p.name for p in units.iterdir()) == sorted(UNITS)
    assert all(
        os.readlink(target / name) == str(units / name) for name in UNITS
    )
    assert not (Path(night_shift_services.__file__).parent / "tmp").exists()


def test_destroy_removes_the_generated_units(dirs, mock_run, tmp_path):
    source, target = dirs
    services = Services(source, target)
    services.setup("/x/schemas", build_only=True)

    services.destroy()

    assert not (tmp_path / "xdg" / "gnome-night-shift" / "units").exists()


def test_destroy_keeps_other_files_in_the_units_dir(dirs, mock_run, tmp_path):
    source, target = dirs
    services = Services(source, target)
    services.setup("/x/schemas", build_only=True)
    units = tmp_path / "xdg" / "gnome-night-shift" / "units"
    (units / "mine.txt").write_text("keep me")

    services.destroy()

    assert sorted(p.name for p in units.iterdir()) == ["mine.txt"]
