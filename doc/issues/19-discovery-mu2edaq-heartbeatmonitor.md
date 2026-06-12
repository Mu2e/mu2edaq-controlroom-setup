---
repo: mu2edaq-heartbeatmonitor
title: Add mu2edaq-discovery auto-discovery support
labels: enhancement
---

Add support for the Mu2e DAQ service discovery protocol so this
application appears in `mu2edaq-discover` scans and the control room
discovery browser (protocol spec:
https://github.com/Mu2e/mu2edaq-discovery/blob/main/doc/PROTOCOL.md —
UDP multicast 239.255.42.99:28999, JSON query/response).

**Requested changes**
- Depend on the `mu2edaq-discovery` package (stdlib-only, pip-installable
  from the sibling submodule under mu2edaq-main).
- Embed a responder at startup:

```python
from mu2edaq_discovery import Responder
responder = Responder(name="Heartbeat Monitor", app="heartbeatmonitor",
                      port=8081, scheme="http",
                      meta={"udp_port": "9999"})
responder.start()
```

- Start the responder **after** the listening socket is bound (never
  advertise a port that isn't accepting), and call `responder.stop()`
  on shutdown.

**Additional opportunity:** the monitor's `SystemRegistry` could also
*ingest* unsolicited ANNOUNCE messages from the 28999 multicast group
alongside its port-9999 heartbeats, giving the dashboard a unified view
of discovered services. Track that as a follow-on; this issue covers
announcing the monitor itself.
