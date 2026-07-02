# Mu2e DAQ Control Room Setup Usage

This guide describes the current state of `mu2edaq-controlroom-setup` and how to use it from an operator or maintainer workstation.

## What This Project Provides

The project manages shared VNC control-room desktops on DAQ hosts and the SSH tunnels needed to reach them from outside the cluster. It also installs small host-side helper scripts that start VNC, publish VNC sessions through `mu2edaq-discovery`, and generate XFCE desktop launchers for DAQ applications.

Main components:

- `crs-remote`: runs setup and VNC lifecycle commands on DAQ hosts over SSH.
- `crs-tunnel`: opens, closes, checks, and connects to local SSH tunnels for VNC sessions.
- `crs-gui`: PyQt6 GUI for tunnel management and service discovery.
- `server/`: scripts copied to the shared DAQ accounts by `crs-remote install`.
- `config/controlroom.yaml`: source of truth for configured VNC sessions.
- `config/apps.yaml`: source of truth for app launchers, app ports, and app start/stop script names.

## Current Configured Sessions

As of the current repository state, `config/controlroom.yaml` defines three VNC sessions, all on `mu2e-mgr-01.fnal.gov`:

| Session | Account | Display | VNC port | Local tunnel port | Geometry |
|---|---|---:|---:|---:|---|
| `dcs-main` | `mu2edcs` | `:1` | `5901` | `5951` | `1920x1080` |
| `shift-main` | `mu2eshift` | `:2` | `5902` | `5952` | `1920x1080` |
| `trig-main` | `mu2etrig` | `:3` | `5903` | `5953` | `1920x1080` |

VNC servers are started with `-localhost yes`, so they are only reachable through SSH tunnels. The tunnel login uses `personal_user` from `controlroom.yaml` when configured, while the remote VNC lifecycle commands run as the shared session accounts.

Note: `config/apps.yaml` still contains application assignments for older session names such as `daq-main`, `daq-aux`, `daq-dl2`, and `shift-aux`. Those entries remain in the app inventory, but desktop launcher provisioning only writes launchers for sessions selected from `controlroom.yaml`. With the current three-session config, only apps assigned to `shift-main`, `dcs-main`, or `trig-main` can be provisioned onto active desktops.

## Prerequisites

On the client machine:

- Python 3.9 or newer.
- Kerberos credentials that can reach the FNAL gateway and DAQ hosts.
- SSH access through `mu2egateway01.fnal.gov`, unless `CRS_GATEWAY` or config overrides it.
- A VNC client:
  - macOS uses `open vnc://localhost:PORT` by default.
  - Other platforms need `vncviewer`, for example TigerVNC.

On the DAQ hosts/session accounts:

- `vncserver`.
- `startxfce4`.
- Python 3 for host-side helper scripts.
- The relevant DAQ application checkouts under the `install_path` values in `config/apps.yaml` if desktop app launchers should work.

## Client Installation

From the repository root:

```bash
./bootstrap.sh
```

This creates `venv/`, installs the package in editable mode with GUI and test extras, and installs sibling `../mu2edaq-discovery` if that checkout exists.

After bootstrap, the main commands are:

```bash
venv/bin/crs-remote
venv/bin/crs-tunnel
venv/bin/crs-gui
```

## First-Time Remote Host Setup

Get a Kerberos ticket first:

```bash
kinit
```

Install the host-side payload to every configured shared account:

```bash
venv/bin/crs-remote install --all
```

This sends the files from `server/` plus `config/controlroom.yaml` and `config/apps.yaml` to each selected account. On the remote side, `install-controlroom.sh` creates:

```text
~/controlroom/bin
~/controlroom/etc
~/controlroom/log
~/.crs
```

It also installs a PATH stanza in `~/.bash_profile` and symlinks app start/stop scripts into `~/controlroom/bin` when the app checkout exists.

Then generate desktop launchers:

```bash
venv/bin/crs-remote provision --all
```

Provisioning calls `~/controlroom/bin/crs-provision-desktop --session <name>` for each configured session. The launchers call:

```bash
~/controlroom/bin/crs-app start <app-id>
~/controlroom/bin/crs-app stop <app-id>
```

## Daily Operation

Start every configured VNC session and open every tunnel:

```bash
bin/start-controlroom.sh
```

Connect to one session:

```bash
venv/bin/crs-tunnel connect --session shift-main
```

Check tunnel state:

```bash
venv/bin/crs-tunnel status
```

Check remote VNC state:

```bash
venv/bin/crs-remote status --all
```

Stop everything:

```bash
bin/stop-controlroom.sh
```

The wrapper scripts are convenience commands. The equivalent explicit startup is:

```bash
venv/bin/crs-remote start --all
venv/bin/crs-tunnel open --all
```

The equivalent explicit shutdown is:

```bash
venv/bin/crs-tunnel close --all
venv/bin/crs-remote stop --all
```

## Selecting Targets

Both `crs-remote` and `crs-tunnel` use the same target selectors:

```bash
--session NAME   one configured session
--host HOST      all sessions on a host
--all            every configured session
```

Examples:

```bash
venv/bin/crs-remote start --session dcs-main
venv/bin/crs-tunnel open --host mu2e-mgr-01.fnal.gov
venv/bin/crs-tunnel close --all
```

For `status`, omitting a selector defaults to `--all`.

