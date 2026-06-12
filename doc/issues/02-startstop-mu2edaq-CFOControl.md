---
repo: mu2edaq-CFOControl
title: Add start-mu2edaq-cfocontrol.sh / stop-mu2edaq-cfocontrol.sh
labels: enhancement
---

No start/stop scripts exist. The control room desktop icons
(mu2edaq-controlroom-setup) launch apps via standardized
`start-<app>.sh` / `stop-<app>.sh` scripts installed in
`~/controlroom/bin`.

**Requested changes**
- Add `start-mu2edaq-cfocontrol.sh` that opens the interactive CFO
  control session (in a terminal) targeting the MacroMaker host/port
  from config; accept a `CRS_PORT_MACROMAKER` env override (default 5000).
- Add `stop-mu2edaq-cfocontrol.sh`; exit 0 as a no-op when nothing runs.
