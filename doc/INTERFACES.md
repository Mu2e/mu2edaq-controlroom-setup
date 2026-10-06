---
title: mu2edaq-controlroom-setup interfaces
group: control-room
tier: A
audience: expert
summary: >
  controlroom.yaml, the ssh/VNC access path and its security boundary,
  the client CLIs, the host-side payload, the apps.yaml sessions
  extension, the start/stop template contract and the VNC discovery
  advertisement exposed by mu2edaq-controlroom-setup
---

# mu2edaq-controlroom-setup — interfaces

| Interface | Kind | Section |
|---|---|---|
| `config/controlroom.yaml` | file format | §1 |
| ssh tunnel and remote-command path | ssh argv, Kerberos | §2 |
| `crs-tunnel`, `crs-remote`, `crs-gui` | client CLI / GUI | §3 |
| host payload in `~/controlroom` | files, scripts, status line format | §4 |
| `apps.yaml` + `sessions:` extension, `crs-app` | file format, exec contract | §5 |
| `templates/start-mu2edaq-APP.sh` | contract pushed into every app | §6 |
| VNC discovery advertisement | mu2edaq-discovery/1 ANNOUNCE | §7 |

---

## 1. `controlroom.yaml`

Path: `--config` > `$CRS_CONFIG` > `./config/controlroom.yaml` relative
to the **current working directory** > `config/controlroom.yaml` in the
package tree (`src/mu2edaq_controlroom_setup/config.py:38-53`). A missing
file is a `ConfigError` (`:57-58`).

| Key | Type | Default | Consumed by | Notes |
|---|---|---|---|---|
| `gateway` | host | `mu2egateway01.fnal.gov` | every ssh as `-J` (`sshutil.py:41-42`) | env `CRS_GATEWAY` overrides (`config.py:62-63`) |
| `personal_user` | string | `$USER` | tunnel login user only (`tunnels.py:31`) | The shipped comment says "login used on the jump host" (`config/controlroom.yaml:5`); the code never applies it to the jump host. See CRS-003 |
| `install_dir` | path | `~/controlroom` | **nothing** | env `CRS_INSTALL_DIR` sets it (`config.py:64-65`); remote paths are hard-coded `~/controlroom/bin` (`remote.py:44,49,54,59`, `gui/discovery_tab.py:51`). CRS-006 |
| `vnc_password_file` | path | `~/.vnc/passwd` | **nothing** | `vncserver` uses its own default |
| `discovery.group` / `.port` / `.timeout` | | `239.255.42.99` / `28999` / `2.0` | GUI local-multicast scan (`gui/discovery_tab.py:41-46`) | |
| `discovery.announce_interval` | int s | 30 | **nothing** | the sidecar reads `CRS_ANNOUNCE_INTERVAL` on the host, which `crs-remote` does not set |
| `accounts` | list | `[]` | **nothing** | informational |
| `sessions[]` | list | `[]` | everything | below |

`sessions[]` entries (`config.py:67-80`, validation `:91-113`):

| Key | Required | Default | Validation |
|---|---|---|---|
| `name` | yes | | unique |
| `host` | yes | | — |
| `account` | yes | | — |
| `display` | yes | | 1–99; unique per host |
| `geometry` | no | `1920x1080` | `^\d{3,5}x\d{3,5}$` |
| `depth` | no | 24 | — |
| `local_port` | no | 0 | unique when non-zero. **0 is accepted** and passed through as `-L 0:localhost:…`; no session in the shipped file omits it |

VNC port = 5900 + `display` (`session.py:5`, `:18-20`).

### 1.1 Two topologies disagree

| Source | Sessions |
|---|---|
| `config/controlroom.yaml:20-41` (what every tool acts on) | `dcs-main` mu2edcs :1→5951, `shift-main` mu2eshift :2→5952, `trig-main` mu2etrig :3→5953 — all on `mu2e-mgr-01.fnal.gov`, 1920x1080 |
| `README.md:23-32` (design, superseded by commit `da08771`, 2026-06-25) | `shift-main` mgr-01 :1→5951, `shift-aux` mgr-01 :2→5952, `daq-main` mu2e-dl-01 :1→5953, `daq-aux` dl-01 :2→5954, `daq-dl2` mu2e-dl-02 :1→5955, `dcs-main` mu2e-dcs-01 :1→5956 |
| `config/apps.yaml` `sessions:` | references `shift-main`, `shift-aux`, `daq-main`, `daq-aux`, `daq-dl2` — only `shift-main` exists in the live config |
| superproject `DAQ-ControlRoom-Instructions.md:34-41`, `DAQ-ControlRoom-Testing.md:188-240` | the six-session README layout; the smoke test's `--session daq-dl2` exits 1 against the shipped config |

