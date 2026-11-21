# Remote control rooms

Clickable launchers that show the Mu2e control room screens at a remote
institution, on Linux or macOS, plus a launcher for the DAQ machine picker.
Each site has two small files in `sites/`; one command installs everything
else. Caltech's remote operations center (ROC) is the first site.

What it does:

- opens each screen through `crs-tunnel connect`, with the site's login
  account, view-only, and saved VNC passwords;
- gets a Kerberos ticket from the site's keytab when there is none;
- makes one launcher per screen (an app-menu entry on Linux, an app in
  `~/Applications/Mu2e` on macOS) and one for `ssh-selector`.

What it never does: start, stop, install or provision anything on the DAQ
hosts. That stays with `crs-remote` and the DAQ coordinator. Screens a site
adds are marked unmanaged, and `crs-remote` refuses them.

## Files

| Path | Purpose |
|---|---|
| `install.sh` | One-time client setup and launcher creation (`--help`) |
| `crs-screen` | Open screens: `crs-screen --site NAME SESSION...`; `--check` tests logins |
| `crs-nodes` | Open the DAQ machine picker (`ssh-selector`) |
| `sites/NAME.yaml` | Site overlay for `crs-tunnel` (login account, view-only, extra screens) |
| `sites/NAME.env` | Launcher settings (Kerberos identity, keytab, viewer, password files, launchers) |
| `sites/example.*` | Templates for a new site |
| `lib/` | Shared shell code and the macOS icon renderer |

Machine-local settings, which are not in git, go in
`~/.config/mu2edaq-remote-site/NAME.env`. That file is read after
`sites/NAME.env` and can override any setting in it.

## Before you start

Ask the DAQ coordinator for:

1. A Kerberos identity authorized on the gateway and the DAQ hosts as the
   account in your overlay's `personal_user` (Caltech: `mu2eshift`), and
   its keytab. Without a keytab, `kinit` asks for that principal's password.
2. Optionally, copies of the VNC password files for the session accounts,
   saved as `~/.vnc/<account>.passwd`, mode 600. Without them the viewer
   asks for the password each time.

Keytabs and password files never go in this repository.

Prerequisites, which `install.sh` checks and explains if missing:

| | Linux | macOS |
|---|---|---|
| Python 3.9+ with venv | distribution `python3` (`python3-venv` on Debian) | `xcode-select --install` |
| ssh, kinit, klist | `openssh-clients`, `krb5-workstation` / `krb5-user` | built in |
| VNC viewer | TigerVNC `vncviewer` (`tigervnc` / `tigervnc-viewer`), or set `SITE_VIEWER` | TigerVNC Viewer.app in /Applications, from tigervnc.org |

On macOS, the built-in Screen Sharing cannot be view-only and cannot read a
password file. A view-only site therefore needs TigerVNC there. Without it,
`crs-tunnel connect` stops before opening anything.

## Install

Check out controlroom-setup, and mu2edaq-cluster-tools next to it for the node
menu. Both are submodules of mu2edaq-main, so a mu2edaq-main checkout already
has them side by side:

```bash
git clone https://github.com/Mu2e/mu2edaq-controlroom-setup.git
git clone https://github.com/Mu2e/mu2edaq-cluster-tools.git      # optional, node menu
mu2edaq-controlroom-setup/remote-site/install.sh --site caltech
```

`install.sh` goes through these steps:

1. Checks the prerequisites.
2. Creates `venv/` with PyYAML only, or reuses the one `bootstrap.sh` made.
3. Checks `sites/NAME.yaml` against `config/controlroom.yaml`.
4. Finds a VNC viewer.
5. Installs `ssh-selector` from `../mu2edaq-cluster-tools`, if needed.
6. Checks the keytab and password-file permissions.
7. Makes the launchers listed in `SITE_LAUNCHERS`.

Use `--launchers "shift-main cr01"` to make a different set, `--no-launchers`
to make none, and `--uninstall` to remove the launchers it made.
`DRY_RUN=1` prints what it would do.

Every launcher file carries a marker naming the site. Before writing
anything, `install.sh` checks each file it would write. Files this installer
made for the same site are replaced. Files it did not make are only
overwritten with `--replace`, and symbolic links never are. If any check
fails, nothing is written. `--uninstall` removes only files that still carry
the site's marker. If one cannot be removed, it says so, exits with an
error and keeps that file on its list, so running `--uninstall` again
retries.

On macOS, the tests check the generated `.icns` icons. Where `iconutil` is
refused (some sandboxes), set `CRS_TEST_NO_ICONUTIL=1` to skip that one
check.

Then make the first ssh contact on purpose, so any host-key questions are
answered once:

```bash
mu2edaq-controlroom-setup/remote-site/crs-screen --site caltech --check
```

