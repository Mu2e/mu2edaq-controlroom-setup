"""Command line entry points: crs-tunnel and crs-remote."""

import argparse
import sys

from .config import ConfigError, load_config
from .remote import RemoteRunner
from .sshutil import KerberosError
from .tunnels import TunnelManager
from . import viewer as viewer_mod


def _common_args(parser):
    parser.add_argument("--config", default=None, help="controlroom.yaml path")
    parser.add_argument("--ssh-config", default=None,
                        help="alternate ssh config (-F) for testing")
    sel = parser.add_argument_group("target selection")
    sel.add_argument("--session", default=None, help="one session by name")
    sel.add_argument("--host", default=None, help="all sessions on a host")
    sel.add_argument("--all", action="store_true", help="every configured session")


def _select(config, args):
    runner = RemoteRunner(config)
    try:
        return runner.select(session=args.session, host=args.host,
                             all_sessions=args.all)
    except (KeyError, ValueError) as exc:
        sys.exit("error: %s" % exc)


def tunnel_main(argv=None):
    parser = argparse.ArgumentParser(
        prog="crs-tunnel",
        description="Manage ssh tunnels to the control room VNC sessions.")
    parser.add_argument("command", choices=["open", "close", "status", "connect"])
    _common_args(parser)
    parser.add_argument("--viewer", default=None,
                        help="VNC viewer binary (connect only)")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        sys.exit("error: %s" % exc)
    manager = TunnelManager(config, ssh_config=args.ssh_config)

    if args.command == "status" and not (args.session or args.host or args.all):
        args.all = True
    sessions = _select(config, args)

    try:
        for session in sessions:
            if args.command == "open":
                state = manager.open(session)
                print("%-12s %s (localhost:%d -> %s:%d)" %
                      (session.name, state, session.local_port,
                       session.host.split(".")[0], session.vnc_port))
            elif args.command == "close":
                state = manager.close(session)
                print("%-12s %s" % (session.name, state))
            elif args.command == "status":
                state = manager.status(session)
                print("%-12s %-7s localhost:%d -> %s:%d (%s)" %
                      (session.name, state, session.local_port,
                       session.host.split(".")[0], session.vnc_port,
                       session.account))
            elif args.command == "connect":
                if manager.status(session) != "open":
                    manager.open(session)
                    print("%-12s tunnel opened" % session.name)
                viewer_mod.attach(session, viewer=args.viewer)
                print("%-12s viewer launched (localhost:%d)" %
                      (session.name, session.local_port))
    except (KerberosError, RuntimeError) as exc:
        sys.exit("error: %s" % exc)
    return 0


def remote_main(argv=None):
    parser = argparse.ArgumentParser(
        prog="crs-remote",
        description="Run control room operations on the DAQ hosts over ssh.")
    parser.add_argument("command",
                        choices=["start", "stop", "status", "install", "provision"])
    _common_args(parser)
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        sys.exit("error: %s" % exc)
    runner = RemoteRunner(config, ssh_config=args.ssh_config)

    if args.command == "status" and not (args.session or args.host or args.all):
        args.all = True
    sessions = _select(config, args)

    # install runs once per (host, account), not once per session.
    if args.command == "install":
        seen = set()
        sessions = [s for s in sessions
                    if (s.host, s.account) not in seen
                    and not seen.add((s.host, s.account))]

    failures = 0
    try:
        for session in sessions:
            result = getattr(runner, args.command)(session)
            out = (result.stdout or b"")
            if isinstance(out, bytes):
                out = out.decode(errors="replace")
            err = (result.stderr or b"")
            if isinstance(err, bytes):
                err = err.decode(errors="replace")
            prefix = "%s@%s" % (session.account, session.host.split(".")[0])
            for line in out.strip().splitlines():
                print("[%s] %s" % (prefix, line))
            if result.returncode != 0:
                failures += 1
                for line in err.strip().splitlines():
                    print("[%s] ERR %s" % (prefix, line), file=sys.stderr)
    except KerberosError as exc:
        sys.exit("error: %s" % exc)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(tunnel_main())
