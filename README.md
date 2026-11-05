# gnome-night-shift

Switch GNOME between light and dark at sunrise and sunset:
systemd timers (`nocturne-shift services`) for the Night Shift extension

---

The helper for the [Night Shift GNOME extension](https://github.com/christophermca/gnome-shell-extension-night-shift):
it switches GNOME between light and dark at sunrise and sunset.

It installs [`nocturne-shift`](https://pypi.org/project/nocturne-shift/) and the
systemd timers that run it, managed with the `gnome-night-shift` command:

```sh
gnome-night-shift setup [SCHEMA_PATH]   # write, link and start the timers
gnome-night-shift stop
gnome-night-shift start
gnome-night-shift teardown              # stop and remove the timers
```

The same actions are also available as `nocturne-shift services ...` when
`nocturne-shift` is on your PATH.

## Install

```sh
pipx install --system-site-packages gnome-night-shift
```

`--system-site-packages` uses your distro's PyGObject instead of building it.
Requires Linux with systemd. If pipx tries to build PyGObject anyway (its uv
backend ignores system packages), add `--backend pip`.
