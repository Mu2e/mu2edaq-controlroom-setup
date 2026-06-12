"""SSH command construction and Kerberos preflight.

Builds ssh argv lists routed through the gateway (ProxyJump), following
the conventions in mu2edaq-cluster-tools/ssh_selector.py and
mu2edaq-controlroom/bin/start_vnc_tunnels_mu2e.sh.
"""

import os
import subprocess


class KerberosError(RuntimeError):
    pass


def check_ticket():
    """Raise KerberosError unless a valid Kerberos ticket exists."""
    result = subprocess.run(["klist", "-s"], capture_output=True)
    if result.returncode != 0:
        raise KerberosError(
            "No valid Kerberos ticket. Run kinit, or use the keytab manager:\n"
            "  python3 mu2edaq-controlroom/mu2e-krb-cron.py\n"
            "(keytabs in ~/Kerberos_Keytabs/Mu2e/<principal>.keytab)"
        )


def control_socket_path(host, port):
    """Control socket path for a tunnel, in ~/.crs (not /tmp)."""
    run_dir = os.path.expanduser("~/.crs")
    os.makedirs(run_dir, exist_ok=True)
    return os.path.join(run_dir, "ssh-ctrl-%s-%d" % (host.split(".")[0], port))


def base_ssh_args(gateway=None, ssh_config=None):
    """Common ssh arguments: GSSAPI auth and optional ProxyJump/config."""
    args = ["ssh",
            "-o", "GSSAPIAuthentication=yes",
            "-o", "GSSAPIDelegateCredentials=yes"]
    if ssh_config:
        args += ["-F", ssh_config]
    if gateway:
        args += ["-J", gateway]
    return args


def remote_command_argv(target, command, gateway=None, ssh_config=None):
    """argv to run `command` (a string) on account@host via the gateway."""
    return base_ssh_args(gateway, ssh_config) + [
        "-o", "BatchMode=yes", target, command]


def tunnel_open_argv(target, local_port, remote_port, socket_path,
                     gateway=None, ssh_config=None):
    """argv to open a backgrounded master tunnel with a control socket."""
    return base_ssh_args(gateway, ssh_config) + [
        "-f", "-N", "-M",
        "-S", socket_path,
        "-o", "ExitOnForwardFailure=yes",
        "-L", "%d:localhost:%d" % (local_port, remote_port),
        target,
    ]


def tunnel_check_argv(target, socket_path):
    """argv to probe a control socket (`ssh -O check`)."""
    return ["ssh", "-S", socket_path, "-O", "check", target]


def tunnel_close_argv(target, socket_path):
    """argv to close a master tunnel via its control socket."""
    return ["ssh", "-S", socket_path, "-O", "exit", target]
