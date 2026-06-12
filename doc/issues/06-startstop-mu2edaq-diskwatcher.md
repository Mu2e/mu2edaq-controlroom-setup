---
repo: mu2edaq-diskwatcher
title: Rename start_diskwatcher.sh / stop_diskwatcher.sh to dashed convention
labels: enhancement
---

For the shared control room bin area (mu2edaq-controlroom-setup):

**Requested changes**
- Rename `start_diskwatcher.sh` / `stop_diskwatcher.sh` to
  `start-mu2edaq-diskwatcher.sh` / `stop-mu2edaq-diskwatcher.sh`
  (keep the old names as symlinks for one release).
- Accept a `CRS_PORT_HTTP` env override for the Flask port (default 5002).