Finally, pin the launchers:

- **Linux:** find "Mu2e ..." in the application menu (GNOME: Activities) and
  add it to Favorites. The KDE application launcher works the same way.
  A copy also goes on `~/Desktop` when that folder exists.
- **macOS:** open `~/Applications/Mu2e` in Finder and drag the apps to the
  Dock. They also show up in Spotlight, in the Apps window on macOS 26, and
  in Launchpad on earlier versions.

## Daily use

Click a launcher. A terminal window opens. It gets a ticket if needed, opens
the tunnel, starts the viewer and closes when it is done (right away on
Linux, after a few seconds on macOS). The tunnel and the viewer keep running
when that window closes.

On errors the window stays open until you press Enter.

From a shell:

```bash
remote-site/crs-screen --site caltech shift-main cr01 cr02
remote-site/crs-nodes --site caltech
venv/bin/crs-tunnel status --site-config remote-site/sites/caltech.yaml
venv/bin/crs-tunnel close --all --site-config remote-site/sites/caltech.yaml
```

`CRS_REMOTE_SITE=caltech` saves typing `--site`. Setting
`CRS_SITE_CONFIG=remote-site/sites/caltech.yaml` does the same for plain
`crs-tunnel` commands.

## Adding a site

1. Copy `sites/example.yaml` and `sites/example.env` to `sites/<site>.yaml`
   and `sites/<site>.env`.
2. In the YAML, set `personal_user` and `gateway` to the account your
   identity is authorized as. Keep `view_only: true`. Add any extra screens
   to watch under `sessions`.
3. In the env file, set `SITE_PRINCIPAL`, `SITE_KEYTAB` (a path, not the
   keytab itself), `SITE_PASSWORD_FILE` and `SITE_LAUNCHERS`.
4. Run `install.sh --site <site>` and `crs-screen --site <site> --check`.

### Site overlay rules

`crs-tunnel` applies overlays on top of `config/controlroom.yaml`:

- **Where they come from:** `--site-config PATH` (repeatable), or else
  `CRS_SITE_CONFIG` with paths separated by `:`.
- **Allowed keys:** only `personal_user`, `gateway`, `view_only` and
  `sessions`. Any other key is an error.
- **`personal_user` and `gateway`:** the last file that sets them wins.
  `CRS_GATEWAY` beats every file.
- **`view_only`:** true if any overlay says true; a later false does not
  undo it.
- **`sessions`:** added after controlroom.yaml's own, and never managed.
  A name, local port or host/display pair that repeats an existing one is
  an error naming the overlay file. If controlroom.yaml later lists the
  same screens, remove them from the overlay.
- **Who reads them:** only `crs-tunnel`. `crs-remote` and `crs-gui` never
  read overlays.

## View-only is a courtesy, not a lock

The view-only setting stops a remote viewer from sending mouse and keyboard
input by accident. It does not stop someone who has the VNC password and
uses another viewer. Real enforcement would need a separate view-only VNC
password on the DAQ hosts; that is the DAQ coordinator's decision.

## Troubleshooting

| Symptom | Look at |
|---|---|
| Launcher window shows an error | the message; then `~/.crs/tunnels.log` |
| Tunnel opens, no picture | `~/.crs/viewer-<session>.log`; the session may not be running on the DAQ host |
| `Permission denied (gssapi-with-mic)` | `klist`: wrong or expired identity; ask whether it is authorized as `personal_user` |
| Viewer asks for a password | no `~/.vnc/<account>.passwd`, or it is out of date |
| macOS: "needs TigerVNC Viewer" | install TigerVNC Viewer.app, or set `SITE_VIEWER` |
| "already open" but nothing works | `crs-tunnel close --session S --site-config ...`, then retry |
| Overlay error at start | the message names the file and the colliding name, port or display |

## Caltech notes

The Caltech ROC computer is novacr02, account `mu2ecr`.

- **Identity:** the Kerberos identity the DAQ coordinator authorized as
  `mu2eshift`. Its name and keytab are set only on the ROC computer, in
  `~/.config/mu2edaq-remote-site/caltech.env`, never in this repository.
- **Not installed:** `trig-main`, because that identity is not authorized as
  `mu2etrig`.
- **Old launchers:** the earlier caltech-roc scripts made launchers with the
  same file names (`mu2e-*.desktop`) but no marker. The first install on
  novacr02 therefore needs `install.sh --site caltech --replace`.
- **Viewer:** without TigerVNC on novacr02, use the RealVNC viewer that came
  with the NOvA scripts. Set it in `~/.config/mu2edaq-remote-site/caltech.env`:

  ```bash
  SITE_VIEWER="$HOME/Documents/NovaCR/bin/vncviewer"
  ```
