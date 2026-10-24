# Radio presets

Any radio Hamlib supports can be set up from the station's Settings screen:
pick the manufacturer and model, then the CAT port, PTT and sound card from the
devices that are plugged in. No file here is needed for that.

The files in this folder are optional **presets**: tested combinations that fill
in all of those fields at once, so a radio can be set up before it's plugged in.
Pick one with New… under Profile in Settings > Radio. Each radio you set up is kept
as a profile there, so switching between radios is one pick and Save.

To add a preset, copy one of these and change:

| Key | What it is |
|---|---|
| `radio_name` | Name shown in Settings |
| `rig_model` | Hamlib model number (`rigctl -l`) |
| `cat_baud` | CAT serial speed; must match the radio's CAT RATE menu |
| `cat_match` | USB match for the CAT serial port: `vendor`, `product`, optional `serial` and `interface` |
| `ptt_method` | `RTS`, `DTR`, `CAT` or `NONE` (VOX) |
| `ptt_match` | USB match for a separate PTT port (RTS/DTR), `cat` to key RTS/DTR on the CAT port, or `null` |
| `audio_match` | USB match for the sound card, or `null` to pick it in Settings |
| `data_mode` | Mode digital apps put the radio in: `data` (DATA-U), `usb`, or `none` (leave it, as for VHF FM) |

USB IDs (`vendor`, `product`) are the 4-digit hex numbers Diagnostics shows next to
each USB device.

Whatever is chosen, the station gives the devices stable names so apps never depend
on USB plug order:

- `/dev/rig-cat`: CAT serial port
- `/dev/rig-ptt`: PTT serial port (when PTT uses a separate port)
- ALSA card `rigaudio`: the radio's sound card
