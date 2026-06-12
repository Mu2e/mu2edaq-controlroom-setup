---
repo: mu2edaq-trigger-scalers
title: Add start/stop wrapper scripts and make the UDP port configurable (5555 clashes with dashboard ZMQ)
labels: enhancement
---

The C++ Qt GUI has no start/stop scripts, and its default UDP receive
port 5555 collides with mu2edaq-dashboard's ZeroMQ port when co-hosted.

**Requested changes**
- Add `start-mu2edaq-trigger-scalers.sh`: locate the built binary
  (build/trigger-scalers), honor `DISPLAY` from the environment, and
  pass the configured endpoints.
- Add `stop-mu2edaq-trigger-scalers.sh`.
- Accept `CRS_PORT_UDP` (control room assigns **5557**) and
  `CRS_PORT_ZMQ` (default 5556) env overrides on top of scalars.yaml.
