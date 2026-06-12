---
repo: mu2edaq-resource-manager
title: Move scripts/start_server.sh to top-level start-mu2edaq-resource-manager.sh and add a stop script
labels: enhancement
---

For the shared control room bin area (mu2edaq-controlroom-setup):

**Requested changes**
- Provide top-level `start-mu2edaq-resource-manager.sh` (wrapping or
  replacing `scripts/start_server.sh`).
- Add `stop-mu2edaq-resource-manager.sh`.
- Accept a `CRS_PORT_HTTP` env override for the FastAPI port (default 8080).
