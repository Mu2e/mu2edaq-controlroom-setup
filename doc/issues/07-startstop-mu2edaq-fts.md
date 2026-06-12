---
repo: mu2edaq-fts
title: Rename start_fts.sh / stop_fts.sh to start-mu2edaq-fts.sh / stop-mu2edaq-fts.sh
labels: enhancement
---

For the shared control room bin area (mu2edaq-controlroom-setup):

**Requested changes**
- Rename `start_fts.sh` / `stop_fts.sh` to `start-mu2edaq-fts.sh` /
  `stop-mu2edaq-fts.sh` (keep the old names as symlinks for one release).
- Accept a `CRS_PORT_HTTP` env override for the web interface port.