## Command Reference

### `crs-remote`

```bash
venv/bin/crs-remote start --session NAME
venv/bin/crs-remote stop --session NAME
venv/bin/crs-remote status --all
venv/bin/crs-remote install --all
venv/bin/crs-remote provision --all
```

Remote commands use SSH with GSSAPI authentication and ProxyJump through the configured gateway. The lifecycle commands call scripts in `~/controlroom/bin` on the session account:

- `start-vnc-session.sh <session> <display> -g <geometry> -d <depth>`
- `stop-vnc-session.sh <session> <display>`
- `status-vnc-session.sh <session> <display>`
- `crs-provision-desktop --session <session>`

`install --all` runs once per unique `(host, account)` pair, not once per display.

### `crs-tunnel`

```bash
venv/bin/crs-tunnel open --session NAME
venv/bin/crs-tunnel close --session NAME
venv/bin/crs-tunnel status
venv/bin/crs-tunnel connect --session NAME
```

Each tunnel is a background SSH master connection with a control socket in `~/.crs`. It forwards:

```text
localhost:<local_port> -> localhost:<5900 + display> on the DAQ host
```

`connect` opens the tunnel if needed and launches a VNC client. Use `--viewer /path/to/vncviewer` to force a specific viewer.

### `crs-gui`

```bash
venv/bin/crs-gui
```

The GUI has:

- A Tunnels tab with per-session Open, Close, and Connect actions.
- A Discovery tab that can scan through the gateway or by local multicast.

In production, use the gateway discovery mode because multicast does not traverse the gateway. Double-clicking a discovered `vnc` row attempts to map it to a configured session, open its tunnel, and attach a viewer.

## Server-Side Tools

These are installed under `~/controlroom/bin` on the DAQ hosts:

- `start-vnc-session.sh`: starts one VNC display and its discovery responder.
- `stop-vnc-session.sh`: stops the discovery responder and VNC display.
- `status-vnc-session.sh`: prints `name|display|port|state|responder`.
- `vnc-discovery-responder.py`: answers discovery queries for a VNC session.
- `crs-app`: dispatches application start/stop scripts with configured port environment variables.
- `crs-provision-desktop`: writes XFCE `.desktop` launchers.

The installed VNC startup file is `~/controlroom/etc/xstartup`, which sets `~/controlroom/bin` in `PATH` and starts XFCE with `startxfce4`.

## Application Launchers And Ports

`config/apps.yaml` defines each application:

- `id`: app id used by `crs-app`.
- `start` and `stop`: standardized script names.
- `install_path`: where the app checkout is expected on DAQ hosts.
- `ports`: named port assignments.
- `sessions`: sessions that should receive desktop icons.
- `desktop`: icon and terminal behavior.

When a launcher runs `crs-app start <app-id>`, `crs-app` exports each configured port as:

```text
CRS_PORT_<NAME>
```

For example, `ports: {http: 8080}` becomes `CRS_PORT_HTTP=8080`.

`crs-app list` can be run on a configured host account to inspect known apps:

```bash
~/controlroom/bin/crs-app list
```

## Configuration Overrides

Configuration precedence is:

```text
command line > environment > YAML config > built-in defaults
```

Useful environment variables:

- `CRS_CONFIG`: alternate `controlroom.yaml`.
- `CRS_APPS_CONFIG`: alternate `apps.yaml`.
- `CRS_GATEWAY`: override the SSH ProxyJump host.
- `CRS_INSTALL_DIR`: override the remote install directory.
- `CRS_GEOMETRY`: default geometry for direct server-side VNC starts.
- `CRS_DEPTH`: default VNC color depth for direct server-side VNC starts.
- `CRS_ANNOUNCE_INTERVAL`: discovery responder announcement interval.

Most normal operation should use the checked-in config files rather than ad hoc environment overrides.

## Troubleshooting

No Kerberos ticket:

```bash
klist -s || kinit
```

Tunnel status says closed after a failed run:

```bash
venv/bin/crs-tunnel status
venv/bin/crs-tunnel open --session shift-main
```

The tunnel manager removes stale control sockets when `ssh -O check` fails.

VNC session is not visible:

```bash
venv/bin/crs-remote status --session shift-main
```

If the VNC display is stopped, start it:

```bash
venv/bin/crs-remote start --session shift-main
```

Viewer does not launch:

```bash
venv/bin/crs-tunnel connect --session shift-main --viewer /path/to/vncviewer
```

On macOS, the default path uses the system `open` command with a `vnc://` URL. On other systems, install TigerVNC or another `vncviewer` implementation.

Desktop icons are missing:

```bash
venv/bin/crs-remote provision --session shift-main
```

If icons are still missing for an app, check that the app's `sessions` entry in `config/apps.yaml` includes an active session from `config/controlroom.yaml`, and that its start/stop scripts exist under the configured `install_path`.

Discovery scan fails in the GUI:

- Confirm the selected remote target is reachable with Kerberos SSH.
- Confirm `mu2edaq-discover --json` is available on the remote target, either in `~/controlroom/bin` or on `PATH`.
- Use gateway mode for production scans.

## Verification

Run the test suite from the repository root:

```bash
venv/bin/pytest
```

The tests cover configuration validation, tunnel command construction, viewer launch behavior, remote install payloads, and desktop launcher generation.