`doc/usage.md:18-30` and `doc/index.html:55-70` describe the three-session
state correctly. Which layout the hosts run today was not verified by this
review. Staged as CRS-002.

---

## 2. Access path and security model

### 2.1 What is enforced, and where

```
operator laptop                 mu2egateway01             mu2e-mgr-01
127.0.0.1:595N  --ssh -L-->  [ProxyJump -J, no shell]  --> sshd --> 127.0.0.1:590N  Xvnc
```

| Property | Enforced at | Mechanism |
|---|---|---|
| VNC accepts only loopback | `server/start-vnc-session.sh:51` | `vncserver … -localhost yes` — only for sessions this script starts; a systemd `vncserver@` unit or a hand-started server follows the host's TigerVNC config. Not verified on the live hosts |
| Only path in from off-host is ssh | consequence of the line above | the `-L` far end `localhost:590N` is resolved **on the session host** (`sshutil.py:59`) |
| ssh reaches the DAQ network only via the gateway | `sshutil.py:41-42` | `-J <gateway>` on every ssh |
| Authentication | `sshutil.py:36-38`, `:16-24` | GSSAPI (Kerberos) only; `klist -s` preflight |
| Local tunnel endpoint is loopback | ssh default only | `-L LPORT:localhost:VPORT` has no bind address; a client `GatewayPorts yes` would expose the forwarded VNC port on the operator's LAN |
| Who may view a session | VNC password | any account able to ssh to `mu2e-mgr-01` can reach every session's loopback port — the tunnel itself logs in as `personal_user`, not the session account, by design (`tunnels.py:22-32`) — so the per-session gate is the VncAuth password in each account's `~/.vnc/passwd` |

So the model holds: the network-reachable surface is sshd on the gateway
and on the session host; VNC is never exposed. Two weaknesses, staged as
CRS-007: every connection sets `GSSAPIDelegateCredentials=yes`, which for
`crs-remote` deposits the operator's TGT into a cache owned by a **shared**
account for the life of the ssh session; and the local `-L` endpoint is not
pinned to `127.0.0.1`.

### 2.2 Login identities

| Operation | ssh login | Evidence |
|---|---|---|
| jump hop | from the client's `ssh_config`, else the local user name | `sshutil.py:42` passes `-J host` with no user |
| `crs-tunnel` forward | `personal_user@host`, fallback `account@host` | `tunnels.py:31-32` |
| `crs-remote start/stop/status/install/provision` | `account@host` (shared) | `remote.py:46,51,56,60,86` via `session.target` |
| GUI gateway discovery scan | `account@host` (shared) | `gui/discovery_tab.py:89-93` |

Commit `da08771` moved tunnels off the shared accounts because they
returned "Permission denied (gssapi-with-mic)" for the operator's
principal. `crs-remote` still needs the shared account — the VNC server
and `~/controlroom` belong to it — so it works only if each shared
account's `.k5login` lists the operator. The commit recorded that, on
`mu2e-mgr-01`, `mu2edcs`, `mu2eshift` and `mu2etrig` did not; unless that
has changed since, every `crs-remote` subcommand fails there with the
same `Permission denied (gssapi-with-mic)` the tunnels hit. Separately, an established access
fact (2026-09-18) is that `anorman@mu2egateway01` is refused (no such
account) while `mu2edaq@mu2egateway01` succeeds; the tools therefore
depend on the client's `ssh_config` naming a jump user. CRS-003.

### 2.3 ssh argv

```
tunnel open : ssh -o GSSAPIAuthentication=yes -o GSSAPIDelegateCredentials=yes [-F CFG] -J GW
                  -f -N -M -S ~/.crs/ssh-ctrl-<short>-<lport> -o ExitOnForwardFailure=yes
                  -L <lport>:localhost:<5900+display> <personal_user>@<host>
tunnel check: ssh -S <sock> -O check <user>@<host>
tunnel close: ssh -S <sock> -O exit  <user>@<host>
remote cmd  : ssh -o GSSAPI… [-F CFG] -J GW -o BatchMode=yes <account>@<host> '<cmd>'
```

(`sshutil.py:34-71`.) The control socket lives in `~/.crs`, not `/tmp`
(`sshutil.py:27-31`), keyed by host short name and local port.

---

## 3. Client commands

| Command | Synopsis | Exit | Page |
|---|---|---|---|
| `crs-tunnel` | `{open,close,status,connect} [--session N\|--host H\|--all] [--config F] [--ssh-config F] [--viewer BIN]` | 0; 1 config/selection/Kerberos/ssh error; 2 argparse | `crs-tunnel(1)` |
| `crs-remote` | `{start,stop,status,install,provision} [--session N\|--host H\|--all] [--config F] [--ssh-config F]` | 0 iff every remote command exited 0 | `crs-remote(1)` |
| `crs-gui` | `[--config F]` | Qt exit code; 1 after config error | `crs-gui(1)` |
| `bin/start-controlroom.sh`, `bin/stop-controlroom.sh` | none | `set -e` | own pages |

