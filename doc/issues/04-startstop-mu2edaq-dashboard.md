---
repo: mu2edaq-dashboard
title: Standardize start script name and add stop-mu2edaq-dashboard.sh
labels: enhancement
---

For the shared control room bin area (mu2edaq-controlroom-setup):

**Requested changes**
- Rename `start_dashboard.sh` to `start-mu2edaq-dashboard.sh`
  (keep the old name as a symlink for one release).
- Add `stop-mu2edaq-dashboard.sh` (none exists today).
- Accept `CRS_PORT_HTTP` (default 5001) and `CRS_PORT_ZMQ` (default 5555)
  env overrides for the web and ZeroMQ ports.
