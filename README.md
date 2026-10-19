# Emcomm-CNC

*Emcomm command and control.*

Turns a fresh minimal Debian 13 install into a dedicated emcomm station: it boots
straight into a full-screen touch launcher for the radio apps, with no desktop
environment.

![Home screen](docs/home.png)

## What's in it so far

- **Base system:** a `radio` user, SSH for remote troubleshooting, PipeWire audio.
- **Settings screen:** callsign, grid, radio, CAT baud rate and PTT method, set on
  the station itself. It opens automatically on first boot. Saving re-applies the
  radio setup and restarts rig control; no files to edit.
- **Radio profiles** (`radios/`): Yaesu FT-891 with a Digirig, and Yaesu FT-710.
  The selected profile gives the radio's devices stable names (`/dev/rig-cat`,
  `/dev/rig-ptt`, ALSA card `rigaudio`), and a Hamlib `rigctld` service starts when
  the radio is plugged in. Every app talks to the radio through `rigctld` on
  `127.0.0.1:4532`.
- **Kiosk:** auto-login on the console, X with Openbox only, screen blanking off.
- **Launcher:** the home screen above. Tiles stay greyed out until the app is installed.
- **Diagnostics:** USB devices with vendor:product IDs, radio ports, sound cards,
  services, recent USB events, a read-frequency check and a 2-second PTT test.
  The same report is available over SSH with `emcomm-diag`.

![Settings](docs/settings.png)

![Diagnostics](docs/diag.png)

The radio apps themselves (Pat, VARA, JS8Call, fldigi/flmsg, Direwolf, ARDOP, WSJT-X)
come next.

## Install

1. Install Debian 13 with only "SSH server" and "standard system utilities" selected
   (no desktop). Create any admin user you like.
2. As root (`su -`):

   ```sh
   apt install -y ansible git
   git clone https://github.com/ac1sb/emcomm-station.git
   cd emcomm-station
   ansible-playbook site.yml
   reboot
   ```

3. The station boots into Settings. Enter your callsign and grid, pick your radio,
   check the baud rate matches the radio's CAT RATE menu, and save.
4. Plug in the radio and open Diagnostics to check the radio, sound card and PTT.

Re-run the playbook any time to update the station. It only changes what's
different and keeps the settings saved on the Settings screen.

Ubuntu Server 24.04 should also work if your hardware needs newer drivers.

## Testing in a VM

A VM is fine for checking the build, the kiosk and the launcher. Snapshot it before
the first run. For on-air testing use real hardware: USB audio passed through to a
VM tends to drop samples, which VARA and FT8 don't tolerate.

## Adding a radio

See [radios/README.md](radios/README.md).

## Development

```sh
pip install ansible-core ansible-lint shellcheck-py pyyaml
ansible-playbook site.yml --syntax-check
ansible-lint
python3 tests/test_apply_settings.py
```
