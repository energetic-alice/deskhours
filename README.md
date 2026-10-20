# deskhours

[![CI](https://github.com/energetic-alice/deskhours/actions/workflows/ci.yml/badge.svg)](https://github.com/energetic-alice/deskhours/actions/workflows/ci.yml)

Count **your working hours** and remind yourself when the day gets long. Two signals are available: real keyboard and mouse activity, or the prompts you sent to a coding agent.

Python 3.9 or newer, no dependencies, macOS and Windows and Linux.

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

| Harness | Layout it looks for | Override |
|---|---|---|
| Cursor | `.cursor/projects/*/agent-transcripts/` | `DESKHOURS_CURSOR_ROOT` |
| Claude Code | `.claude/projects/` | `DESKHOURS_CLAUDE_ROOT` |
| Codex | `.codex/sessions/` and `.codex/archived_sessions/` | `DESKHOURS_CODEX_ROOTS` |

Nothing needs configuring. Those layouts are looked for under the few places the three operating systems keep user data — your home directory, `~/Library/Application Support`, `$XDG_CONFIG_HOME`, `$XDG_DATA_HOME`, `%APPDATA%`, `%LOCALAPPDATA%` — and the projects inside come from whatever directories the harness itself created. A harness you do not use contributes nothing, and a directory that is not there is not an error.

To see what your machine actually offers:

```bash
deskhours sources
deskhours sources --scan ~/Volumes/work   # only if a harness lives somewhere unusual
```

`sources` prints each directory, whether it exists, and how many prompts and days came from it, so a harness that contributes nothing is visibly missing rather than silently absent. If yours lives somewhere the list above does not cover, `--scan` searches a directory you name, and an override then points at it for good (several paths join with the platform path separator: `:`, or `;` on Windows).

Only turns a person typed count. Agent replies, tool output, injected reminders,
scheduled heartbeats, page-open events and subagent sessions are skipped, so a long
unattended run or an overnight watcher does not become working hours.

These session logs are an internal detail of each tool, not a published format, so a new version can change them. `deskhours sources` is how you notice: a harness that used to report prompts and now reports none has either gone unused or changed its layout.

**Why look in a few places instead of searching the disk?** Because searching is both slower and less safe, which is easy to assume the other way round. Measured on one real machine: checking the candidate places took 0.1 ms and found all 3 installed harnesses, while walking the whole home directory took 4.3 seconds and returned a 4th match — a sandboxed agent session carrying its own nested `.claude/projects/` tree, same layout, same `subagents/` folder. Counting that would have credited an agent's own turns as time a person worked. A search has to know to throw such copies away before it is even correct, and on macOS it needs access to your entire disk to run. `--scan` does apply those exclusions, which is why it stays opt-in and prints what it found instead of counting it.

Every project counts, and none of them has to be configured: each harness keeps one directory per project under its own root, so ten projects are read the same way as one. Narrow it with `--project`, which matches loosely: every harness spells the same project differently, so `--project "my api"` also finds the directory named `Users-me-Projects-My-API`.

A poll reads only the logs written since the day began, because a session file that has not been touched since yesterday cannot hold a prompt from today. The cost therefore follows how much you worked today, not how much history you have kept. Measured on one machine with 388 session logs holding 392 MB, that is 51 MB per poll instead of all of it, and it stays that way as the history grows.

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
pip install -e ".[dev]"
pytest
ruff check src tests
ruff format src tests
```

No runtime dependencies, by design: each platform is reached through a tool it already ships with, so the only install step is the package itself. CI runs the tests on Linux, macOS and Windows against the oldest and newest supported Python, and checks that the command line answers on a machine with no session history at all.

The layout follows the signals it reads:

| Module | Holds |
|---|---|
| `core.py` | the counting rules, with no disk and no operating system |
| `sources.py` | the two signals behind one interface |
| `transcripts.py` | reading agent session logs, and finding where they live |
| `tick.py` | one poll: read, update, maybe remind |
| `state.py` | today's slots on disk |
| `platform.py` | picks the backend for this system |
| `idle/`, `notify/`, `install/` | one module per system, same name in each |

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
