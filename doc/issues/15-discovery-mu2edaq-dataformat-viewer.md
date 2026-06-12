---
repo: mu2edaq-dataformat-viewer
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
responder = Responder(name="Data Format Viewer", app="dataformat-viewer",
                      port=7755, scheme="tcp")
responder.start()
```

- Start the responder **after** the listening socket is bound (never
  advertise a port that isn't accepting), and call `responder.stop()`
  on shutdown.

