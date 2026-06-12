#!/usr/bin/env python3
"""Mock auto-discovery responder for a VNC session.

VNC does not speak mu2edaq-discovery, so the session start wrapper
launches this sidecar, which answers DISCOVER queries (and optionally
multicasts periodic announcements) on the session's behalf.

Self-contained: uses mu2edaq_discovery when installed, otherwise falls
back to an embedded minimal responder implementing the same protocol
(mu2edaq-discovery/1). Stdlib only either way.

Usage:
  vnc-discovery-responder.py --name daq-main --display :1 --port 5901 \
      --geometry 2560x1440 [--account mu2edaq] [--announce-interval 30]
"""

import argparse
import os
import signal
import sys
import time

try:
    from mu2edaq_discovery import Responder
except ImportError:
    # Embedded fallback (protocol mu2edaq-discovery/1). Keep in sync with
    # the mu2edaq-discovery package; this exists so DAQ hosts need no venv.
    import json
    import random
    import socket
    import struct
    import threading
    import uuid
    from datetime import datetime, timezone

    GROUP, PORT, PROTO, MAX_DGRAM = "239.255.42.99", 28999, "mu2edaq-discovery/1", 1400

    class Responder(threading.Thread):
        JITTER_MAX = 0.250

        def __init__(self, name, app, port, scheme=None, version=None, meta=None,
                     host=None, group=GROUP, listen_port=PORT,
                     announce_interval=0, bind_interface=None):
            super().__init__(daemon=True)
            self.instance_id = str(uuid.uuid4())
            self._fields = {
                "proto": PROTO, "type": "ANNOUNCE", "id": self.instance_id,
                "name": name, "app": app, "host": host or socket.getfqdn(),
                "port": int(port), "scheme": scheme or app,
                "version": version or "0", "pid": os.getpid(),
                "started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            if meta:
                self._fields["meta"] = dict(meta)
            self.group, self.listen_port = group, listen_port
            self.announce_interval = announce_interval
            self.bind_interface = bind_interface or "0.0.0.0"
            self._stop_event = threading.Event()

        def _announce(self, qid=None):
            msg = dict(self._fields)
            if qid is not None:
                msg["qid"] = qid
            return json.dumps(msg, separators=(",", ":")).encode()

        def _matches(self, filt):
            import fnmatch
            for key, pat in (filt or {}).items():
                if key not in ("app", "name", "host"):
                    return False
                if not fnmatch.fnmatch(str(self._fields.get(key, "")), str(pat)):
                    return False
            return True

        def stop(self, timeout=2.0):
            self._stop_event.set()
            try:
                poke = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                poke.sendto(b"", ("127.0.0.1", self.listen_port))
                poke.close()
            except OSError:
                pass
            self.join(timeout=timeout)

        def run(self):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass
            sock.bind(("", self.listen_port))
            mreq = struct.pack("4s4s", socket.inet_aton(self.group),
                               socket.inet_aton(self.bind_interface))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(0.5)
            send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            send.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
            next_announce = (time.monotonic() + self.announce_interval
                             if self.announce_interval > 0 else None)
            try:
                while not self._stop_event.is_set():
                    if next_announce and time.monotonic() >= next_announce:
                        try:
                            send.sendto(self._announce(), (self.group, self.listen_port))
                        except OSError:
                            pass
                        next_announce = time.monotonic() + self.announce_interval
                    try:
                        data, addr = sock.recvfrom(MAX_DGRAM + 1)
                    except socket.timeout:
                        continue
                    if self._stop_event.is_set():
                        break
                    try:
                        msg = json.loads(data.decode())
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if (not isinstance(msg, dict) or msg.get("proto") != PROTO
                            or msg.get("type") != "DISCOVER"):
                        continue
                    if not self._matches(msg.get("filter")):
                        continue
                    time.sleep(random.uniform(0, self.JITTER_MAX))
                    try:
                        send.sendto(self._announce(qid=msg.get("qid")), addr)
                    except OSError:
                        pass
            finally:
                send.close()
                sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="Discovery responder sidecar for a VNC session.")
    parser.add_argument("--name", required=True, help="session name (e.g. daq-main)")
    parser.add_argument("--display", required=True, help="VNC display (e.g. :1)")
    parser.add_argument("--port", type=int, required=True, help="VNC port (5900+N)")
    parser.add_argument("--geometry", default="", help="session geometry WxH")
    parser.add_argument("--account", default=os.environ.get("USER", ""),
                        help="account owning the session")
    parser.add_argument("--announce-interval", type=int,
                        default=int(os.environ.get("CRS_ANNOUNCE_INTERVAL", "30")),
                        help="seconds between unsolicited announces (0 = off)")
    args = parser.parse_args()

    meta = {"display": args.display, "account": args.account}
    if args.geometry:
        meta["geometry"] = args.geometry

    responder = Responder(
        name="VNC %s %s (%s)" % (os.uname().nodename, args.display, args.name),
        app="vnc", port=args.port, scheme="vnc", version="1.0", meta=meta,
        announce_interval=args.announce_interval,
    )
    responder.start()

    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
    signal.signal(signal.SIGINT, lambda *a: stop.append(1))
    while not stop and responder.is_alive():
        time.sleep(1)
    responder.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
