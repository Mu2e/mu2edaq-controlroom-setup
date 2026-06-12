---
repo: mu2edaq-trigger-scalers
title: Add discovery support (blocked on mu2edaq-discovery C++ library)
labels: enhancement
---

Add support for the Mu2e DAQ service discovery protocol so the trigger
scalers display appears in `mu2edaq-discover` scans and the control
room discovery browser (protocol spec:
https://github.com/Mu2e/mu2edaq-discovery/blob/main/doc/PROTOCOL.md —
UDP multicast 239.255.42.99:28999, JSON query/response).

This is a C++ Qt application; the native responder is **blocked on the
mu2edaq-discovery C++ library** (tracked in that repo as future work —
the protocol is plain JSON over UDP, so a `QUdpSocket` implementation
is mechanical).

**Interim option (unblocked now):** have
`start-mu2edaq-trigger-scalers.sh` launch the stdlib-only Python
responder as a sidecar alongside the binary:

```bash
python3 -c "
from mu2edaq_discovery import Responder
import signal, time
r = Responder(name='Trigger Scalers', app='trigger-scalers',
              port=int('${CRS_PORT_UDP:-5557}'), scheme='udp',
              meta={'zmq_port': '${CRS_PORT_ZMQ:-5556}'})
r.start(); signal.pause()
" &
echo $! > /tmp/trigger-scalers-responder.pid
```

and kill it from the stop script.

**Native (once the C++ lib exists)**
- Join 239.255.42.99:28999, answer DISCOVER with ANNOUNCE after the
  receive sockets are bound; stop announcing on shutdown.
