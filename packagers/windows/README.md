# Windows packager

`deskhours install` now creates the Task Scheduler task itself, so nothing here is required. See the Windows section of the top-level [README](../../README.md).

What `install` runs, for reference or for building the task by hand:

```bat
schtasks /Create /TN deskhours /TR "\"C:\path\to\deskhours.exe\" tick --threshold 8.0 --idle-threshold 300 --slot 30 --source input --dialog" /SC MINUTE /MO 5 /RU %USERNAME% /IT /F
```

Notes for anyone adjusting it:

- `/IT` keeps the task tied to a logged-on session. Drop it and the reminder still runs, but its window has no desktop to appear on.
- `/RU` with your own account plus `/IT` is what avoids a stored-password prompt. `install` passes the bare user name, which is what a local account needs; on a domain machine schtasks may want `DOMAIN\user`, so create the task by hand with that form.
- Older Windows builds cap the `/TR` value at 261 characters. A long install path plus `--project` can reach that, in which case shorten the path or add the console script to `PATH` and pass `deskhours` alone.
- There is only ever one task. `--source agents` rewrites the same `deskhours` task, because two tasks would fire two reminders for the same day.
