# Launcher icons and launchers for remote-site/install.sh. Sourced, not run.
# Needs lib/common.sh first (REMOTE_SITE_DIR, SITE_NAME, fail). bash 3.2
# compatible.
#
# One launcher per name: a session name opens that screen (crs-screen), the
# name "nodes" opens the DAQ machine picker (crs-nodes).
#   Linux: ~/.local/share/applications/mu2e-<name>.desktop, Terminal=true,
#          icon ~/.local/share/icons/mu2e/mu2e-<name>.svg, and a copy of the
#          .desktop in ~/Desktop when that folder exists
#   macOS: ~/Applications/Mu2e/Mu2e <name>.app, which opens Terminal on a
#          .command file; icon drawn from the same SVG (AppKit, sips, iconutil)
#
# Every file carries a marker naming the site. The installer only replaces
# or removes files with this site's marker, never symbolic links, and
# replaces files without a marker only with --replace (LAUNCHER_REPLACE=1).
# preflight_launchers checks every target before anything is written.
# Every file written is appended to $INSTALLED_LIST for --uninstall.

LAUNCHER_MARKER="X-Mu2e-Remote-Site"
LAUNCHER_REPLACE=${LAUNCHER_REPLACE:-}

# icon_label NAME: short text drawn on a screen icon (shift-main -> SHIFT,
# cr01 -> CR1)
icon_label() {
    local label
    case $1 in
        cr0?)   label=CR${1#cr0} ;;
        cr*)    label=CR${1#cr} ;;
        *-main) label=${1%-main} ;;
        *)      label=$1 ;;
    esac
    echo "$label" | tr '[:lower:]' '[:upper:]' | cut -c1-5
}

# icon_svg NAME: the icon picture. A monitor with the label (blue: desks,
# teal: control room wall screens crNN) or a terminal for "nodes". Text is
# placed with explicit offsets, not dominant-baseline, so librsvg (Linux)
# and AppKit (macOS) draw it the same way. The marker comment is line 2.
icon_svg() {
    if [ "$1" = nodes ]; then
        cat << EOF
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
<!-- $LAUNCHER_MARKER=$SITE_NAME -->
  <rect x="4" y="4" width="120" height="120" rx="24" fill="#2C2C2A"/>
  <rect x="16" y="22" width="96" height="84" rx="8" fill="#000000" stroke="#FFFFFF" stroke-width="4"/>
  <line x1="16" y1="38" x2="112" y2="38" stroke="#FFFFFF" stroke-width="4"/>
  <text x="28" y="73" font-family="Menlo, DejaVu Sans Mono, monospace" font-weight="bold" font-size="26" fill="#FF6C0C">&gt;_</text>
  <text x="64" y="98" font-family="Helvetica, DejaVu Sans, Arial, sans-serif" font-weight="bold" font-size="18" fill="#FFFFFF" text-anchor="middle">DAQ</text>
</svg>
EOF
        return
    fi
    local label bg size
    label=$(icon_label "$1")
    case $1 in cr*) bg="#0F6E56" ;; *) bg="#1F4E8C" ;; esac
    size=28
    [ ${#label} -ge 4 ] && size=24
    [ ${#label} -ge 5 ] && size=20
    cat << EOF
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
<!-- $LAUNCHER_MARKER=$SITE_NAME -->
  <rect x="4" y="4" width="120" height="120" rx="24" fill="$bg"/>
  <rect x="16" y="24" width="96" height="64" rx="7" fill="#FFFFFF"/>
  <rect x="22" y="30" width="84" height="52" rx="3" fill="#10233D"/>
  <rect x="56" y="88" width="16" height="10" fill="#FFFFFF"/>
  <rect x="40" y="98" width="48" height="6" rx="3" fill="#FFFFFF"/>
  <text x="64" y="$((56 + size * 35 / 100))" font-family="Helvetica, DejaVu Sans, Arial, sans-serif" font-weight="bold" font-size="$size" fill="#FFFFFF" text-anchor="middle">$label</text>
</svg>
EOF
}

# launcher_command NAME: the command a launcher runs, one argument per line
launcher_command() {
    if [ "$1" = nodes ]; then
        printf '%s\n' "$REMOTE_SITE_DIR/crs-nodes" --site "$SITE_NAME"
    else
        printf '%s\n' "$REMOTE_SITE_DIR/crs-screen" --site "$SITE_NAME" "$1"
    fi
}

launcher_title() {
    if [ "$1" = nodes ]; then echo "Mu2e DAQ nodes"; else echo "Mu2e $1"; fi
}

launcher_comment() {
    if [ "$1" = nodes ]; then
        echo "Log in to a Mu2e DAQ machine (ssh-selector)"
    else
        echo "Mu2e control room screen $1 ($SITE_TITLE)"
    fi
}

launcher_platform() {
    case $(uname -s) in
        Darwin) echo macos ;;
        Linux) echo linux ;;
        *) echo other ;;
    esac
}

