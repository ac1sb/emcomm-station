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
- **Launcher:** the home screen above. Works by touch, mouse or keyboard: Tab moves
  between buttons, 1–9 open tiles, Esc/F1 goes Home, F2 Diagnostics, F3 Settings,
  F4 Logs. A tile for an app that isn't installed says "tap to install". To use
  your own picture on a tile, long-press it (or right-click, or press the Menu key)
  and pick an SVG, PNG or JPG from a USB stick or `~/Downloads`; "Use the standard
  icon" puts it back. **Light mode** / **Dark mode** in Settings switches the colours
  (light is easier to read in daylight); the choice is remembered.
- **Radio apps:** JS8Call, WSJT-X, fldigi with flamp, flmsg (ICS-213 forms), Pat for
  Winlink mail, VARA HF and VARA FM (under Wine), ARDOP (ardopcf) and Direwolf for
  packet. Every app reaches the radio through `rigctld`, so CAT and PTT are set up
  once, in Settings. Callsign and grid are filled in for each app.
- **Logs:** JS8Call messages and activity, WSJT-X contacts and Winlink mail in one
  place, plus a box to note a voice or other contact. Notes get the UTC time,
  frequency and mode from the radio.
- **Update station** (in Settings): downloads the latest Emcomm-CNC and installs
  anything missing, with progress on screen. No terminal or password needed.
- **Diagnostics:** USB devices with vendor:product IDs, radio ports, sound cards,
  services, recent USB events, a read-frequency check and a 2-second PTT test.
  The same report is available over SSH with `emcomm-diag`.

![Home screen in light mode](docs/home-light.png)

![Settings](docs/settings.png)

![Diagnostics](docs/diag.png)

![Logs](docs/logs.png)

## Using the apps

- **Winlink over VARA:** tap VARA HF (or FM) first. The first tap sets up Wine and
  downloads VARA from Winlink, or uses a VARA setup .zip from a USB stick or
  `~/Downloads`. VARA uses the default sound card, which is the radio. Then
  open Winlink mail (Pat), which keys the radio through `rigctld`. On first use, set
  your Winlink password in Pat's configuration page.
- **Winlink over ARDOP or packet:** start ARDOP or Packet from their tiles, then use
  Pat as above.
- **JS8Call and WSJT-X** start with your callsign, grid and rig control filled in
  (radio "Hamlib NET rigctl", PTT by CAT).
- **Audio:** whenever the radio's sound card is plugged in, the station makes it the
  default speaker and microphone, so apps left on their "default" sound device use
  the radio. (`emcomm-audio-default` does this; Diagnostics shows the current default.)
- **fldigi:** in Configure > Rig control > Hamlib, pick "Hamlib NET rigctl" with
  device `localhost:4532`, and pick the sound card under Audio.

Running more than one sound-card app at a time doesn't work: close one before
opening the next.

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

To update later, tap **Update station** in Settings, or re-run the playbook as root.
Either way only what's different changes, and the settings saved on the Settings
screen are kept.

The station user (`radio`) has no password and can't use `sudo` or `apt` in the
terminal. That's deliberate: installing apps and updating go through the launcher's
buttons instead. For anything else, log in over SSH with the admin account you made
when installing Debian.

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