`status` defaults to `--all` in both CLIs (`cli.py:48-49`, `:95-96`); every
other command needs a target (`remote.py:96-109`). `install` collapses to
one run per (host, account) (`cli.py:100-104`). `--host` matches FQDN or
short name (`session.py:50-52`).

---

## 4. Host payload

`crs-remote install` streams an in-memory `tar.gz` of
`server/{start,stop,status}-vnc-session.sh, vnc-discovery-responder.py,
crs-app, crs-provision-desktop, xstartup, install-controlroom.sh}` plus both
config files (`remote.py:20-24`, `:64-78`) and runs, as the session account,

```
rm -rf ~/.crs-payload && mkdir -p ~/.crs-payload && tar xzf - -C ~/.crs-payload --strip-components=1
  && bash ~/.crs-payload/install-controlroom.sh && rm -rf ~/.crs-payload
```

(`remote.py:84-92`). Resulting layout:

| Path | Content |
|---|---|
| `~/controlroom/bin/` | the six scripts (0755) **and a symlink per app start/stop script** whose checkout exists (`install-controlroom.sh:56-95`) |
| `~/controlroom/etc/` | `controlroom.yaml`, `apps.yaml` (0644), `xstartup` (0755) |
| `~/controlroom/log/` | `vnc-<name>.log`, `vnc-responder-<name>.log` |
| `~/.crs/` | `vnc-responder-:N.pid` |
| `~/.bash_profile` | marker-guarded `PATH=$HOME/controlroom/bin:$PATH` |

Nothing in the payload installs `mu2edaq-discovery` (CRS-004).

`status-vnc-session.sh` output, one line per queried display
(`server/status-vnc-session.sh:5-7`, `:39`):

```
<name>|:<display>|<5900+display>|running|stopped|alive|dead|none
         field 4: running|stopped     field 5: alive|dead|none
```

---

## 5. `apps.yaml`, `sessions:` and `crs-app`

The schema is documented authoritatively in
[`mu2edaq-desktop/docs/INTERFACES.md` §1](../../mu2edaq-desktop/docs/INTERFACES.md)
and `apps.yaml(5)` (shipped in mu2edaq-desktop). This package's copy is
identical in every shared field and adds:

- `sessions: [<session-name>, …]` — consumed only by
  `crs-provision-desktop` (`server/crs-provision-desktop:67-75`). Names are
  not validated against `controlroom.yaml`; an unknown name silently
  produces no launcher. With the shipped files eight of twelve apps have no
  defined session (dashboard, diskwatcher, fts, heartbeatmonitor,
  resource-manager, runlog-db, dataformat-viewer, cfocontrol);
  `shift-main` gets four (controlcenter, bigredbox, downtime-logger,
  trigger-scalers) and `dcs-main`/`trig-main` receive no launchers at all.

**PyYAML-free fallback.** `crs-app`, `crs-provision-desktop` and step 5 of
`install-controlroom.sh` use PyYAML when the host's system `python3` has
it, else `crs-app`'s `_tiny_yaml` (`server/crs-app:31-67`). That parser
returns `{"apps": [...]}` for any file and does not convert booleans.
Measured against the shipped files: for `apps.yaml` it differs from PyYAML
only in `desktop.terminal`, which comes back as the string `"false"` — and
`bool("false")` is true (`server/crs-provision-desktop:76`), so every
launcher is written `Terminal=true`; for `controlroom.yaml` it returns no
`sessions` key, so `crs-provision-desktop --all-local` always exits 1.
CRS-014.

`crs-app` versus desktop's `mu2edaq-app`: compared row by row in
`mu2edaq-desktop/docs/INTERFACES.md` §2.1. The port export is identical;
script resolution and execution model differ. The consequential difference
for this package: `crs-app` prefers `~/controlroom/bin/<script>`
(`server/crs-app:70-75`), which `install-controlroom.sh:85-90` creates as a
**symlink**; all twelve adopted start scripts compute
`SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`, which through
the link is `~/controlroom/bin`, so they look for `venv/` and `config/`
there and fail. Reproduced in a scratch directory with `os.execve` on a
link. CRS-001 (S2).

---

## 6. Start/stop template contract

`templates/start-mu2edaq-APP.sh` and `stop-mu2edaq-APP.sh` (with man-page
templates) were pushed into every app repository by the eleven
`doc/issues/0[1-9]-*`, `10-*`, `11-*` tickets. The contract:

