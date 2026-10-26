#!/bin/bash
# Take Emcomm-CNC off a computer it was put on with install-desktop.sh:
#
#   sudo /opt/emcomm-station/uninstall-desktop.sh [--packages]
#
# Removes its programs, services, menu entry, login session and settings, and
# puts back the gpsd settings it changed. With --packages it also offers to
# remove the packages it installed (it lists them and asks first). Your own
# files are left: ~/.config/emcomm, recordings, frequency lists, app settings.
set -uo pipefail

DEST=/opt/emcomm-station
BEFORE=/etc/emcomm/before

if [ "$(id -u)" != 0 ]; then
  echo "Run it with sudo: sudo $0" >&2
  exit 1
fi
if [ "$(cat /etc/emcomm/mode 2>/dev/null)" = kiosk ]; then
  echo "This computer was built as a dedicated station (kiosk mode); this only undoes desktop mode." >&2
  exit 1
fi
packages=false
[ "${1:-}" = --packages ] && packages=true

echo "== Stopping Emcomm-CNC's services =="
for unit in emcomm-nwr emcomm-adsb emcomm-igate rigctld rigctld2; do
  systemctl disable --now "$unit" 2>/dev/null
  rm -f "/etc/systemd/system/$unit.service"
done
systemctl daemon-reload
rm -f /etc/udev/rules.d/99-emcomm-radio.rules /etc/udev/rules.d/99-emcomm-radio2.rules /etc/udev/rules.d/99-emcomm-vhf.rules
udevadm control --reload 2>/dev/null

echo "== Putting back settings it changed =="
if [ -f "$BEFORE/gpsd" ]; then
  cp "$BEFORE/gpsd" /etc/default/gpsd
elif grep -q "Emcomm-CNC" /etc/default/gpsd 2>/dev/null; then
  # gpsd came with Emcomm-CNC: its standard settings (find GPS receivers by itself).
  printf 'START_DAEMON="true"\nUSBAUTO="true"\nDEVICES=""\nGPSD_OPTIONS=""\n' > /etc/default/gpsd
fi
systemctl try-restart gpsd 2>/dev/null
rm -f /etc/modprobe.d/emcomm-rtl-sdr.conf /etc/sudoers.d/emcomm-update /etc/sudoers.d/emcomm-settings

echo "== Removing its programs, menu entry and login session =="
rm -f /usr/local/bin/emcomm-* /usr/local/sbin/emcomm-*
# Programs it put in /usr/local/bin, unless they were there before.
for prog in ardopcf winetricks chirp contact meshcore-cli meshtastic-desktop meshy; do
  if ! grep -qx "$prog" "$BEFORE/usr-local-bin" 2>/dev/null; then
    rm -f "/usr/local/bin/$prog"
  fi
done
rm -f /usr/share/applications/emcomm-cnc.desktop /usr/share/xsessions/emcomm-cnc.desktop \
  /usr/share/icons/hicolor/scalable/apps/emcomm-cnc.svg
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null
rm -rf /usr/share/emcomm /opt/emcomm /var/cache/emcomm
# meshtastic: Meshtastic's command line through emcomm-mesh-check, unless it was someone else's.
if [ "$(readlink /usr/local/bin/meshtastic 2>/dev/null)" = /usr/local/bin/emcomm-mesh-check ]; then
  rm -f /usr/local/bin/meshtastic
fi
rm -f /var/log/emcomm-update.log /var/log/emcomm-update.log.1

if $packages && [ -f "$BEFORE/packages" ]; then
  added=$(comm -13 "$BEFORE/packages" <(dpkg-query -W -f '${Package}\n' | sort))
  if [ -z "$added" ]; then
    echo "No packages were added since Emcomm-CNC was installed."
  else
    echo
    echo "Packages added since Emcomm-CNC was installed (including any you added yourself since):"
    echo "$added" | tr '\n' ' ' | fold -s -w 78
    echo
    read -r -p "Remove all of these? [y/N] " answer
    if [ "$answer" = y ] || [ "$answer" = Y ]; then
      # shellcheck disable=SC2086
      apt-get purge -y $added && apt-get autoremove -y
    fi
  fi
fi

rm -rf /etc/emcomm "$DEST"
echo
echo "Emcomm-CNC is removed."
$packages || echo "The packages it installed are still there; run with --packages to see and remove them."
echo "Your own files are kept: ~/.config/emcomm, ~/Recordings, ~/Scanner channels.csv and the apps' settings."
for app in org.meshtastic.MeshtasticDesktop page.codeberg.sesivany.Meshy; do
  if flatpak info --system "$app" >/dev/null 2>&1; then
    echo "$app is still installed (Flatpak); remove it with: flatpak uninstall $app"
  fi
done
echo "Your account is still in the dialout, plugdev and bluetooth groups (harmless; for radios and USB devices)."
