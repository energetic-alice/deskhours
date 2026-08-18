# deskhours

Count **your working hours** and remind yourself when the day gets long. Two signals are available: real keyboard and mouse activity, or the prompts you sent to a coding agent.

## How it works

1. A small background job polls every few minutes.
2. If the signal says you were there, the current **30-minute slot** counts as active.
3. Active hours today = number of distinct active slots × slot length.
4. When you cross **8h** (configurable), deskhours shows a reminder — then again at each further whole hour.

## Two ways to count

### `--source input` (default)

Idle time from the operating system. A slot counts when idle time is below a threshold (default **5 minutes**). Docs, Zoom, terminals and browsers all count, because the signal is system input, not a specific app.

What it does *not* measure:

- A meeting where you never touch keyboard or mouse may under-count.
- Sleep, closed lid and lock screen grow idle time, so they do not count.
- Which app you used — on purpose, to stay privacy-friendly.

### `--source agents`

Prompts you sent to a coding agent. deskhours reads the session logs that Cursor, Claude Code and Codex already keep on your machine, and counts a slot when it holds at least one prompt you typed:

| Harness | Where the sessions live |
|---|---|
| Cursor | `~/.cursor/projects/*/agent-transcripts/` |
| Claude Code | `~/.claude/projects/` |
| Codex | `~/.codex/sessions/` and `~/.codex/archived_sessions/` |

Only turns a person typed count. Agent replies, tool output, injected reminders and subagent sessions are skipped, so a long unattended run or an overnight watcher does not become working hours.

All projects count by default. Narrow it with `--project`, which matches loosely, so `--project "DevOps Assistant"` also finds the directory named `Users-me-Documents-DevOps-Assistant`.

What it does *not* measure: thinking, reading, reviewing a diff, meetings, and any work you did without an agent.

### Which one to pick

| | `input` | `agents` |
|---|---|---|
| Knows about the past | no — hours exist only because earlier polls saved them | yes — rebuilds the day from the logs on every run |
| Survives a missed poll | no | yes |
| Needs the background job | yes, to count at all | only for the reminder |
| Works without an idle backend | no | yes, on any platform |

Because the two counts answer different questions, each keeps its own state file and its own background job. You can run both at once, or use `agents` on demand with no install at all:

```bash
deskhours status --source agents
```

## Status

| Platform | Idle probe | Reminder | Background install |
|---|---|---|---|
| **macOS** | `IOHIDSystem` | notification or modal dialog | `deskhours install` |
| **Windows** | `GetLastInputInfo` | MessageBox | draft in `packagers/windows/` |
| **Linux** | `xprintidle` (X11) | `notify-send` | draft in `packagers/linux/` |
| Linux Wayland | not yet | — | — |

No third-party Python packages. On Linux you also need the system tools above (`xprintidle`, `notify-send`). The idle probe column applies to `--source input`; `--source agents` reads files and works everywhere, but the reminder and the background install are still per platform.

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

Each source installs its own job and keeps its own state, so installing one never replaces the other:

| Source | LaunchAgent | State file |
|---|---|---|
| `input` | `com.deskhours.plist` | `~/.local/share/deskhours/state.json` |
| `agents` | `com.deskhours.agents.plist` | `~/.local/share/deskhours/state-agents.json` |

```bash
deskhours install --source agents
deskhours uninstall --source agents
deskhours uninstall
```

## CLI

```bash
deskhours status                 # today hours + current idle (no write)
deskhours status --source agents # today hours from agent prompts (no write)
deskhours status --source agents --project "DevOps Assistant"
deskhours tick                   # poll, save if active, maybe notify
deskhours tick --dry-run         # same print as status
deskhours tick -v                # real tick + print status
deskhours tick --threshold 6
deskhours install --dialog
deskhours uninstall
```

## Development

```bash
pip install -e . pytest
pytest
```

## Privacy

- Runs locally.
- Stores only today's slot list + last notified hour.
- No network calls. No telemetry. No app names.
- `--source agents` reads only the timestamps and the shape of your session logs. Prompt text is used for one purpose — deciding whether a line is a real human turn — and is never stored.

## Roadmap

- [x] macOS end-to-end
- [x] Windows idle + MessageBox
- [x] Linux X11 idle + notify-send
- [x] Count from coding-agent prompts (`--source agents`)
- [ ] `deskhours install` for Windows Task Scheduler
- [ ] `deskhours install` for systemd --user
- [ ] Wayland idle backend

## License

MIT — see [LICENSE](LICENSE).
