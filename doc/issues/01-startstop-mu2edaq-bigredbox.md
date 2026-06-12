---
repo: mu2edaq-bigredbox
title: Standardize start/stop scripts to start-mu2edaq-bigredbox.sh / stop-mu2edaq-bigredbox.sh
labels: enhancement
---

The control room bin installer (mu2edaq-controlroom-setup) symlinks every
app's standardized `start-<app>.sh` / `stop-<app>.sh` into a single
`~/controlroom/bin` area. The current `start_daq_alert.sh` /
`stop_daq_alert.sh` names do not match the convention.

**Requested changes**
- Rename to `start-mu2edaq-bigredbox.sh` / `stop-mu2edaq-bigredbox.sh`.
- Keep the old names as symlinks for one release.
- Honor `DISPLAY` from the environment (icons launch inside VNC desktops)
  and accept a `CRS_PORT_UDP` override for the 37020 listener port.
