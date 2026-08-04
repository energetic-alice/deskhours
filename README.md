# deskhours

Count **time at your computer** from real keyboard/mouse activity, and remind yourself when the day gets long.

## How it works

1. A small background job polls idle time every few minutes.
2. If idle time is below a threshold (default **5 minutes**), the current **30-minute slot** counts as active.
3. Active hours today = number of distinct active slots × slot length.
4. When you cross **8h** (configurable), deskhours shows a reminder — then again at each further whole hour.

Docs, Zoom, terminals, and browsers all count, because the signal is system input — not a specific app.

### What it does *not* measure

- A meeting where you never touch keyboard/mouse may under-count.
- Sleep / lid closed / lock screen → idle grows → not counted.
- Which app you used (on purpose — privacy-friendly).

## Status

| Platform | Idle probe | Reminder | Background install |
|---|---|---|---|
| **macOS** | `IOHIDSystem` | notification or modal dialog | `deskhours install` |
| **Windows** | `GetLastInputInfo` | MessageBox | draft in `packagers/windows/` |
| **Linux** | `xprintidle` (X11) | `notify-send` | draft in `packagers/linux/` |
| Linux Wayland | not yet | — | — |

No third-party Python packages. On Linux you also need the system tools above (`xprintidle`, `notify-send`).

## Install (macOS)

Homebrew Python is PEP-668 managed — use a venv:

```bash
git clone https://github.com/energetic-alice/deskhours.git
cd deskhours
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
deskhours status
deskhours install --dialog
```

`install` writes `~/Library/LaunchAgents/com.deskhours.plist` and loads it (poll every **5 minutes**). Run it from the activated venv so the agent points at `.venv/bin/deskhours` (outside `Documents`, so macOS TCC will not block it).

State file: `~/.local/share/deskhours/state.json`

```bash
deskhours uninstall
```

## CLI

```bash
deskhours status                 # today hours + current idle (no write)
deskhours tick                   # poll, save if active, maybe notify
deskhours tick --dry-run         # same print as status
deskhours tick -v                # real tick + print status
deskhours tick --threshold 6
deskhours install --dialog
deskhours uninstall
```

## Privacy

- Runs locally.
- Stores only today's slot list + last notified hour.
- No network calls. No telemetry. No app names.

## Roadmap

- [x] macOS end-to-end
- [x] Windows idle + MessageBox
- [x] Linux X11 idle + notify-send
- [ ] `deskhours install` for Windows Task Scheduler
- [ ] `deskhours install` for systemd --user
- [ ] Wayland idle backend

## License

MIT — see [LICENSE](LICENSE).