| Element | Template value |
|---|---|
| Names | `start-mu2edaq-<app>.sh`, `stop-mu2edaq-<app>.sh` |
| Ports | `PORT_SPEC` lines `NAME DEFAULT`; exports `CRS_PORT_<NAME>` |
| Pid / log | `$CRS_HOME/run/<id>.pid`, `$CRS_HOME/log/<id>.log` |
| Idempotence | start no-op if pid alive; stop no-op if no pid |
| Stop | SIGTERM, SIGKILL after `CRS_STOP_TIMEOUT` (10 s) |
| Foreground | `--foreground` execs |
| Precedence (documented, `:15-21`) | `--port` > `CRS_PORT_<NAME>` > `--config FILE` > default |
| Precedence (actual) | `--port` > **`--config FILE`** > `CRS_PORT_<NAME>` > default |

The config file is `source`d with `set -a` after the environment is
inherited (`:99-103`), so a `CRS_PORT_HTTP=` line in it overwrites the
value `crs-app` exported. Verified: env 5001 + config 9999 → `HTTP=9999`.
CRS-005, S4 because no adopted start script carries the template's config
layer (`grep -l 'CRS_APP_CONFIG\|PORT_SPEC\|set -a' ../*/start-mu2edaq-*.sh`
matches nothing), so the inversion is latent. Adopters diverged from the template in practice: no adopted
start script uses `$CRS_HOME/run`; most key their pid file off
`$SCRIPT_DIR` (`grep -h PID_FILE= ../*/start-mu2edaq-*.sh`), which under
the symlink path of §5 is `~/controlroom/bin`. The template documents
intent more than the deployed reality.

---

## 7. Discovery advertisement (VNC sidecar)

`server/start-vnc-session.sh:56-66` starts
`server/vnc-discovery-responder.py` with **bare `python3`**, outside any
virtual environment. This is the suite's only system-interpreter Python
discovery sidecar (CONTRACT §9.4); the wire protocol is defined in
[`mu2edaq-discovery/doc/INTERFACES.md`](../../mu2edaq-discovery/doc/INTERFACES.md).

| ANNOUNCE field | Value | Evidence |
|---|---|---|
| `name` | `VNC <nodename> :<N> (<session>)` | `:154` |
| `app`, `scheme` | `vnc` | `:155` |
| `port` | 5900+N, int | `:155` |
| `version` | `"1.0"` | `:155` |
| `meta` | `{"display": ":N", "account": "<user>", "geometry": "WxH"}` — **all strings**, as CONTRACT §9.5 requires | `:149-151` |
| unsolicited announce | every `CRS_ANNOUNCE_INTERVAL` s, default **30** | `start-vnc-session.sh:15`, `:63` |

The last row contradicts `mu2edaq-discovery/doc/INTERFACES.md` §1.4 ("No
package in the suite currently enables it"): every VNC sidecar multicasts
an unsolicited ANNOUNCE every 30 s by default.

**Deployment constraint.** Which implementation runs depends on whether
`import mu2edaq_discovery` succeeds in the host's system `python3`
(`:23-25`). Nothing in this package arranges that: `install-controlroom.sh`
installs no Python package and `bootstrap.sh` installs the sibling only into
the *client* venv. When it fails, the embedded fallback (`:26-132`) runs.
Measured differences from the reference responder (CONTRACT §9.5,
discovery INTERFACES §1.8):

| DISCOVER | reference (Python) | fallback |
|---|---|---|
| `filter: []` | silent | **replies** |
| `qid` absent or non-string | silent | **replies** |
| `filter` key outside app/name/host | silent | silent |
| `filter: ["x"]` or `filter: "x"` | silent | **`AttributeError` in the receive loop → thread dies → process exits 0** |
| oversize ANNOUNCE | raises (thread dies, discovery #8) | not checked; unreachable with these fields |

Reproduced on 2026-10-06 by loading the sidecar file without
`mu2edaq_discovery` on the path and sending each DISCOVER above to its
socket: the list- and string-`filter` cases left the thread dead.
A single malformed datagram from anywhere on the subnet therefore removes
that VNC session from discovery until the session is restarted. The
fallback also omits `IP_MULTICAST_IF` on its send socket (reference
`mu2edaq-discovery/src/mu2edaq_discovery/responder.py:92-95`), so on a multi-homed host the unsolicited ANNOUNCE
leaves by the default-route interface. The protocol duplication itself is
staged once, in `mu2edaq-discovery` (DISC-015, `f36464fd`). The GUI's
gateway scan has the same dependency in another form: it runs
`mu2edaq-discover --json` on the host (`gui/discovery_tab.py:49-53`), which
nothing installs. CRS-004.
