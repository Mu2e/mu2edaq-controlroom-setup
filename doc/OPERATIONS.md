---
title: mu2edaq-controlroom-setup operations
group: control-room
tier: A
audience: runco
summary: >
  What runs where, its state files and logs, how to check it, and how to
  recover it, for the control-room VNC sessions, their discovery sidecars
  and the operator-side ssh tunnels
---

# mu2edaq-controlroom-setup — operations

The command-by-command operator guide is [usage.md](usage.md); this page is
the run-book: process inventory, state, health checks, known failure modes
and recovery. Interfaces are in [INTERFACES.md](INTERFACES.md).

## 1. What runs, where, as whom

| Process | Host | Account | Started by | Lifetime | State |
|---|---|---|---|---|---|
| `Xvnc :N` (TigerVNC) + XFCE | session host (`mu2e-mgr-01` as configured) | session account (`mu2edcs`, `mu2eshift`, `mu2etrig`) | `start-vnc-session.sh` via `crs-remote start` | until `vncserver -kill` | `~/.vnc/<host>:N.pid`, `~/controlroom/log/vnc-<name>.log` |
| `vnc-discovery-responder.py` | same | same | `start-vnc-session.sh:58`, `nohup python3` (system interpreter) | until SIGTERM, or until its thread dies | `~/.crs/vnc-responder-:N.pid`, `~/controlroom/log/vnc-responder-<name>.log` |
| ssh master per tunnel (`ssh -f -N -M`) | operator machine | operator | `crs-tunnel open`/`connect`, `crs-gui` | until `crs-tunnel close`, network loss, or logout | `~/.crs/ssh-ctrl-<shorthost>-<lport>` |
| DAQ application | session host | session account | desktop launcher → `crs-app start <id>` → app's start script | app-defined | app-defined pid/log (see each app's OPERATIONS.md) |

Nothing here is a systemd unit and nothing restarts automatically. A host
reboot leaves every session, sidecar and application down until someone
runs `crs-remote start` and relaunches the applications.

Ports: VNC `5900+N`/tcp on loopback of the session host; tunnel listeners
`5951–5953`/tcp on loopback of the operator machine; sidecar
`28999`/udp on all interfaces of the session host (multicast group
`239.255.42.99`).

## 2. Prerequisites, once per account

1. A Kerberos ticket in the default cache whose principal the target
   accounts accept (`klist -s` must succeed; every `crs-*` ssh is
   GSSAPI-only): tunnels log in as `personal_user`, `crs-remote` as the
   session's shared account (§4.2). `kinit <you>@FNAL.GOV` is the normal
   choice. Do **not** follow the hint printed by `crs-tunnel`/`crs-remote`
   (`sshutil.py:22`) to run `mu2edaq-controlroom/mu2e-krb-cron.py`: when the
   default cache holds a principal outside its allow-list (any personal
   principal) it runs `kdestroy` and replaces it with the service
   principals, after which the tunnels — which log in as `personal_user` —
   fail (CRS-008).
2. The jump-host login comes from your `ssh_config`, not from this tool.
   `anorman@mu2egateway01` is refused (no such account) while
   `mu2edaq@mu2egateway01` works (established 2026-09-18), so a
   `Host mu2egateway01*` block with a working `User` is required.
3. A VNC password in each session account: `~/.vnc/passwd` must exist
   before the first `crs-remote start`, because `vncserver` prompts for one
   otherwise and `crs-remote` runs with `BatchMode=yes` and no tty.
   ```bash
   ssh -J mu2egateway01.fnal.gov mu2eshift@mu2e-mgr-01.fnal.gov vncpasswd
   ```
4. `crs-remote install --all`, then `crs-remote provision --all`.

## 3. Health checks

```bash
venv/bin/crs-tunnel status                 # client: open|closed per session
venv/bin/crs-remote status                 # host: NAME|:N|PORT|running|stopped|alive|dead|none
```

Read the `status-vnc-session.sh` line as:

| Field 4 | Field 5 | Meaning | Action |
|---|---|---|---|
| running | alive | healthy | — |
| running | dead | sidecar exited; session invisible to discovery | §4.3 |
| running | none | started without the sidecar, or by something other than this tool | check §3.1 |
| stopped | dead/none | session down | `crs-remote start --session NAME` |

### 3.1 Is VNC really loopback-only?

The only enforcement is the `-localhost yes` argument this package passes
(`start-vnc-session.sh:51`). A session started any other way is not
covered. On the session host:

```bash
ss -ltnp 'sport = :5901'      # Local Address must be 127.0.0.1:5901 or [::1]:5901
```

Anything else (`0.0.0.0`, `*`, a routable address) means the VNC password
is the only protection on the network: stop that session and restart it
with `crs-remote start`.

### 3.2 Which discovery implementation is the sidecar running?

```bash
ssh -J mu2egateway01.fnal.gov mu2eshift@mu2e-mgr-01.fnal.gov \
    "python3 -c 'import mu2edaq_discovery, sys; print(mu2edaq_discovery.__file__)'"
```

An `ImportError` means the embedded fallback is in use; it replies to some
malformed queries and dies on others (CRS-004, INTERFACES §7).

### 3.3 Is the session discoverable?

From any host on the DAQ subnet that has `mu2edaq-discovery` installed:

