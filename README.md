# Emcomm-CNC

*Emcomm command and control.*

Turns a fresh minimal Debian 13 install into a dedicated emcomm station: it boots
straight into a full-screen touch launcher for the radio apps, with no desktop
environment.

![Home screen](docs/home.png)

## What's in it so far

- **Base system:** a `radio` user, SSH for remote troubleshooting, PipeWire audio.
- **Settings screen:** callsign, grid and the radio, set on the station itself and
  opened automatically on first boot. Any radio Hamlib supports can be picked by
  manufacturer and model; the CAT port, PTT port and sound card are picked from the
  USB devices that are plugged in, with a Rescan button. Saving gives those devices
  stable names (`/dev/rig-cat`, `/dev/rig-ptt`, ALSA card `rigaudio`) and restarts
  Hamlib's `rigctld`, which every app uses to reach the radio on `127.0.0.1:4532`.
  `rigctld` starts by itself whenever the radio is plugged in.
- **Presets** (`radios/`): Yaesu FT-891 with a Digirig, and Yaesu FT-710. Optional
  shortcuts that fill in every radio field at once, even before the radio is plugged in.
- **Kiosk:** auto-login on the console, X with Openbox only, screen blanking off.
- **Launcher:** the home screen above. Tiles stay greyed out until the app is installed.
  Works by touch, mouse or keyboard: Tab moves between buttons, 1–9 open tiles,
  Esc/F1 goes Home, F2 opens Diagnostics, F3 opens Settings.
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

3. Plug in the radio. The station boots into Settings: enter your callsign and grid,
   pick a preset or your radio's manufacturer and model, pick the CAT port and sound
   card, check the baud rate matches the radio's CAT RATE menu, and save.
4. Plug in the radio and open Diagnostics to check the radio, sound card and PTT.

Re-run the playbook any time to update the station. It only changes what's
different and keeps the settings saved on the Settings screen.

Ubuntu Server 24.04 should also work if your hardware needs newer drivers.

## Testing in a VM

A VM is fine for checking the build, the kiosk and the launcher. Snapshot it before
the first run. For on-air testing use real hardware: USB audio passed through to a
VM tends to drop samples, which VARA and FT8 don't tolerate.

## Adding a preset

No file is needed to use a radio. To add a one-tap preset, see
[radios/README.md](radios/README.md).

## Development

```sh
pip install ansible-core ansible-lint shellcheck-py pyyaml
ansible-playbook site.yml --syntax-check
ansible-lint
python3 tests/test_apply_settings.py
```
