---
repo: mu2edaq-dataformat-viewer
title: Add start-mu2edaq-dataformat-viewer.sh / stop-mu2edaq-dataformat-viewer.sh
labels: enhancement
---

No start/stop scripts exist. The control room desktop icons
(mu2edaq-controlroom-setup) need standardized scripts.

**Requested changes**
- Add `start-mu2edaq-dataformat-viewer.sh` (activate venv, launch the
  PyQt6 GUI; `DISPLAY` must be honored from the environment so the app
  appears in the invoking VNC session).
- Add `stop-mu2edaq-dataformat-viewer.sh`.
- Accept a `CRS_PORT_LISTEN` env override for the 7755 listener port.
