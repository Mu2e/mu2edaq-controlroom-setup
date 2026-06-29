# Standardized control-room start/stop script template

This directory is an adoption kit for **application repositories** (e.g.
`mu2edaq-dashboard`, `mu2edaq-bigredbox`). The control room launches each
app through the dispatcher `crs-app start <app-id>` / `crs-app stop
<app-id>`, which looks for `start-mu2edaq-<app>.sh` / `stop-mu2edaq-<app>.sh`
in `~/controlroom/bin` (or the app's `install_path`) and exports
`CRS_PORT_<NAME>` for each port declared under the app in
`config/apps.yaml`.

These templates give every app the same contract: consistent script
names, pid/log handling, and the project-wide override precedence
**command line > environment > config file > default**.

## Files

| file | purpose |
|---|---|
| `start-mu2edaq-APP.sh` | start template — daemonizes the app, writes a pid file |
| `stop-mu2edaq-APP.sh`  | stop template — SIGTERM then SIGKILL after a timeout |
| `start-mu2edaq-APP.1`  | man page for the start script |
| `stop-mu2edaq-APP.1`   | man page for the stop script |

## Adopting in an app repo

1. Copy `start-mu2edaq-APP.sh` and `stop-mu2edaq-APP.sh` into the app
   repo and rename `APP` to the app id, e.g. `start-mu2edaq-dashboard.sh`.
2. In **both** scripts set `APP_ID` (must match the `id:` in this
   project's `config/apps.yaml`) and `APP_DESC`.
3. In the start script:
   - **EDIT 2** — list the app's ports in `PORT_SPEC`, one `NAME DEFAULT`
     per line (names must match the keys under the app's `ports:` in
     `apps.yaml`; `crs-app` exports them upper-cased as `CRS_PORT_<NAME>`).
     Leave the list empty if the app has no ports.
   - **EDIT 3** — set `CMD` to the app's real entry point, referencing
     ports via the exported `CRS_PORT_<NAME>` variables.
4. `chmod +x` both scripts and commit them.
5. Copy the `.1` man pages, rename to match, and install them into the
   app repo's `man/man1/`.
6. (Transition) keep any old script name as a symlink for one release.

## Contract / conventions

- **Port precedence:** `--port NAME=VALUE` > `CRS_PORT_<NAME>` env >
  `--config FILE` > built-in default.
- **Pid file:** `$CRS_HOME/run/<app-id>.pid` (`CRS_HOME` defaults to
  `~/controlroom`; override the run dir with `CRS_RUN_DIR`).
- **Logs:** `$CRS_HOME/log/<app-id>.log` (override with `CRS_LOG_DIR`).
- **Idempotent:** start is a no-op if already running; stop is a no-op if
  not running (and cleans up a stale pid file).
- **Foreground mode:** `--foreground` execs the app instead of
  daemonizing, for use under a supervisor or while debugging.
- **Portable to bash 3.2** (the system bash on macOS) — no associative
  arrays — so the scripts behave the same on the Linux DAQ hosts and on a
  developer's Mac.

## Verify before committing

```bash
bash -n start-mu2edaq-<app>.sh stop-mu2edaq-<app>.sh   # syntax
shellcheck start-mu2edaq-<app>.sh stop-mu2edaq-<app>.sh # optional, if installed
man ./man/man1/start-mu2edaq-<app>.1                    # renders cleanly
```

The corresponding per-repo work is tracked by the "Standardize start/stop
scripts" issues filed in each application repository under the
[Mu2e organization](https://github.com/Mu2e).