```bash
mu2edaq-discover --filter app=vnc
```

Each configured session should appear once as `VNC <host> :N (<name>)`.
The advertised port is the loopback-only VNC port; a client has to map it
to a configured session and tunnel to it, which is what `crs-gui`'s
Discovery tab does on double-click.

## 4. Failure modes and recovery

### 4.1 A desktop launcher does nothing, or the app fails to find its venv

Cause: CRS-001. `crs-app` runs `~/controlroom/bin/<start-script>`, which
`install-controlroom.sh` created as a symlink; the start script computes
its directory from the unresolved link, looks for `venv/` and `config/` in
`~/controlroom/bin`, and fails. All twelve start scripts `cd "$SCRIPT_DIR"`
and then use paths relative to it (`venv/`, `build/`, `lib/`, the main
`.py`), so none of them starts through a launcher. Stop launchers resolve
the same way: scripts that keep their pid file under `$SCRIPT_DIR` report
"not running" and leave the app up; bigredbox (pid file in `/tmp`) and
controlcenter (`pgrep` fallback) still stop.

Workaround until the fix lands: run the script from its checkout.

```bash
cd ~/mu2edaq-main/mu2edaq-dashboard && CRS_PORT_HTTP=5001 CRS_PORT_ZMQ=5555 ./start-mu2edaq-dashboard.sh
```

`crs-app list` prints each app's ports for the environment line.

### 4.2 `crs-remote` fails with `Permission denied (gssapi-with-mic)`

`crs-remote` logs in as the session's shared account; tunnels log in as
`personal_user`. Commit `da08771` moved the tunnels off the shared
accounts because those accounts on `mu2e-mgr-01` did not accept the
operator's principal (CRS-003). There is no workaround inside this tool:
the fix is an entry for the operator's principal in each shared account's
`~/.k5login` on each session host. Check with

```bash
ssh -J mu2egateway01.fnal.gov -o BatchMode=yes mu2eshift@mu2e-mgr-01.fnal.gov true && echo accepted
```

Note that `crs-tunnel` and `crs-remote` use the same default credential
cache, so one principal must be accepted by both `personal_user` (tunnels)
and every shared account (`crs-remote`).

### 4.3 Sidecar `dead`

The responder thread exited: a bind failure on 28999, or — with the
embedded fallback — a DISCOVER whose `filter` is a JSON list or string.
The process exits 0 either way, so check the log first:

```bash
tail ~/controlroom/log/vnc-responder-<name>.log
```

Restarting only the sidecar is not scripted. Either restart the session
(`crs-remote stop` then `start`, which disconnects every viewer) or start
the sidecar by hand with the arguments `start-vnc-session.sh:58-64` uses:

```bash
nohup python3 ~/controlroom/bin/vnc-discovery-responder.py --name shift-main \
    --display :2 --port 5902 --geometry 1920x1080 \
    >>~/controlroom/log/vnc-responder-shift-main.log 2>&1 &
echo $! > ~/.crs/vnc-responder-:2.pid
```

### 4.4 Tunnel reported closed but the port is busy

`crs-tunnel open` uses `ExitOnForwardFailure=yes`, so a listener left on
the local port by another ssh makes the open fail. Find and stop it:

```bash
lsof -nP -iTCP:5952 -sTCP:LISTEN
```

`crs-tunnel status` deletes a control socket whose `ssh -O check` fails,
so a stale socket alone never blocks a reopen.

### 4.5 Some applications have no launcher

Expected with the shipped configuration: `apps.yaml` assigns eight of the
twelve applications only to sessions that `controlroom.yaml` no longer
defines, and `dcs-main` and `trig-main` are assigned none (CRS-002).
Launchers are never removed when an assignment is dropped; delete stale
`~/Desktop/<id>-{start,stop}.desktop` files by hand.

### 4.6 Every launcher opens a terminal / `--all-local` says no sessions

The host's system `python3` lacks PyYAML, so `crs-provision-desktop` fell
back to `crs-app`'s restricted parser (CRS-014). Install `python3-pyyaml`
on the host, or use `--session NAME`, and re-run provisioning.

## 5. Changes and upgrades

* **Configuration or scripts changed**: edit `config/*.yaml` or `server/*`
  on the operator machine, then `crs-remote install --all` (ships both
  configs and all scripts, re-creates the app symlinks) and
  `crs-remote provision --all`. Running sessions keep their old
  `xstartup` and sidecar until restarted.
* **Moving the install area**: not supported. `CRS_INSTALL_DIR` and
  `install_dir` are parsed and ignored; `crs-remote` always calls
  `~/controlroom/bin`, and the PATH stanza and `xstartup` hard-code it
  (CRS-006).
* **Changing the announce interval**: `discovery.announce_interval` in
  `controlroom.yaml` has no effect. Set `CRS_ANNOUNCE_INTERVAL` in the
  session account's environment before `start-vnc-session.sh` runs.

## 6. Shutdown

```bash
bin/stop-controlroom.sh       # crs-tunnel close --all, then crs-remote stop --all
```

`stop-vnc-session.sh` signals the sidecar first, so the session leaves
discovery before its port closes. Stopping a session disconnects every
operator attached to it and ends every application started from its
desktop that did not daemonize outside the session.
