# emcomm-station

Turns a fresh minimal Debian 12 install into a dedicated emcomm station: it boots
straight into a full-screen touch launcher for the radio apps, with no desktop
environment.

![Home screen](docs/home.png)

## What's in it so far

- **Base system:** a `radio` user, SSH for remote troubleshooting, PipeWire audio.
- **Radio profiles** (`radios/`): Yaesu FT-891 with a Digirig, and Yaesu FT-710.
  Each one sets up stable device names (`/dev/rig-cat`, `/dev/rig-ptt`, ALSA card
  `rigaudio`) and a Hamlib `rigctld` service that starts when the radio is plugged in.
  Every app talks to the radio through `rigctld` on `127.0.0.1:4532`.
- **Kiosk:** auto-login on the console, X with Openbox only, screen blanking off.
- **Launcher:** the home screen above. Tiles stay greyed out until the app is installed.
- **Diagnostics:** USB devices with vendor:product IDs, radio ports, sound cards,
  services, recent USB events, a read-frequency check and a 2-second PTT test.
  The same report is available over SSH with `emcomm-diag`.

![Diagnostics](docs/diag.png)

The radio apps themselves (Pat, VARA, JS8Call, fldigi/flmsg, Direwolf, ARDOP, WSJT-X)
come next.

## Install

1. Install Debian 12 with only "SSH server" and "standard system utilities" selected
   (no desktop). Create any admin user you like.
2. As root (`su -`):

   ```sh
   apt install -y ansible git
   git clone https://github.com/ac1sb/emcomm-station.git
   cd emcomm-station
   ```

3. Edit `group_vars/all.yml`: callsign, grid, and `station_radio`.
4. Set the radio's CAT RATE menu to 38400.
5. Run the build and reboot:

   ```sh
   ansible-playbook site.yml
   reboot
   ```

Re-run the playbook any time you change settings. It only changes what's different.

## Testing in a VM

A VM is fine for checking the build, the kiosk and the launcher. Snapshot it before
the first run. For on-air testing use real hardware: USB audio passed through to a
VM tends to drop samples, which VARA and FT8 don't tolerate.

## Adding a radio

See [radios/README.md](radios/README.md).
