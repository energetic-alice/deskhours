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

| Harness | Where the sessions live | Override |
|---|---|---|
| Cursor | `~/.cursor/projects/*/agent-transcripts/` | `DESKHOURS_CURSOR_ROOT` |
| Claude Code | `~/.claude/projects/` | `DESKHOURS_CLAUDE_ROOT` |
| Codex | `~/.codex/sessions/` and `~/.codex/archived_sessions/` | `DESKHOURS_CODEX_ROOTS` |

Nothing needs configuring on a normal machine: projects are discovered from whatever directories a harness has created, a harness you do not use contributes nothing, and a missing directory is not an error. Set an override only if a harness lives somewhere else; several paths join with the platform path separator (`:`, or `;` on Windows).

To see what your machine actually offers:

```bash
deskhours sources
```

It prints each directory, whether it exists, and how many prompts and days came from it — so a harness that contributes nothing is visibly missing rather than silently absent.

Only turns a person typed count. Agent replies, tool output, injected reminders and subagent sessions are skipped, so a long unattended run or an overnight watcher does not become working hours.

**Why not search the disk for transcripts?** Because a match is not proof. A sandboxed agent session can carry its own nested `.claude/projects/` tree, with the same layout and the same `subagents/` folder, and counting it would credit an agent's own turns as your working time. Scanning for the file pattern also finds JSONL datasets, captured CLI output and cached tool logs — on one real machine, 52 stray `.jsonl` files against 435 genuine ones. Known locations plus an override stay honest; `deskhours sources` makes the result checkable.

All projects count by default. Narrow it with `--project`, which matches loosely: every harness spells the same project differently, so `--project "my api"` also finds the directory named `Users-me-Projects-My-API`.

What it does *not* measure: thinking, reading, reviewing a diff, meetings, and any work you did without an agent.

### Which one to pick

| | `input` | `agents` |
|---|---|---|
| Knows about the past | no — hours exist only because earlier polls saved them | yes — rebuilds the day from the logs on every run |
| Survives a missed poll | no | yes |
| Needs the background job | yes, to count at all | only for the reminder |
| Works without an idle backend | no | yes, on any platform |

Because the two counts answer different questions, each keeps its own state file. One background job runs at a time, so pick the signal you want reminders from — and read the other on demand, with no install at all:

```bash
deskhours status --source agents
```

## Status

| Platform | Idle probe | Reminder | Background install |
|---|---|---|---|
| **macOS** | `IOHIDSystem` | notification or modal dialog | `deskhours install` (LaunchAgent) |
| **Windows** | `GetLastInputInfo` | MessageBox | `deskhours install` (Task Scheduler) |
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

## Install (Windows)

```bat
git clone https://github.com/energetic-alice/deskhours.git
cd deskhours
py -m venv .venv
.venv\Scripts\activate
pip install -e .
deskhours status
deskhours install --dialog
```

`install` creates a Task Scheduler task named `deskhours` that runs every **5 minutes** under your account, tied to a logged-on session so the reminder can actually appear on screen. Inspect or remove it from the command line:

```bat
schtasks /Query /TN deskhours
deskhours uninstall
```

Install from the activated venv, so the task points at `.venv\Scripts\deskhours.exe`. Without the console script on `PATH` the task falls back to the interpreter that ran `install`, which only works if that interpreter can import the package.

## One job, switched by a flag

There is a single background job — `com.deskhours` on macOS, the `deskhours` task on Windows — and `--source` decides what it counts. Installing again replaces it rather than adding a second one, because two jobs would mean two reminders for the same day:

```bash
deskhours install                  # count keyboard and mouse activity
deskhours install --source agents  # replace it: count agent prompts instead
deskhours uninstall
```

State is kept per source, so switching back and forth does not mix the two counts:

| Source | State file |
|---|---|
| `input` | `state.json` |
| `agents` | `state-agents.json` |

State lives in `~/.local/share/deskhours/` (`%LOCALAPPDATA%\deskhours\` on Windows). `status` reads the file for the source you ask about, and `--source agents` also rebuilds the day from the logs, so it is correct even right after a switch.

## CLI

```bash
deskhours status                 # today hours + current idle (no write)
deskhours status --source agents # today hours from agent prompts (no write)
deskhours status --source agents --project "my api"
deskhours sources                # which transcript directories were found
deskhours sources --project "my api"
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
- [x] `deskhours install` for Windows Task Scheduler
- [ ] `deskhours install` for systemd --user
- [ ] Wayland idle backend