linux_apps_dir() { echo "${XDG_DATA_HOME:-$HOME/.local/share}/applications"; }
linux_icons_dir() { echo "${XDG_DATA_HOME:-$HOME/.local/share}/icons/mu2e"; }
mac_bundle() { echo "$HOME/Applications/Mu2e/$(launcher_title "$1").app"; }

# owned FILE MARKERLINE: FILE is a regular file (not a link) with that line
owned() { [ -f "$1" ] && [ ! -L "$1" ] && grep -qxF "$2" "$1" 2> /dev/null; }

# owned_bundle DIR: a macOS bundle this installer made for this site. The
# bundle, Contents and Resources must be real directories and the marker a
# regular file, so nothing reached through a symbolic link counts as ours.
owned_bundle() {
    local m="$1/Contents/Resources/$LAUNCHER_MARKER"
    [ -d "$1" ] && [ ! -L "$1" ] \
        && [ -d "$1/Contents" ] && [ ! -L "$1/Contents" ] \
        && [ -d "$1/Contents/Resources" ] && [ ! -L "$1/Contents/Resources" ] \
        && [ -f "$m" ] && [ ! -L "$m" ] \
        && [ "$(cat "$m" 2> /dev/null)" = "$SITE_NAME" ]
}

# empty_skeleton DIR: a real directory holding only directories (no files,
# no links), e.g. what is left after a removal failed at its last rmdir.
# Removing it with rmdir cannot lose data.
empty_skeleton() {
    [ -d "$1" ] && [ ! -L "$1" ] && [ -z "$(find "$1" ! -type d -print 2> /dev/null | head -1)" ]
}

# launcher_targets NAME: "kind<TAB>path" for each file NAME's launcher writes
launcher_targets() {
    local id=mu2e-$1
    case $(launcher_platform) in
        linux)
            printf 'desktop\t%s\n' "$(linux_apps_dir)/$id.desktop"
            printf 'svg\t%s\n' "$(linux_icons_dir)/$id.svg"
            [ -d "$HOME/Desktop" ] && printf 'desktop\t%s\n' "$HOME/Desktop/$id.desktop"
            ;;
        macos)
            printf 'bundle\t%s\n' "$(mac_bundle "$1")"
            ;;
    esac
    return 0
}

# target_problem KIND PATH: print why PATH may not be written, or nothing
target_problem() {
    local kind=$1 path=$2
    if [ -L "$path" ]; then
        echo "symbolic link, never replaced: $path"
        return
    fi
    [ -e "$path" ] || return 0
    case $kind in
        desktop) owned "$path" "$LAUNCHER_MARKER=$SITE_NAME" && return 0 ;;
        svg) owned "$path" "<!-- $LAUNCHER_MARKER=$SITE_NAME -->" && return 0 ;;
        bundle) owned_bundle "$path" && return 0 ;;
    esac
    if [ -n "$LAUNCHER_REPLACE" ] && [ "$kind" != bundle ] && [ -f "$path" ]; then
        return 0
    fi
    if [ -n "$LAUNCHER_REPLACE" ] && [ "$kind" = bundle ] && [ -d "$path" ]; then
        return 0
    fi
    echo "not made by this installer for site $SITE_NAME: $path"
}

