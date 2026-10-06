# Staged issues — mu2edaq-controlroom-setup

GitHub writes are not permitted in this review wave (CONTRACT §9.1). Each
section below is one issue body in the §6 format, fingerprint included.
Target repository for all of them: `Mu2e/mu2edaq-controlroom-setup`
(public, issues enabled). Label: `mega-review` plus the category.

Dedup read, 2026-10-06:

```
$ gh issue list -R Mu2e/mu2edaq-controlroom-setup --state all --limit 300
#4 OPEN  requirements.txt and pyproject.toml disagree about PyQt6
```

No fingerprint present. #4 shares no significant title tokens with any
finding below and is not re-filed.

Cross-package findings staged elsewhere and only referenced here:
`mu2edaq-desktop` DESK-001 (`8c3c7ace`, inventory hand-copied),
DESK-002 (`de6e3b61`, `mu2edaq-app` blocks on captured stdout);
`mu2edaq-discovery` DISC-015 (`f36464fd`, four implementations of the wire
format, including this package's fallback); `mu2edaq-controlroom` CR-002
(the cron that destroys personal tickets, referenced by CRS-008).

| ID | Sev | Category | Title | Fingerprint |
|---|---|---|---|---|
| CRS-001 | S2 | bug | [launch] crs-app execs the ~/controlroom/bin symlink, so every adopted start script resolves SCRIPT_DIR to the bin area and fails | 6b03e34b |
| CRS-002 | S3 | bug | [config] session topology disagrees between controlroom.yaml, README/runbooks and apps.yaml; 8 of 12 apps get no launcher | f6599080 |
| CRS-003 | S3 | bug | [ssh] crs-remote and the GUI gateway scan log in as shared accounts that refuse the operator's principal | 1ceb25cd |
| CRS-004 | S3 | bug | [discovery] VNC sidecar runs under system python3 with nothing installing mu2edaq-discovery; the embedded fallback dies on a malformed DISCOVER | 27f73a63 |
| CRS-005 | S4 | bug | [template] start template sources --config after the environment, inverting its documented port precedence | 5eae41a4 |
| CRS-006 | S3 | bug | [config] install_dir, CRS_INSTALL_DIR, vnc_password_file, accounts and discovery.announce_interval are parsed and never used | 8acd9bdd |
| CRS-007 | S3 | enhancement | [ssh] credentials are delegated into shared accounts and the local forward is not pinned to loopback | fb7108a1 |
| CRS-008 | S3 | documentation | [docs] the no-ticket hint sends operators to mu2e-krb-cron.py, which destroys a personal ticket | f73dfcd7 |
| CRS-009 | S3 | enhancement | [ci] no CI workflow for a 43-test suite | c5bcbf9b |
| CRS-010 | S4 | bug | [gui] Discovery-tab double-click opens the ssh tunnel on the UI thread | 638fc580 |
| CRS-011 | S4 | bug | [packaging] pyproject.toml declares BSD-3-Clause while LICENSE is MIT | 23ae1ad1 |
| CRS-012 | S4 | documentation | [docs] doc/issues/README.md calls the 22 filed and closed tickets drafts; README test count is stale | 19e3ea39 |
| CRS-013 | S4 | documentation | [man] man pages were misnamed, unversioned and missing for six executables | 3433011d |
| CRS-014 | S4 | bug | [host] the PyYAML-free fallback parser breaks --all-local and writes Terminal=true on every launcher | a3ca8c30 |

---

## CRS-001 — [launch] crs-app execs the ~/controlroom/bin symlink, so every adopted start script resolves SCRIPT_DIR to the bin area and fails

**Severity:** S2 — production breakage or silent wrong behaviour; workaround exists
**Category:** bug
**Location:** `server/crs-app:70-75`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`install-controlroom.sh` replaces `~/controlroom/bin/<start|stop script>`
with a symbolic link into each app's checkout, and `crs-app` prefers that
path and `execve`s it. Every one of the twelve adopted start scripts
computes its own directory with `dirname "${BASH_SOURCE[0]}"` without
resolving links, then `cd`s there and uses relative paths, so through the
link it looks for `venv/`, `build/`, `config/` and its entry point in
`~/controlroom/bin` and fails. No desktop launcher can start its app.

## Evidence
```
$ sed -n 70,75p server/crs-app
def _find_script(app, which):
    script = app[which]
    crs_bin = os.path.expanduser(os.path.join(
        os.environ.get("CRS_HOME", "~/controlroom"), "bin", script))
    if os.access(crs_bin, os.X_OK):
        return crs_bin
$ sed -n 85,90p server/install-controlroom.sh
        src = os.path.join(install, script)
        dst = os.path.join(crs_home, "bin", script)
        if os.path.exists(src):
            if os.path.islink(dst) or os.path.exists(dst):
                os.remove(dst)
            os.symlink(src, dst)
$ grep -h 'SCRIPT_DIR=' ../mu2edaq-*/start-mu2edaq-*.sh | sort | uniq -c
  12 SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# reproduction: checkout/start-x.sh prints SCRIPT_DIR; bin/start-x.sh -> checkout/start-x.sh
$ python3 -c 'import os,sys; p=sys.argv[1]; os.execve(p,[p],dict(os.environ))' $S/bin/start-x.sh
SCRIPT_DIR=.../link2/bin
```
Stop launchers resolve the same way; those keeping their pid file under
`$SCRIPT_DIR` report "not running" and leave the app up.

## Why it matters
The desktop launchers are the control room's start/stop interface for
shifters. Through them every app fails to start, and most fail to stop.
The workaround — run the script from its checkout — is not discoverable
from the desktop.

## Suggested fix
In `crs-app`, resolve the script before exec (`os.path.realpath`) or
prefer `install_path/<script>` and keep the symlink only for PATH
convenience. Defensively, have the template and the adopted scripts use
`SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"`
(GNU `readlink -f`; add a fallback for macOS bash 3.2). Add a test that
execs a start script through a link in a temp `CRS_HOME`.

## Related
- `mu2edaq-desktop` DESK-002 (the other launcher's defect)

<!-- mega-review-fingerprint: 6b03e34b -->

---

## CRS-002 — [config] session topology disagrees between controlroom.yaml, README/runbooks and apps.yaml; 8 of 12 apps get no launcher

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `config/controlroom.yaml:20-41`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
Three sources describe the VNC sessions differently and nothing reconciles
them. `controlroom.yaml` (what every tool acts on) defines three sessions
on `mu2e-mgr-01`: `dcs-main` :1, `shift-main` :2, `trig-main` :3 (commit
`da08771`). `README.md:23-32` and the superproject's
`DAQ-ControlRoom-Instructions.md:34-41` and `DAQ-ControlRoom-Testing.md`
document six sessions on four hosts. `apps.yaml` assigns apps to the
six-session names, which `crs-provision-desktop` does not validate.

## Evidence
```
$ python3 - <<'EOF'   # shipped config/apps.yaml against config/controlroom.yaml
12 apps; 8 with no defined session: ['dashboard', 'diskwatcher', 'fts', 'heartbeatmonitor',
  'resource-manager', 'runlog-db', 'dataformat-viewer', 'cfocontrol']
per session: {'dcs-main': [], 'shift-main': ['controlcenter', 'bigredbox',
  'downtime-logger', 'trigger-scalers'], 'trig-main': []}
undefined names referenced: ['daq-aux', 'daq-dl2', 'daq-main', 'shift-aux']
EOF
$ sed -n 27,32p README.md
| shift-main | mu2e-mgr-01 | mu2eshift | :1 | 2560x1440 | 5951 |
| shift-aux | mu2e-mgr-01 | mu2eshift | :2 | 1920x1080 | 5952 |
| daq-main | mu2e-dl-01 | mu2edaq | :1 | 2560x1440 | 5953 |
...
$ sed -n 3p bin/start-controlroom.sh
# start all six VNC sessions on the cluster, then open all tunnels.
$ venv/bin/pytest -q    # the conflict is known to the suite
42 passed, 1 xfailed
```
The superproject smoke test runs `crs-remote start --session daq-dl2`,
which exits 1 ("no session named 'daq-dl2'") against the shipped config.

## Why it matters
`crs-remote provision --all` writes launchers only on `shift-main`;
`dcs-main` and `trig-main` operators get none, and eight applications have
no launcher anywhere. Local port 5951 means `shift-main` in the README and
runbooks but `dcs-main` in the tools. Which layout the hosts run was not
verified in this review — that is the point: the repository cannot say.
S3 rather than S2 because the omission is visible (no icon) and the
`xfail` shows it is known.

## Suggested fix
Decide the live layout, make `controlroom.yaml` say it, regenerate the
README table and runbooks from it, remap `apps.yaml` `sessions:`, and turn
the `xfail` into a test that every `sessions:` name exists in
`controlroom.yaml`.

## Related
- `mu2edaq-desktop` DESK-001 (`8c3c7ace`)

<!-- mega-review-fingerprint: f6599080 -->

---

## CRS-003 — [ssh] crs-remote and the GUI gateway scan log in as shared accounts that refuse the operator's principal

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `src/mu2edaq_controlroom_setup/remote.py:33-39`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`crs-remote` (start, stop, status, install, provision) and the GUI's
"Via gateway" discovery scan ssh to `session.account@host`, the shared
account. Commit `da08771` moved the tunnels to `personal_user` precisely
because those accounts on `mu2e-mgr-01` returned
`Permission denied (gssapi-with-mic)` for the operator's principal; the
same login is still used for everything else. Separately, the shipped
`controlroom.yaml:5` describes `personal_user` as "login used on the jump
host", but the code never applies it to the jump (`-J host` carries no
user).

## Evidence
```
$ sed -n 43,46p src/mu2edaq_controlroom_setup/remote.py
    def start(self, session):
        cmd = ("~/controlroom/bin/start-vnc-session.sh %s %d -g %s -d %d" % ...
        return self._run(session.target, cmd)
$ sed -n 89,93p src/mu2edaq_controlroom_setup/gui/discovery_tab.py
        for s in self.config.sessions:
            if s.target not in seen:
$ git show -s da08771 | sed -n 6,12p
    Tunnels failed with "Permission denied (gssapi-with-mic)" because the
    forward SSHed in as the shared VNC account (mu2edcs/mu2eshift/mu2etrig),
    which the operator's Kerberos principal isn't authorized to log in as.
$ sed -n 5p config/controlroom.yaml
personal_user: anorman              # login used on the jump host
```

## Why it matters
Unless the shared accounts' `.k5login` changed after `da08771`, every
`crs-remote` subcommand fails on `mu2e-mgr-01`, so sessions cannot be
installed, started, stopped or provisioned from the tool. Not verified
live in this review, hence S3; if confirmed it is S2.

## Suggested fix
Document the `.k5login` requirement per shared account and add a
`crs-remote check` that runs `ssh -o BatchMode=yes account@host true` and
reports which accounts refuse the principal. Either drop the
"jump host" wording for `personal_user` or add an explicit
`gateway_user` key passed as `-J user@gateway`.

<!-- mega-review-fingerprint: 1ceb25cd -->

---

## CRS-004 — [discovery] VNC sidecar runs under system python3 with nothing installing mu2edaq-discovery; the embedded fallback dies on a malformed DISCOVER

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `server/vnc-discovery-responder.py:23-132`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`start-vnc-session.sh:58` starts the sidecar with bare `python3`. It
imports `mu2edaq_discovery.Responder` if the system interpreter has it,
else an embedded copy of the protocol. Nothing in this package installs
`mu2edaq-discovery` system-wide (`install-controlroom.sh` installs no
Python package; `bootstrap.sh` installs it only into the client venv), so
the fallback is what runs on a stock host. The fallback skips the
reference implementation's validation: it answers DISCOVERs the reference
ignores, and a `filter` that is a JSON list or string raises
`AttributeError` in the receive thread, which ends the process.

## Evidence
```
# fallback loaded with mu2edaq_discovery absent; one DISCOVER per case to 127.0.0.1
qid str, no filter   reply=REPLY  thread_alive=True
filter []            reply=REPLY  thread_alive=True     # reference: silent
qid absent           reply=REPLY  thread_alive=True     # reference: silent
qid int              reply=REPLY  thread_alive=True     # reference: silent
filter ['x']         reply=silent thread_alive=False
filter 'x'           reply=silent thread_alive=False
AttributeError: 'list' object has no attribute 'items'
  File "server/vnc-discovery-responder.py", line 68, in _matches
    for key, pat in (filt or {}).items():
$ sed -n 163,166p server/vnc-discovery-responder.py
    while not stop and responder.is_alive():
        time.sleep(1)
    responder.stop()
    return 0
```
The GUI's gateway scan has the same gap: it runs `mu2edaq-discover --json`
on the host (`gui/discovery_tab.py:49-53`), which nothing installs.

## Why it matters
One malformed datagram from any host on the subnet removes a VNC session
from discovery until the session is restarted, and the sidecar exits 0 so
nothing records a failure (`status` shows `dead`). Tunnels still work —
they are configured, not discovered — hence S3.

## Suggested fix
Minimal: in `_matches`, return False unless `filt` is a dict, and reject a
DISCOVER whose `qid` is not a string. Proper: have `crs-remote install`
install `mu2edaq-discovery` into the session account's user site
(`python3 -m pip install --user`) and keep the fallback only as a last
resort, run against the discovery conformance corpus proposed in DISC-015.

## Related
- `mu2edaq-discovery` DISC-015 (`f36464fd`), `Mu2e/mu2edaq-discovery#8`

<!-- mega-review-fingerprint: 27f73a63 -->

---

## CRS-005 — [template] start template sources --config after the environment, inverting its documented port precedence

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** bug
**Location:** `templates/start-mu2edaq-APP.sh:99-121`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
The template documents `--port` > `CRS_PORT_<NAME>` > `--config FILE` >
default, but it `source`s the config file with `set -a` after the
environment is inherited, so a `CRS_PORT_HTTP=` line in the file
overwrites the value `crs-app` exported.

## Evidence
```
$ sed -n 18,21p templates/start-mu2edaq-APP.sh
#   1. command line       --port NAME=VALUE      (repeatable)
#   2. environment        CRS_PORT_<NAME>        (crs-app sets these)
#   3. config file        sourced from --config FILE / $CRS_APP_CONFIG
$ sed -n 99,103p templates/start-mu2edaq-APP.sh
if [[ -n "$CONFIG_FILE" ]]; then
  ...
  set -a; source "$CONFIG_FILE"; set +a
# env CRS_PORT_HTTP=5001 + config CRS_PORT_HTTP=9999  ->  exported HTTP=9999
$ grep -l 'CRS_APP_CONFIG\|PORT_SPEC\|set -a' ../*/start-mu2edaq-*.sh
(no output)
```

## Why it matters
No adopted start script carries the template's config layer, so nothing
deployed is affected today (S4). The next app copied from the template
inherits a precedence opposite to the suite convention.

## Suggested fix
Snapshot `CRS_PORT_*` from the environment before sourcing the file and
restore those that were set, or source the file into a subshell and read
only names the environment did not set.

<!-- mega-review-fingerprint: 5eae41a4 -->

---

## CRS-006 — [config] install_dir, CRS_INSTALL_DIR, vnc_password_file, accounts and discovery.announce_interval are parsed and never used

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `src/mu2edaq_controlroom_setup/config.py:21-29`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
Four `controlroom.yaml` keys and one environment override are loaded into
`ControlRoomConfig` and read by nothing. The remote side hard-codes
`~/controlroom/bin`, and the sidecar's announce interval comes only from
`CRS_ANNOUNCE_INTERVAL` on the host, which `crs-remote` does not set.

## Evidence
```
$ grep -rn 'install_dir\|vnc_password_file\|\.accounts\|announce_interval' src server | grep -v pycache
src/mu2edaq_controlroom_setup/config.py:24:    "install_dir": "~/controlroom",
src/mu2edaq_controlroom_setup/config.py:25:    "vnc_password_file": "~/.vnc/passwd",
src/mu2edaq_controlroom_setup/config.py:65:        merged["install_dir"] = os.environ["CRS_INSTALL_DIR"]
src/mu2edaq_controlroom_setup/session.py:37:    install_dir: str
server/vnc-discovery-responder.py:145: default=int(os.environ.get("CRS_ANNOUNCE_INTERVAL", "30")),
$ grep -n 'controlroom/bin' src/mu2edaq_controlroom_setup/remote.py
44:        cmd = ("~/controlroom/bin/start-vnc-session.sh %s %d -g %s -d %d" %
49:        cmd = ("~/controlroom/bin/stop-vnc-session.sh %s %d" %
54:        cmd = ("~/controlroom/bin/status-vnc-session.sh %s %d" %
59:        cmd = "~/controlroom/bin/crs-provision-desktop --session %s" % session.name
$ sed -n 81-82p README.md
Command line > environment (`CRS_CONFIG`, `CRS_GATEWAY`,
`CRS_INSTALL_DIR`, `CRS_PORT_*`, …) > YAML config > defaults.
```

## Why it matters
An operator who changes `install_dir`, sets `CRS_INSTALL_DIR`, or sets
`discovery.announce_interval: 0` to silence multicast sees no effect and
no error. A host with a non-default `CRS_HOME` gets an install that
`crs-remote` then cannot find.

## Suggested fix
Use `config.install_dir` in `remote.py` and the GUI scan, pass
`CRS_HOME` and `CRS_ANNOUNCE_INTERVAL` through the remote command line,
and either use or delete `vnc_password_file` and `accounts`. Reject
unknown keys in `load_config`.

<!-- mega-review-fingerprint: 8acd9bdd -->

---

## CRS-007 — [ssh] credentials are delegated into shared accounts and the local forward is not pinned to loopback

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** enhancement
**Location:** `src/mu2edaq_controlroom_setup/sshutil.py:34-61`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
Every ssh sets `GSSAPIDelegateCredentials=yes`. For `crs-remote` the
target is a shared account, so the operator's forwardable TGT is written
into a credential cache owned by an account many people can become, for
the life of the session. The tunnel uses `-L LPORT:localhost:VPORT` with
no bind address, so the loopback-only local listener depends on the
client's `GatewayPorts` default.

## Evidence
```
$ sed -n 36-38p src/mu2edaq_controlroom_setup/sshutil.py
    args = ["ssh",
            "-o", "GSSAPIAuthentication=yes",
            "-o", "GSSAPIDelegateCredentials=yes"]
$ sed -n 59p src/mu2edaq_controlroom_setup/sshutil.py
        "-L", "%d:localhost:%d" % (local_port, remote_port),
```

## Why it matters
Nothing the remote commands do needs a delegated ticket. Exposure is
bounded by the short life of a `crs-remote` session and by sshd's
credential cleanup, which is why this is S3 rather than S1. A client
`ssh_config` with `GatewayPorts yes` would publish the forwarded VNC port
on the operator's LAN with only the VNC password in front of it.

## Suggested fix
Set `GSSAPIDelegateCredentials=no` for `remote_command_argv` (and for the
tunnel, which needs no delegation either); write the forward as
`-L 127.0.0.1:LPORT:localhost:VPORT`.

<!-- mega-review-fingerprint: fb7108a1 -->

---

## CRS-008 — [docs] the no-ticket hint sends operators to mu2e-krb-cron.py, which destroys a personal ticket

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** documentation
**Location:** `src/mu2edaq_controlroom_setup/sshutil.py:20-24`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
When `klist -s` fails, `crs-tunnel`/`crs-remote` tell the operator to run
`mu2edaq-controlroom/mu2e-krb-cron.py`; `README.md:45-46` says the same.
That script `kdestroy`s the default cache whenever its principal is not
one of six service principals — which includes every personal principal —
and refills the collection with the service principals. The tunnels log
in as `personal_user`, so the remedy breaks the thing it is offered for.

## Evidence
```
$ sed -n 21-23p src/mu2edaq_controlroom_setup/sshutil.py
            "No valid Kerberos ticket. Run kinit, or use the keytab manager:\n"
            "  python3 mu2edaq-controlroom/mu2e-krb-cron.py\n"
            "(keytabs in ~/Kerberos_Keytabs/Mu2e/<principal>.keytab)"
$ sed -n 341,348p ../mu2edaq-controlroom/mu2e-krb-cron.py
    if current_principal not in allowed_principals:
        logging.warning(
            "Current principal '%s' is not in the allowed list — destroying ticket.", ...
        run_kdestroy(args.dry_run)
        for p in principals:
            kinit_new(p["name"], p["keytab"], args.dry_run)
```

## Why it matters
The legacy package is superseded by `mu2edaq-kerberos` and recommended for
retirement; the hint keeps it load-bearing and steers operators into a
ticket loss that then surfaces as an unexplained tunnel failure.

## Suggested fix
Change the hint to `kinit <you>@FNAL.GOV` for tunnels, and
`get-kerberos-ticket <identity>` (mu2edaq-kerberos) where a service
principal is wanted. Update `README.md:45-46` to match.

## Related
- `mu2edaq-controlroom` CR-002 (the cron's ticket destruction)

<!-- mega-review-fingerprint: f73dfcd7 -->

---

## CRS-009 — [ci] no CI workflow for a 43-test suite

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** enhancement
**Location:** `.github/workflows`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
43 pytest tests exist and pass locally; nothing runs them on push or PR.

## Evidence
```
$ ls .github
ls: .github: No such file or directory
$ venv/bin/pytest -q
42 passed, 1 xfailed in 1.63s
```

## Why it matters
CONTRACT §6 S3 anchor case. `test_desktop.py` executes the real host
scripts; a regression in `install-controlroom.sh` or
`crs-provision-desktop` reaches the DAQ hosts unchecked.

## Suggested fix
A GitHub Actions workflow on `ubuntu-latest` with Python 3.9 and 3.12:
`pip install -e '.[dev]'` (no GUI extra needed) and `pytest`.

<!-- mega-review-fingerprint: c5bcbf9b -->

---

## CRS-010 — [gui] Discovery-tab double-click opens the ssh tunnel on the UI thread

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** bug
**Location:** `src/mu2edaq_controlroom_setup/gui/main.py:41-44`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`MainWindow._connect_to_vnc` calls `TunnelManager.open`, a blocking
`ssh -f` with Kerberos authentication through the gateway, directly in
the slot. The Tunnels tab does the same work in a `QThread`.

## Evidence
```
$ sed -n 40,44p src/mu2edaq_controlroom_setup/gui/main.py
                try:
                    manager = TunnelManager(self.config)
                    if manager.status(session) != "open":
                        manager.open(session)
                    viewer_mod.attach(session)
```

## Why it matters
The window freezes for the authentication round trip (seconds through the
gateway; until the ssh timeout if the gateway is unreachable).

## Suggested fix
Reuse `_TunnelWorker(action="connect")` from `tunnels_tab.py`.

<!-- mega-review-fingerprint: 638fc580 -->

---

## CRS-011 — [packaging] pyproject.toml declares BSD-3-Clause while LICENSE is MIT

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** bug
**Location:** `pyproject.toml:11`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
Commit `b72c0f0` added an MIT `LICENSE`; the package metadata still says
BSD-3-Clause.

## Evidence
```
$ sed -n 11p pyproject.toml
license = {text = "BSD-3-Clause"}
$ head -1 LICENSE
MIT License
```

## Why it matters
Installed metadata misstates the licence.

## Suggested fix
`license = {text = "MIT"}`.

<!-- mega-review-fingerprint: 23ae1ad1 -->

---

## CRS-012 — [docs] doc/issues/README.md calls the 22 filed and closed tickets drafts; README test count is stale

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** documentation
**Location:** `doc/issues/README.md:4-5`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`doc/issues/README.md` says the tickets are drafts not to be submitted;
all 22 were filed and all are closed. `README.md:97` says 38 tests; there
are 43. `doc/README.md:12` and `README.md:91` repeat "draft".

## Evidence
```
$ sed -n 4,5p doc/issues/README.md
body below the `---` separator is the issue text. **These are drafts —
do not submit without explicit approval.**
# exact-title match with gh issue list --state all, all 22: CLOSED
01-startstop-mu2edaq-bigredbox -> #2 CLOSED ... 22-discovery-mu2edaq-trigger-scalers -> #2 CLOSED
$ sed -n 97p README.md
venv/bin/pytest        # 38 tests: config validation, tunnel argv, payload,
```

## Why it matters
Someone following the helper loop in `doc/issues/README.md:15-21` files 22
duplicates.

## Suggested fix
Mark the directory as a historical record, list the filed issue numbers
(the table in `doc/ARCHITECTURE.md`), remove the bulk-filing loop, and
fix the test count.

<!-- mega-review-fingerprint: 19e3ea39 -->

---

## CRS-013 — [man] man pages were misnamed, unversioned and missing for six executables

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** documentation
**Location:** `man/man1/`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
Before this review: `install-controlroom.1` and `start-vnc-session.1`
were named without the `.sh` the commands are invoked with; `crs-app.1`
also documented `crs-provision-desktop`; `.TH` carried "Mu2e DAQ" instead
of `<package> <version>`; no page existed for `crs-provision-desktop`,
`start-controlroom.sh`, `stop-controlroom.sh`, `status-vnc-session.sh`,
`stop-vnc-session.sh` or `vnc-discovery-responder.py`.

## Evidence
```
$ git show b72c0f0:man/man1/crs-app.1 | head -1
.TH CRS\-APP 1 "2026-06-12" "Mu2e DAQ" "Mu2e DAQ Manual"
$ git ls-tree --name-only b72c0f0 man/man1/
crs-app.1 crs-gui.1 crs-remote.1 crs-tunnel.1 install-controlroom.1 start-vnc-session.1
```

## Why it matters
Fixed in the mega-review man-page commit; recorded so the fingerprint
exists if the layout regresses.

## Suggested fix
None beyond the review commit. Keep one page per shipped executable.

<!-- mega-review-fingerprint: 3433011d -->

---

## CRS-014 — [host] the PyYAML-free fallback parser breaks --all-local and writes Terminal=true on every launcher

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** bug
**Location:** `server/crs-app:31-67`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
When the host's system `python3` has no PyYAML, `crs-app`,
`crs-provision-desktop` and `install-controlroom.sh` use `_tiny_yaml`. It
always returns `{"apps": [...]}` and leaves booleans as strings. For
`controlroom.yaml` there is then no `sessions` key, so
`crs-provision-desktop --all-local` always exits 1; for `apps.yaml`,
`terminal: false` becomes `"false"`, and `bool("false")` is true.

## Evidence
```
$ python3 -c '...m._tiny_yaml("config/controlroom.yaml")'
keys: ['apps'] | sessions: None | apps entries: 3
$ python3 -c '... compare _tiny_yaml and yaml.safe_load on config/apps.yaml'
controlcenter desktop fallback= {'icon': 'preferences-system', 'terminal': 'false'}
              pyyaml= {'icon': 'preferences-system', 'terminal': False}
... (all 12 apps)
$ sed -n 76p server/crs-provision-desktop
        terminal = bool(app.get("desktop", {}).get("terminal", False))
```

## Why it matters
`crs-remote provision` uses `--session`, so the main path still writes
launchers; they all open an extra terminal window. Whether the AL9 hosts'
system Python has PyYAML was not checked. S4.

## Suggested fix
Convert `true`/`false` in `_tiny_yaml`; have `--all-local` fail with a
clear message when PyYAML is missing (the session list is nested YAML the
fallback cannot parse), or install `python3-pyyaml` as a documented host
prerequisite.

<!-- mega-review-fingerprint: a3ca8c30 -->
