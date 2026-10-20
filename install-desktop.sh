#!/bin/bash
# Install Emcomm-CNC on a Debian or Ubuntu computer that's already in use
# ("desktop mode"), for the person running it:
#
#   sudo ./install-desktop.sh
#
# Adds Emcomm-CNC to the app menu and an Emcomm-CNC session to the login screen.
# The desktop, login, boot and clock are left as they are, and apps install from
# their tiles. uninstall-desktop.sh takes it all away again. Running this again
# updates it (as does Settings > Update station).
set -euo pipefail

DEST=/opt/emcomm-station

if [ "$(id -u)" != 0 ]; then
  echo "Run it with sudo: sudo $0" >&2
  exit 1
fi
user="${SUDO_USER:-}"
if [ -z "$user" ] || [ "$user" = root ]; then
  echo "Run it with sudo from your own account (not as root), so it's set up for you." >&2
  exit 1
fi
# shellcheck source=/dev/null
. /etc/os-release
case " ${ID:-} ${ID_LIKE:-} " in
  *" debian "*|*" ubuntu "*) ;;
  *) echo "This needs Debian, Ubuntu or a system built on them (found ${PRETTY_NAME:-unknown})." >&2; exit 1 ;;
esac
if [ "$(dpkg --print-architecture)" != amd64 ]; then
  echo "Note: some apps (VARA, Pat, ardopcf) are only set up for 64-bit PCs; the rest should work." >&2
fi

# What was here before, so uninstall-desktop.sh can tell what Emcomm-CNC added.
mkdir -p /etc/emcomm/before
[ -f /etc/emcomm/before/packages ] || dpkg-query -W -f '${Package}\n' | sort > /etc/emcomm/before/packages
[ -f /etc/emcomm/before/usr-local-bin ] || ls /usr/local/bin > /etc/emcomm/before/usr-local-bin

echo "== Installing Ansible and git =="
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ansible-core git python3-apt

# The playbook lives where only root can change it, so the launcher's Update
# station (which runs it as root) can't be used to run anything else. A copy of
# this folder, git history and all, so Update station pulls from the same place.
here="$(cd "$(dirname "$0")" && pwd)"
if [ "$here" != "$DEST" ]; then
  echo "== Copying the playbook to $DEST =="
  rm -rf "$DEST"
  cp -a "$here" "$DEST"
  chown -R root:root "$DEST"
  chmod -R go-w "$DEST"
fi

mkdir -p "$DEST/host_vars"
cat > "$DEST/host_vars/localhost.yml" <<VARS
# Written by install-desktop.sh: Emcomm-CNC on a computer already in use, for $user.
station_mode: desktop
station_user: $user
VARS

echo "== Setting up Emcomm-CNC for $user =="
cd "$DEST"
ansible-playbook site.yml

echo
echo "Emcomm-CNC is installed. Open it from your app menu (Emcomm-CNC), or pick the"
echo "Emcomm-CNC session on the login screen for the full-screen station."
echo "Log out and back in once first, so you can use the radio's serial ports and the SDR."
echo "To take it off again: sudo $DEST/uninstall-desktop.sh"