# preflight_launchers NAME...: check the platform, the paths that go into
# launchers, and every target file, before anything is written. Fails with
# the full list of problems.
preflight_launchers() {
    local platform problems n line
    platform=$(launcher_platform)
    [ "$platform" != other ] || fail "launchers are made for Linux and macOS only"
    if [ "$platform" = linux ]; then
        case $REMOTE_SITE_DIR in
            *[\"\`\$\\]*|*"
"*)
                fail "this checkout's path cannot go in a .desktop Exec line (quote, \$, backtick, backslash or newline): $REMOTE_SITE_DIR" ;;
        esac
    fi
    problems=
    for n in "$@"; do
        while IFS="$(printf '\t')" read -r kind path; do
            line=$(target_problem "$kind" "$path")
            [ -z "$line" ] || problems="$problems
  $line"
        done < <(launcher_targets "$n")
    done
    if [ -n "$problems" ]; then
        echo "Launcher files in the way:$problems" >&2
        fail "nothing was written; move these away, or rerun with --replace to overwrite files (never symbolic links) that this installer did not make"
    fi
}

record() {
    [ -z "${INSTALLED_LIST:-}" ] || echo "$1" >> "$INSTALLED_LIST" \
        || fail "cannot write $INSTALLED_LIST"
}

# -- Linux ---------------------------------------------------------------------

install_linux_launcher() {
    local name=$1 apps icons id exec_line a
    apps=$(linux_apps_dir)
    icons=$(linux_icons_dir)
    id=mu2e-$name
    mkdir -p "$apps" "$icons" || fail "cannot create $apps or $icons"
    icon_svg "$name" > "$icons/$id.svg" || fail "cannot write $icons/$id.svg"
    record "$icons/$id.svg"
    # preflight_launchers has rejected paths that need escaping in Exec
    exec_line=
    while IFS= read -r a; do
        exec_line="$exec_line${exec_line:+ }\"$a\""
    done < <(launcher_command "$name")
    cat > "$apps/$id.desktop" << EOF || fail "cannot write $apps/$id.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Terminal=true
Icon=$icons/$id.svg
Name=$(launcher_title "$name")
Comment=$(launcher_comment "$name")
Exec=$exec_line
Categories=Network;RemoteAccess;
$LAUNCHER_MARKER=$SITE_NAME
EOF
    record "$apps/$id.desktop"
    echo "  $apps/$id.desktop"
    if [ -d "$HOME/Desktop" ]; then
        cp "$apps/$id.desktop" "$HOME/Desktop/$id.desktop" \
            && chmod +x "$HOME/Desktop/$id.desktop" \
            || fail "cannot write $HOME/Desktop/$id.desktop"
        record "$HOME/Desktop/$id.desktop"
    fi
}

# -- macOS ---------------------------------------------------------------------

# make_icns SVG ICNS: AppKit draws the SVG at 1024 px, sips scales it to the
# ten iconset sizes, iconutil packs them.
make_icns() {
    local tmp s
    tmp=$(mktemp -d "${TMPDIR:-/tmp}/mu2e-icon.XXXXXX") || return 1
    osascript -l JavaScript "$REMOTE_SITE_DIR/lib/svg2png.js" "$1" "$tmp/icon.png" 1024 \
        || { rm -rf "$tmp"; return 1; }
    mkdir "$tmp/icon.iconset"
    for s in 16 32 128 256 512; do
        sips -z $s $s "$tmp/icon.png" --out "$tmp/icon.iconset/icon_${s}x${s}.png" > /dev/null \
            && sips -z $((s * 2)) $((s * 2)) "$tmp/icon.png" \
                --out "$tmp/icon.iconset/icon_${s}x${s}@2x.png" > /dev/null \
            || { rm -rf "$tmp"; return 1; }
    done
    iconutil -c icns "$tmp/icon.iconset" -o "$2" || { rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"
}

install_mac_launcher() {
    local name=$1 bundle title ident a problem
    title=$(launcher_title "$name")
    bundle=$(mac_bundle "$name")
    ident=org.mu2e.remote-site.$(echo "$SITE_NAME.$name" | tr -c 'A-Za-z0-9.\n' '-')
    # Checked again here in case this function is used without preflight
    problem=$(target_problem bundle "$bundle")
    [ -z "$problem" ] || fail "$problem"
    rm -rf "$bundle"
    mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources" \
        || fail "cannot create $bundle"
    echo "$SITE_NAME" > "$bundle/Contents/Resources/$LAUNCHER_MARKER" \
        || fail "cannot write $bundle"
    record "$bundle"

    {
        echo '#!/bin/bash'
        echo 'export CRS_FROM_LAUNCHER=1'
        printf 'exec'
        while IFS= read -r a; do printf ' %q' "$a"; done < <(launcher_command "$name")
        echo
    } > "$bundle/Contents/Resources/run.command" || fail "cannot write $bundle"
    cat > "$bundle/Contents/MacOS/launcher" << 'EOF' || fail "cannot write $bundle"
#!/bin/bash
# Open Terminal on run.command so prompts and errors are visible.
exec /usr/bin/open -a Terminal "$(cd "$(dirname "$0")/../Resources" && pwd)/run.command"
EOF
    chmod +x "$bundle/Contents/MacOS/launcher" "$bundle/Contents/Resources/run.command" \
        || fail "cannot make $bundle executable"

    cat > "$bundle/Contents/Info.plist" << EOF || fail "cannot write $bundle"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$title</string>
  <key>CFBundleDisplayName</key><string>$title</string>
  <key>CFBundleIdentifier</key><string>$ident</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
EOF
    icon_svg "$name" > "$bundle/Contents/Resources/icon.svg" || fail "cannot write $bundle"
    make_icns "$bundle/Contents/Resources/icon.svg" "$bundle/Contents/Resources/icon.icns" \
        || echo "  (could not make the icon for $title; it gets the default icon)"
    local lsregister=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
    [ -x "$lsregister" ] && "$lsregister" -f "$bundle" > /dev/null 2>&1
    echo "  $bundle"
}

install_launcher() {
    case $(launcher_platform) in
        macos) install_mac_launcher "$1" ;;
        linux) install_linux_launcher "$1" ;;
        *) fail "launchers are made for Linux and macOS only" ;;
    esac
}

