# mu2edaq-controlroom-setup

Setup and management tooling for the Mu2e DAQ control room: six VNC
viewport sessions on the DAQ cluster, remote orchestration from an
external machine through the FNAL gateway, client-side ssh tunnel
management with a GUI, XFCE desktops with start/stop icons for the DAQ
applications, and integration with the
[mu2edaq-discovery](https://github.com/Mu2e/mu2edaq-discovery) service
discovery protocol.

## Architecture

```
 your machine (Mac/Linux)         mu2egateway01.fnal.gov          DAQ hosts
┌──────────────────────────┐      ┌───────────────┐      ┌──────────────────────────┐
│ crs-remote ──── ssh -J ──┼──────┤   ProxyJump   ├──────┤ ~/controlroom/bin/       │
│ crs-tunnel ──── ssh -L ──┼──────┤  (Kerberos)   ├──────┤   start-vnc-session.sh   │
│ crs-gui (PyQt6)          │      └───────────────┘      │   vncserver :N + XFCE    │
│ vncviewer → localhost:595x                             │   discovery responder    │
└──────────────────────────┘                             └──────────────────────────┘
```

The six sessions (central config: `config/controlroom.yaml`):

| session | host | account | display | geometry | local port |
|---|---|---|---|---|---|
| shift-main | mu2e-mgr-01 | mu2eshift | :1 | 2560x1440 | 5951 |
| shift-aux | mu2e-mgr-01 | mu2eshift | :2 | 1920x1080 | 5952 |
| daq-main | mu2e-dl-01 | mu2edaq | :1 | 2560x1440 | 5953 |
| daq-aux | mu2e-dl-01 | mu2edaq | :2 | 1920x1080 | 5954 |
| daq-dl2 | mu2e-dl-02 | mu2edaq | :1 | 2560x1440 | 5955 |
| dcs-main | mu2e-dcs-01 | mu2edcs | :1 | 2560x1440 | 5956 |

VNC servers listen on `5900+display`, bound to localhost only — the
**only** path in is an ssh tunnel. Each session start also launches a
small discovery responder sidecar so VNC sessions appear in
`mu2edaq-discover` scans (VNC itself has no discovery protocol).

## Install (client machine)

```bash
./bootstrap.sh         # venv + PyQt6 + sibling mu2edaq-discovery
```

Prerequisites: a Kerberos ticket (`kinit`, or the keytab manager in
`mu2edaq-controlroom/mu2e-krb-cron.py`) and a VNC client. On macOS the
built-in Screen Sharing client is used (`open vnc://localhost:PORT`); on
Linux/Windows install TigerVNC's `vncviewer`.

## First-time host setup

```bash
venv/bin/crs-remote install --all      # ships scripts/configs per (host, account)
venv/bin/crs-remote provision --all    # generates desktop icons
```

## Daily operation

```bash
bin/start-controlroom.sh               # start all sessions + open all tunnels
venv/bin/crs-tunnel connect --session daq-main
venv/bin/crs-gui                       # or do everything from the GUI
bin/stop-controlroom.sh                # tear it all down
```

Or piecemeal: `crs-remote {start|stop|status}` and
`crs-tunnel {open|close|status|connect}` with
`--session NAME | --host H | --all`.

## Port assignments

`config/apps.yaml` is the single source of port truth. Desktop icons
run `crs-app start <id>`, which exports `CRS_PORT_<NAME>` for each of
the app's ports and execs its standardized `start-<app>.sh`. Two
deliberate reassignments to remove collisions: heartbeatmonitor HTTP
8080→8081 (resource-manager owns 8080) and trigger-scalers UDP
5555→5557 (dashboard ZMQ owns 5555).

## Configuration precedence

Command line > environment (`CRS_CONFIG`, `CRS_GATEWAY`,
`CRS_INSTALL_DIR`, `CRS_PORT_*`, …) > YAML config > defaults.

## Layout

- `config/` — controlroom.yaml (sessions/gateway/discovery), apps.yaml (app inventory)
- `src/mu2edaq_controlroom_setup/` — Python package (`crs-tunnel`, `crs-remote`, `crs-gui`)
- `server/` — scripts installed onto DAQ hosts (no venv needed there)
- `bin/` — client-side convenience wrappers
- `man/man1/` — man pages for every tool
- `doc/issues/` — draft GitHub issues for per-app standardization and discovery adoption
- `tests/` — pytest suite (`venv/bin/pytest`)

## Tests

```bash
venv/bin/pytest        # 38 tests: config validation, tunnel argv, payload,
                       # .desktop generation via the real server scripts
```
