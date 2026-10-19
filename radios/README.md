# Radio profiles

Each file here describes one radio setup. Pick one with `station_radio` in
`group_vars/all.yml` (the file name without `.yml`).

To add a radio, copy the closest profile and change:

| Key | What it is | How to find it |
|---|---|---|
| `rig_model` | Hamlib model number | `rigctl -l \| grep -i <model>` |
| `cat_baud` | CAT serial speed | Must match the radio's CAT RATE menu |
| `cat_udev_match` | udev match for the CAT serial port | Diagnostics → USB devices, or `udevadm info /dev/ttyUSB0` |
| `ptt_method` | `RTS`, `DTR` or `CAT` | `CAT` if the radio keys over CAT; `RTS` for Digirig |
| `ptt_udev_match` | udev match for the PTT serial port (RTS/DTR only) | Digirig: `10c4:ea60` |
| `audio_udev_match` | udev match for the sound card | Diagnostics → USB devices |

The USB IDs in the shipped profiles are the usual ones for these devices.
Check them against Diagnostics on first boot; if a device shows up under a different ID, update the profile and re-run the playbook.

The station creates stable names, so apps never depend on USB plug order:

- `/dev/rig-cat`: CAT serial port
- `/dev/rig-ptt`: PTT serial port (RTS/DTR profiles only)
- ALSA card `rigaudio`: the radio's sound card