# bundle_entries BUNDLE: every entry of the bundle except the marker file
# and the two directories that hold it, deepest level last
bundle_entries() {
    local b=$1 res="$1/Contents/Resources" e
    for e in "$res"/* "$res"/.[!.]* "$b"/Contents/* "$b"/Contents/.[!.]* "$b"/* "$b"/.[!.]*; do
        [ -e "$e" ] || [ -L "$e" ] || continue
        case $e in "$b/Contents"|"$res"|"$res/$LAUNCHER_MARKER") continue ;; esac
        printf '%s\n' "$e"
    done
}

# remove_bundle BUNDLE: delete an owned bundle (owned_bundle checked first)
# with its marker last, so a partial failure leaves the marker and a retry
# still recognizes the bundle. Each entry is removed with rm -rf on the
# entry itself, which removes a symbolic link, never what it points to.
remove_bundle() {
    local b=$1 e
    while IFS= read -r e; do
        rm -rf "$e" 2> /dev/null
    done < <(bundle_entries "$b")
    [ -z "$(bundle_entries "$b")" ] || return 1
    rm -f "$b/Contents/Resources/$LAUNCHER_MARKER" \
        && rmdir "$b/Contents/Resources" "$b/Contents" "$b" 2> /dev/null
}

# uninstall_recorded: remove what INSTALLED_LIST names, only where the file
# still carries this site's marker. Paths that are gone or no longer ours
# are dropped from the list; paths that could not be removed stay in it, so
# a later --uninstall can retry. Returns 1 if anything could not be removed.
uninstall_recorded() {
    local path keep failed=0
    keep=$(mktemp "${INSTALLED_LIST}.XXXXXX") || fail "cannot write next to $INSTALLED_LIST"
    while IFS= read -r path; do
        [ -n "$path" ] || continue
        case $path in
            *.app)
                if owned_bundle "$path"; then
                    remove_bundle "$path"
                elif empty_skeleton "$path"; then
                    # left by an earlier removal that failed at its last rmdir
                    find "$path" -type d -empty -delete 2> /dev/null
                else
                    continue
                fi ;;
            *.desktop) owned "$path" "$LAUNCHER_MARKER=$SITE_NAME" || continue
                   rm -f "$path" 2> /dev/null ;;
            *.svg) owned "$path" "<!-- $LAUNCHER_MARKER=$SITE_NAME -->" || continue
                   rm -f "$path" 2> /dev/null ;;
            *) continue ;;
        esac
        if [ -e "$path" ] || [ -L "$path" ]; then
            echo "  could not remove $path" >&2
            echo "$path" >> "$keep"
            failed=1
        else
            echo "  removed $path"
        fi
    done < "$INSTALLED_LIST"
    if [ "$failed" = 1 ]; then
        mv "$keep" "$INSTALLED_LIST" || fail "cannot update $INSTALLED_LIST"
        return 1
    fi
    rm -f "$keep" "$INSTALLED_LIST"
    return 0
}
