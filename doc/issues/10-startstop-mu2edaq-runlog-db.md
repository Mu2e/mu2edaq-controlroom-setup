---
repo: mu2edaq-runlog-db
title: Standardize start-mu2e-rundb-viewer to start-mu2edaq-runlog-db.sh and add a stop script
labels: enhancement
---

For the shared control room bin area (mu2edaq-controlroom-setup):

**Requested changes**
- Rename `start-mu2e-rundb-viewer` to `start-mu2edaq-runlog-db.sh`
  (matching the repo name, with `.sh`; keep the old name as a symlink
  for one release).
- Add `stop-mu2edaq-runlog-db.sh`.
- Accept a `CRS_PORT_HTTP` env override for the Django/gunicorn port
  (default 8000).
