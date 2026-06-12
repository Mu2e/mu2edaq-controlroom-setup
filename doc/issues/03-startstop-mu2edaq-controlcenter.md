---
repo: mu2edaq-controlcenter
title: Rename start.sh / stop.sh to start-mu2edaq-controlcenter.sh / stop-mu2edaq-controlcenter.sh
labels: enhancement
---

`start.sh` / `stop.sh` collide with identically-named scripts from other
repos when symlinked into the shared `~/controlroom/bin` area used by the
control room setup (mu2edaq-controlroom-setup).

**Requested changes**
- Rename to `start-mu2edaq-controlcenter.sh` / `stop-mu2edaq-controlcenter.sh`
  (keep `start.sh`/`stop.sh` as symlinks for one release).
- Make the TCP command server port (9876) overridable via `CRS_PORT_CMD`
  env var and a `--port` option.
