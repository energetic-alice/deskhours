# Windows packager (draft)

`deskhours` already reads idle time on Windows via `GetLastInputInfo` and can show a `MessageBox` reminder.

Background install is not wired into `deskhours install` yet. Until then:

1. `pip install deskhours` (or `pip install -e .` from a clone)
2. Create a Task Scheduler task that runs every 5 minutes:

```text
Program: deskhours
Arguments: tick --threshold 8 --dialog
```

Run only when the user is logged on.
