---
repo: mu2edaq-heartbeatmonitor
title: Add start/stop scripts and make the HTTP port configurable (8080 clashes with resource-manager)
labels: enhancement
---

No start/stop scripts exist, and the Flask dashboard defaults to HTTP
8080, which collides with mu2edaq-resource-manager when co-hosted.

**Requested changes**
- Add `start-mu2edaq-heartbeatmonitor.sh` / `stop-mu2edaq-heartbeatmonitor.sh`.
- Make the HTTP port configurable (config + `--port` + `CRS_PORT_HTTP`
  env override). The control room app inventory assigns it **8081**.
- Keep the UDP heartbeat listener port configurable too
  (`CRS_PORT_UDP`, default 9999).
