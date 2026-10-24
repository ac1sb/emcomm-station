# Emcomm-CNC operations guide

*How to operate the station: what each app is for, which apps work together, what
to open first, and the radio, rig and audio settings for each one.*

This guide is for an operator who knows radio but has never used this station.
Nothing is assumed about Linux. Building and installing the station are covered in
the [README](../README.md); this guide starts with the station already set up.

> **Draft.** Sections marked ⚠ **Not yet tested on this station** describe
> features that work in the build but have not yet been run with real radios.
> Treat the steps as right, and the results as unconfirmed.

Every time and date the station writes (forms, logs, recordings, net logs) is in
**UTC**. The top bar shows local time and UTC side by side.

## Contents

1. [The station at a glance](#1-the-station-at-a-glance)
2. [Before you operate: the start-up check](#2-before-you-operate-the-start-up-check)
3. [How the pieces fit together](#3-how-the-pieces-fit-together)
4. [Which apps work together, and in what order](#4-which-apps-work-together-and-in-what-order)
5. [Winlink email: Pat with VARA, ARDOP or packet](#5-winlink-email-pat-with-vara-ardop-or-packet)
6. [WSJT-X (FT8)](#6-wsjt-x-ft8)
7. [JS8Call](#7-js8call)
8. [fldigi, flamp and flmsg](#8-fldigi-flamp-and-flmsg)
9. [Forms: ICS-213 messages, nets, ICS-309 and ICS-205](#9-forms-ics-213-messages-nets-ics-309-and-ics-205)
10. [Logs](#10-logs)
11. [Recorder and Broadcastify](#11-recorder-and-broadcastify)
12. [Reference and the Winlink gateway finder](#12-reference-and-the-winlink-gateway-finder)
13. [Scanner](#13-scanner)
14. [Gqrx](#14-gqrx)
15. [NOAA radio (weather alerts with no internet)](#15-noaa-radio-weather-alerts-with-no-internet)
16. [APRS and the iGate](#16-aprs-and-the-igate)
17. [Meshtastic and MeshCore](#17-meshtastic-and-meshcore)
18. [Map](#18-map)
19. [Online, Browser and Library](#19-online-browser-and-library)
20. [CHIRP](#20-chirp)
21. [Settings](#21-settings)
22. [Diagnostics](#22-diagnostics)
23. [Troubleshooting](#23-troubleshooting)
24. [Where things are kept](#24-where-things-are-kept)

---

## 1. The station at a glance

### The screen

- **Top bar:** callsign, grid square (from the GPS when one is plugged in), local
  time and UTC, network status, weather alerts in force, **Rec**, ⌨ (on-screen
  keyboard) and **⏻** (Settings, Diagnostics, Power).
- **Home:** the app tiles, 18 to a page. Swipe sideways, tap ◀ ▶ or press Page
  Up/Down for the next page.
- **Folders** group related apps under one tile. Standard folders:
  - **Email:** Winlink mail (Pat), VARA HF, VARA FM, ARDOP, Packet.
  - **Mesh & APRS:** Meshtastic, MeshCore, APRS.
- **Home bar:** when an app is open, a thin bar across the top of the screen has
  **⌂ Home**, a button for each open app (tap it to bring that app to the front,
  ✕ to close it) and the time.

Tapping a tile whose app is already open brings it to the front; it does not start
a second copy. While an app starts, its tile shows **Opening…**. If it shows
**Didn't start** or **No window yet**, see [Troubleshooting](#23-troubleshooting).

### Keys (when a keyboard is plugged in)

| Key | Goes to |
| --- | --- |
| Esc or F1 | Home |
| F2 | Diagnostics |
| F3 | Settings |
| F4 | Logs |
| F5 | Reference |
| F6 | Wi-Fi |
| F7 | Online |
| F8 | Net control |
| F9 | Forms |
| 1-9 | Open the first nine tiles on the page shown |
| Alt+Tab | Switch between open apps |

Every drop-down list can be searched: tap it and type, or start typing on it.

### Tile menu

Long-press a tile (or right-click it) for **Rename**, **Change picture**, **Move to a
folder** / **Take it out** and **Arrange tiles**.

### Dedicated station or desktop mode

The station runs two ways:

- **Dedicated station:** its own computer, starting straight into the Emcomm-CNC
  screen.
- **Desktop mode:** Emcomm-CNC added to an Ubuntu or Debian computer you already
  use, opened from the app menu or picked as the **Emcomm-CNC** session on the
  login screen.

Operating is the same in both. Where desktop mode differs, this guide says so in a
box like this:

> **Desktop mode:** differences show here.

The biggest difference is sound: see [Sound](#sound-one-card-for-the-radio-one-speaker-for-listening).

---

## 2. Before you operate: the start-up check

Do this at the start of every session. It takes two minutes and catches almost
every problem before you go on the air.

1. **Radio on, then station.** Turn the radio on and connect its USB cable before
   starting the station (or before opening Emcomm-CNC in desktop mode). Rig
   control starts by itself once the radio is plugged in.
2. **Diagnostics (F2) > Read frequency.** It should show the frequency on the
   radio's display. If it doesn't, rig control isn't reaching the radio: see
   [Troubleshooting](#23-troubleshooting).
3. **Time.** Check UTC in the top bar against a known source. FT8, JS8Call and VARA
   all fail if the clock is off by more than about a second. With a GPS plugged
   in, Diagnostics shows whether the clock is following it.
4. **Settings (F3) > Audio.** The **Radio sound card** section should name the
   radio's card (on the FT-710, the C-Media **USB Audio Device**). The **Listening
   speaker** should be the speaker or headphones you want to hear the Scanner and
   recordings on.
5. **Diagnostics > PTT test (2 s)** into a dummy load, or on a clear frequency
   after identifying. The radio should key for two seconds and drop.

You're ready to operate.

---

## 3. How the pieces fit together

### One radio, one rig control

All the radio apps reach the radio through one program, **rigctld** (Hamlib's rig
control server, at `127.0.0.1:4532`). It owns the radio's CAT port and keys the
radio. That's why rig control is set up once, in **Settings > Radio**, and every app
is pointed at the same place:

| In the app, choose | Value |
| --- | --- |
| Rig / radio | **Hamlib NET rigctl** |
| Address / network server / device | **127.0.0.1:4532** (fldigi writes it `localhost:4532`) |
| PTT method | **CAT** (fldigi: "PTT via Hamlib command") |

Don't pick the radio's own model (FT-710, FT-891) inside an app, and don't pick
**FLRig**: the station doesn't run flrig, and only one program can hold the CAT
port. rigctld handles the radio model and PTT method chosen in Settings.

**Transmit from one app at a time.** There is one radio. Any app can key it and
change its frequency, so two transmitting apps will fight.

### Sound: one card for the radio, one speaker for listening

The station keeps two kinds of sound apart:

- **Radio apps** send and receive audio through the radio's sound card: WSJT-X,
  JS8Call, fldigi (and flamp), VARA HF and VARA FM, ARDOP, Direwolf (Packet and
  APRS).
- **Everything else** plays on the **Listening speaker** (Settings > Audio): the
  Scanner, Gqrx, the browser, the Library, recordings, alert sounds. If there's no
  listening speaker, they play into a silent output. Nothing that isn't a radio app
  is ever let onto the radio's sound card, so it can't be transmitted by VOX or
  mixed into a digital signal.

While Emcomm-CNC is running, the radio apps reach the radio's sound card with no
sound settings of their own: the station moves each one onto the radio as it
starts. Leave their audio device on **default** (or **pulse**). If the radio is
unplugged, their sound goes to a silent output rather than to a speaker.

> **Desktop mode:** this holds whenever Emcomm-CNC is open, whatever Settings >
> Audio > **When the radio is every app's speaker and microphone** is set to. That
> setting only matters for radio apps you run **with Emcomm-CNC closed**:
>
> - **Only while Emcomm-CNC is open** (recommended): the radio is the default only
>   while Emcomm-CNC is open; your own speaker and microphone come back when you
>   exit.
> - **Always:** the radio is always the default.
> - **Never:** your computer's own speaker stays the default. A radio app used with
>   Emcomm-CNC closed must be set to the radio's sound card by name (on the FT-710,
>   the C-Media **USB Audio Device**). "default" or "pipewire" would then lead to the
>   computer's speaker: you hear the tones and nothing goes out.
>
> An app left set to a *different* USB sound card is left alone, since that may be a
> second radio.

### Levels

**Settings > Audio > Levels** has two sliders with live meters:

- **To radio** (transmit audio from the radio apps). Raise it until the radio's ALC
  meter just starts to move, then back off a little. With ALC showing, the signal is
  distorted and splatters.
- **From radio** (receive audio into the radio apps). Set it so the meter sits about
  a third of the way up on band noise.

Set them once per radio and band; they're kept. **Diagnostics > Audio levels** opens
the same page.

### The modem ports

The Winlink modems and Direwolf each listen on a local port that Pat or Xastir
connects to. Only programs on the station itself can reach them (the firewall
blocks the network).

| Program | Port | Used by |
| --- | --- | --- |
| rigctld | 4532 | every radio app |
| VARA HF / VARA FM | 8300 | Pat |
| ARDOP (ardopcf) | 8515 | Pat |
| Direwolf, main radio | 8000 (AGW), 8001 (KISS) | Pat (packet), Xastir |
| Direwolf, APRS radio | 8010 | Xastir, iGate |
| Pat | 8080 | the Winlink mail window |

VARA HF and VARA FM share port 8300, so only one of them can run at a time.

---

## 4. Which apps work together, and in what order

### Order to open things

| To do this | Open first | Then | Notes |
| --- | --- | --- | --- |
| Winlink over VARA HF | **VARA HF** (wait for its window) | **Winlink mail** | Pat tunes the radio and keys it through VARA |
| Winlink over VARA FM | **VARA FM** | **Winlink mail** | Needs a VHF/UHF radio as the main radio |
| Winlink over ARDOP | **ARDOP** | **Winlink mail** | |
| Winlink over packet | **Packet** | **Winlink mail** | 1200 baud, VHF/UHF |
| FT8 | **WSJT-X** | | |
| JS8 | **JS8Call** | | |
| PSK, MT63, Olivia, etc. | **fldigi** | **flamp** or **flmsg** if needed | |
| Send an ICS-213 by radio | **Forms** (F9) | it offers **Start fldigi** | |
| APRS | **APRS** | | Starts Direwolf and Xastir together |
| Listen on a scanner | **Scanner** or **Gqrx** | | Uses an SDR dongle, not the radio |

The rule for Winlink: **modem first, then Pat.** Pat connects to the modem when you
tap Connect; if the modem isn't running, the connect fails.

### Can run at the same time

- **Any radio app + Scanner, Gqrx, NOAA radio, ADS-B map.** These use RTL-SDR
  dongles, not the radio.
- **Any radio app + Recorder.** The Recorder records the radio's receive audio
  alongside whatever else is listening.
- **Any radio app + Forms, Logs, Reference, Map, Online, Library.**
- **Several radio apps listening** (JS8Call and fldigi, say) all hear the radio.
  Transmit from only one.
- **APRS on the APRS radio + anything on the main radio.** With a second radio set up
  in Settings > APRS iGate, APRS has its own radio and sound card.
- **Meshtastic and MeshCore** use their own LoRa radios.

### Don't run together

- **Two modems for Pat at once** (VARA HF and VARA FM can't both start; VARA and
  ARDOP would both hear and answer).
- **Two apps that control the radio's frequency**, such as WSJT-X and JS8Call: each
  moves the radio to its own frequency. Close one before opening the other.
- **Packet and APRS on the main radio** when there's no APRS radio: they share one
  Direwolf on one frequency.
- **Scanner and Gqrx on the same dongle.** Each SDR dongle serves one program. With
  two dongles plugged in, each takes its own.

---

## 5. Winlink email: Pat with VARA, ARDOP or packet

**Winlink mail** (Pat) is the station's email client for the Winlink system. It
opens in its own window. Pat doesn't make sound itself; it hands each message to a
**modem** (VARA HF, VARA FM, ARDOP or Packet), which talks to the radio.

| Modem | Band | Speed | Notes |
| --- | --- | --- | --- |
| VARA HF | HF | Fastest on HF | Windows program, runs under Wine. Speed-limited without a licence key |
| ARDOP | HF | Slower than VARA | Free, open source |
| VARA FM | VHF/UHF | Fast | Needs a VHF/UHF radio |
| Packet | VHF/UHF | 1200 baud | Uses Direwolf; works with any FM radio |

### First-time setup (once)

1. Open **Winlink mail**. Pat already has your callsign, grid and the rig control
   address.
2. Open Pat's configuration page and enter your **Winlink password**.

### Sending and receiving over VARA HF

⚠ **Not yet tested on this station.**

1. Tap **VARA HF** (Email folder). The first time, it installs VARA from a setup
   `.zip` in Downloads or on a USB stick; if there's none, it opens Winlink's
   download page.
2. Wait for the VARA HF window.
3. Tap **Winlink mail**.
4. Write your message with **New message**, or skip this to just check mail.
5. Tap **Connect**. Pick **VARA HF**, the gateway's callsign, and its frequency
   (the gateway finder on the Reference page lists the nearest ones). Pat sets the
   radio to the gateway's dial frequency and connects.
6. Watch the VARA window: the waterfall, the signal-to-noise figure and the
   transfer. When it disconnects, received mail is in Pat's inbox.

**VARA HF settings** (VARA's own Settings menu, once):

| Setting | Value |
| --- | --- |
| SoundCard > Device Input / Output | The default device. The station moves VARA onto the radio |
| PTT | **None**. Pat keys the radio through rig control |
| TCP ports | 8300 (the standard; Pat expects it) |
| Licence key | Your key, if you have one |

On the radio, turn **VOX off**. Set the levels as in [Levels](#levels), and VARA's
own **Tune** button to check the ALC.

### VARA FM

⚠ **Not yet tested on this station.**

The same as VARA HF, with **VARA FM** in place of VARA HF and an FM gateway on a
VHF/UHF frequency. The FT-710 and FT-891 reach 6 m but not 2 m or 70 cm, so VARA FM
needs a VHF/UHF radio set as the main radio in Settings > Radio.

### ARDOP

1. Tap **ARDOP** (Email folder). A window opens with the modem's log; leave it open.
2. Tap **Winlink mail** > **Connect** > **ARDOP**, the gateway and its frequency.

ARDOP needs no settings: it uses the radio's sound card and Pat keys the radio.

### Packet

1. Tune the radio to the packet gateway's frequency (FM).
2. Tap **Packet** (Email folder). Direwolf opens in a window and shows each packet
   it hears.
3. Tap **Winlink mail** > **Connect** > **AX.25** (packet) and the gateway's
   callsign.

Direwolf's settings are written each time Packet starts (1200 baud, PTT through rig
control). For your own settings, copy `~/.config/emcomm/direwolf.conf` to
`~/.config/emcomm/direwolf.custom.conf` and edit that.

### When it doesn't connect

- The modem window isn't open, or was opened after Pat tried: open the modem, then
  Connect again.
- No transmit: check **Diagnostics > PTT test**, and that VARA's PTT is set to None
  (Pat keys the radio).
- Transmits but the gateway doesn't answer: check the clock, the To radio level
  (ALC), and that you're on the dial frequency Pat set.
- The gateway list is old: **Reference > Nearest Winlink gateways > Update list**
  (needs the internet).

---

## 6. WSJT-X (FT8)

**What it's for:** FT8 and the other weak-signal modes. At an emcomm station it's
mostly a band check: which bands are open, and from where (the map shows stations
heard, and Online > Who heard me shows who heard you).

Tap **WSJT-X**. The first time it's opened from the tile, your callsign, grid and
rig control are filled in. Open it from the tile, not from the computer's own app
menu, or those settings aren't filled in.

### Settings (File > Settings), once

**Radio tab**

| Setting | Value |
| --- | --- |
| Rig | **Hamlib NET rigctl** |
| Network Server | **127.0.0.1:4532** |
| PTT Method | **CAT** |
| Mode | **Data/Pkt** |
| Split Operation | **Fake It** |

Tap **Test CAT** (turns green) and **Test PTT** (keys the radio).

**Audio tab**

| Setting | Value |
| --- | --- |
| Input | **default** (the station moves it to the radio). Used with Emcomm-CNC closed in desktop mode set to Never: the radio's **USB Audio Device** |
| Output | The same as Input |
| Channels | **Mono** |

Leave the Power slider (bottom right of the main window) near the top and set the
transmit level with **To radio** in Settings > Audio.

### Operating

Pick the band from the drop-down; WSJT-X moves the radio there. Contacts logged in
WSJT-X show on the station's Logs page.

---

## 7. JS8Call

**What it's for:** keyboard messaging on HF that gets through in poor conditions,
with store-and-forward through other stations (relay and inbox). Good for passing
short traffic when voice isn't working.

Tap **JS8Call**. The first time it's opened from the tile, your callsign, grid and
rig control are filled in.

### Settings (File > Settings), once

**Radio tab:** the same as WSJT-X: Rig **Hamlib NET rigctl**, Network Server
**127.0.0.1:4532**, PTT **CAT**, Mode **Data/Pkt**, Split **Fake It**.

**Audio tab:** the same as WSJT-X: **default**, **Mono**.

JS8Call's messages and activity show on the Logs page. Frequencies for JS8 on each
band are in Reference.

---

## 8. fldigi, flamp and flmsg

### fldigi

**What it's for:** the general digital-mode program: PSK, MT63, Olivia, RTTY, CW and
the NBEMS modes used to pass ICS forms. Forms' **Send by radio** uses fldigi.

fldigi gets no settings from the station, so set these once.

**Configure > Rig Control > Hamlib**

| Setting | Value |
| --- | --- |
| Use Hamlib | ticked |
| Rig | **Hamlib NET rigctl** |
| Device | **localhost:4532** |
| PTT via Hamlib command | ticked |

Untick **Use flrig** and **Use RigCAT** if either is ticked. Tap **Initialize**.

**Configure > Audio > Devices**

| Setting | Value |
| --- | --- |
| With Emcomm-CNC open | **PulseAudio** (server string left blank) |
| Used with Emcomm-CNC closed, desktop mode set to Never | **PortAudio**, Capture and Playback: the radio's **USB Audio Device** |

Save the configuration before closing the dialog.

### flamp

Sends files (a spreadsheet, a picture, a long message) as blocks that the other
station can re-request if any are missed. It works through fldigi: open **fldigi**
first, then flamp from fldigi's menu.

### flmsg

Fills in and reads NBEMS forms (ICS-213 and many others). Most of the time use the
station's own **Forms** page instead (next section), which shows ICS-213s on FEMA's
form and sends them through fldigi. Use the **flmsg** tile for its other forms. The
station keeps flmsg on UTC (dates `2026-10-21`, times `1356Z`) and in its full
window.

---

## 9. Forms: ICS-213 messages, nets, ICS-309 and ICS-205

**Forms** (tile or F9) is one page for everything written down during an event. The
list on the left holds every ICS-213 message (written here or received by fldigi),
every net, and every ICS-309 and ICS-205, newest first. The drop-down narrows it to
one kind. Pick one to see it on the right.

### Write an ICS-213

1. **New ▾ > ICS-213 message.** The blank FEMA form opens with a box on each field.
2. Fill in To, From, Subject and Message. The date and time (UTC) are already
   filled in, and the incident too while a net is open.
3. **Save**, or **Send by radio** to send it now.

### Reply to an ICS-213

Pick the message in the list and tap **Reply / Edit**. A received message gets the
reply boxes at the bottom and is saved as a copy, so what came in stays as it was.

### Send by radio

1. Pick the message (or tap Send by radio while writing one; it saves first).
2. The window shows whether fldigi is running. If not, tap **Start fldigi** and wait.
3. Pick the modem (MT63-2000L is the usual choice; agree it with the receiving
   station). The one fldigi is on is picked already.
4. Tap Send. fldigi keys the radio and sends; the window says when it's back on
   receive.

The other station's fldigi saves the message for flmsg as usual, and it shows on
their Forms page. A copy of what went out is kept in `~/.nbems/WRAP/send`.

### Receive an ICS-213

Leave **fldigi** open on the agreed frequency and mode. Received messages appear in
the Forms list. Tap one to see it on FEMA's form; **More ▾ > Print** prints it or
saves a PDF.

### Run a net

1. **New ▾ > Net log** (or F8). Name the net and tap **Start net**.
2. Check-ins: type the callsign and press Enter (or tap **Check in**).
3. Traffic: fill in From, To and Message and tap **Log**.
4. **Undo** removes the last entry.
5. When you're done, **Close net**.

Every entry gets the UTC time. The open net stays at the top of the Forms list with
**Net control** and **ICS-309 log** buttons.

### ICS-309 and ICS-205

- **ICS-309 Communications Log:** pick a net in the list and **New ▾ > ICS-309 Communications Log** (or **ICS-309 log** on Net control). It
  fills in the log from that net (or the open or last net).
- **ICS-205 Radio Communications Plan:** filled in from My frequencies (receive and
  transmit frequency, tone, and the note as the assignment).

Both are saved in `~/ICS forms` and open with a **Print** button; the print dialog
can also save a PDF to a USB stick.

---

## 10. Logs

**Logs** (tile or F4) shows in one place:

- **Contact notes:** your own notes. Type a callsign and a note (traffic passed,
  signal report, net) and tap **Add note**; the UTC time, frequency and mode are
  filled in from the radio.
- **JS8Call messages** and **JS8Call all activity.**
- **WSJT-X contacts.**
- **Winlink mail.**
- **Station updates:** the log of the last Update station.

The **Forms** button goes to Forms (F9) and **Recorder** to the Recorder.

---

## 11. Recorder and Broadcastify

### Recorder

Records the radio's receive audio to `~/Recordings`, each file named with the UTC
time, frequency and mode. Open it with **Rec** in the top bar.

- **Record when there's a signal:** keeps only the parts with audio. Use it to
  monitor a frequency for hours.
- **Record everything:** continuous, in hourly files.
- **Stop** ends it. **Start recording when the station starts** brings it back
  after a restart or power cut.

**Rec** turns red while recording. Recordings play on the Listening speaker, never
through the radio. **Select**, then tap recordings (or **Select all**), then
**Delete** removes several at once. When `~/Recordings` passes about 2 GB, the oldest
recordings are deleted to make room.

### Broadcastify

Streams the same receive audio to a Broadcastify feed. Apply for a feed at
broadcastify.com; once it's approved, type its server, port, mount and password in
**Feed settings** and tap **Go live**. **Live** shows next to Rec while it streams. It
reconnects by itself if the internet drops.

⚠ **Not yet tested on this station** against Broadcastify's own servers.

---

## 12. Reference and the Winlink gateway finder

**Reference** (tile or F5) holds the frequency lists:

- US band plan, with a line at the top saying whether it's day or night at your
  grid and which HF bands to try for nearby and distant stations.
- Emergency and calling frequencies (IARU emergency centres of activity, Hurricane
  Watch Net, SATERN, 60 m channels, simplex calling, APRS).
- JS8Call and FT8 dial frequencies.
- Other services to listen to (NOAA Weather Radio, marine channel 16, aviation
  guard, FRS/GMRS, MURS, CB), marked receive only.
- **My frequencies:** your own list.

The row the radio is on is highlighted. The search box narrows by name, note, mode
or MHz; the drop-down by band.

- **Tune** puts the radio on that frequency and mode. For a repeater in My
  frequencies, it also sets the offset and tone (on bands the radio supports).
- **Save to mine** copies a row to My frequencies.
- **Add frequency** saves the radio's current frequency (or one you type) with a
  name and note. **Edit** changes or removes one of your rows.
- **Load a list** adds a CSV from a USB stick or Downloads: the station's own
  layout, a CHIRP export, or a RepeaterBook or RadioReference download.

### Nearest Winlink gateways

On the Reference page: every gateway channel from Pat's list, nearest to your grid
first, with distance, bearing, mode, hours and whether it's open now. Pick VARA HF,
ARDOP, VARA FM or Packet to narrow it, and **Tune** puts the radio on the gateway's
dial frequency. **Update list** downloads a fresh one when the station is online.

Within about 300 miles, NVIS on 80 m or 40 m (or 60 m) usually works better than
the nearest gateway on a higher band.

---

## 13. Scanner

The Scanner is the station's own scanning receiver. It uses an **RTL-SDR dongle**
(or another SDR), not the radio, so it runs alongside anything else, and it plays on
the Listening speaker.

### Start

Plug in a dongle with a VHF/UHF antenna and tap **Scanner**. It scans
`~/Scanner channels.csv`, which starts as Vermont's emergency channels (law
enforcement, fire/EMS, interop/EOC) plus an **Airband** group.

### Controls

| Control | What it does |
| --- | --- |
| Groups (left) | Tick or untick whole groups |
| Distance | Listen within 10, 25, 50 or 100 miles of your grid, or everywhere. Statewide channels with no site are always kept |
| **Hold** | Stay on the channel. Tapping a channel in the list also holds there |
| **Skip** | Move on |
| **Lock out** | Leave this channel out of the scan (or untick it) |
| **Stay on a signal** | How long it listens once it stops: until quiet plus 2, 5 or 10 s for a reply, or a set time (5 s to 1 minute) |
| **Tone squelch** | Stop only when the channel's own PL tone is there. DPL channels stop on any signal |
| Squelch | 1 opens on almost anything, 9 needs a strong signal; 4 suits most antennas |
| **Tune** | Keypad to listen on any frequency the receiver reaches; − and + step 12.5 kHz (5 kHz below 50 MHz) |
| **Save to list** | Adds the tuned frequency to **My channels** |
| **Load a list** | Any CSV with a Frequency column (MHz), such as a RadioReference export, from a USB stick |
| **Receiver** | Which SDR, gain and frequency correction (ppm) |

It plays analog FM and AM. P25, DMR and other digital channels are listed but not
scanned. Airband needs an antenna for about 120-135 MHz: a 2 m/70 cm antenna hears
nearby aircraft; a discone or an airband quarter-wave (about 58 cm) does better.

### Dongles

Each dongle serves one program. With three dongles, a sensible split is:

| Dongle | Used by |
| --- | --- |
| 1 | NOAA radio (weather alerts), 162 MHz antenna |
| 2 | Scanner or Gqrx, VHF/UHF antenna |
| 3 | ADS-B (map aircraft), 1090 MHz antenna, picked in Settings > Devices > ADS-B receiver |

With only one dongle, the weather alert listener pauses while the Scanner or Gqrx
has it, and resumes when they close. **Settings > Devices > Free the SDR receiver**
closes whatever is holding a dongle.

---

## 14. Gqrx

A waterfall receiver for listening anywhere a receiver reaches, HF included. Modes:
FM, AM, SSB, CW. The Scanner's channel list is loaded as its bookmarks.

- Tap **Gqrx**. With more than one receiver it asks which. Press Gqrx's **▶** to
  start receiving.
- **HF on an RTL-SDR:** an RTL-SDR Blog V4 tunes HF directly. Other RTL-SDR dongles
  offer "on HF (direct sampling)" for 0.5 to 28.8 MHz.
- **No receiver plugged in:** **Practice signal** plays a recording around 146.5 MHz
  to learn on; **Network receiver** uses an RTL-SDR on another computer (`rtl_tcp`).

Gqrx is receive only and never touches the radio.

---

## 15. NOAA radio (weather alerts with no internet)

Decodes the SAME alert bursts from NOAA Weather Radio with an RTL-SDR dongle and a
162 MHz antenna.

1. Tap **NOAA radio**.
2. Pick your nearest transmitter's channel (weather.gov/nwr lists them).
3. Pick a state and county and tap **Add county**, for each county you want.

Alerts for your counties join the internet alerts in the top bar and on the Online
page; warnings pop up on screen. The weekly test is noted but not shown as an alert,
so you can see the receiver is working.

---

## 16. APRS and the iGate

### APRS tile

Tap **APRS** (Mesh & APRS folder). It starts Direwolf and opens **Xastir** with your
callsign and the position at the centre of your grid square. Direwolf stops when
Xastir closes.

- With no APRS radio set up, APRS uses the main radio, which must be on 144.390 MHz
  FM (North America), and the FT-710 and FT-891 can't reach it.
- With an APRS radio set up (below), it uses that radio.

### APRS radio and iGate (Settings > APRS iGate)

⚠ **Not yet tested on this station.**

A second radio kept on 144.390 MHz, with its own Digirig. For the Icom ID-5100: a
Digirig Mobile and Digirig's "ICOM RJ-45 Cable for Digirig Mobile", in the mic jack
and SP1. Unplug the hand mic while it's in use.

| Setting | Value |
| --- | --- |
| Sound card | The Digirig, listed by USB socket. Keep it in the same socket |
| PTT port | The Digirig's serial port |
| iGate | **Off** (APRS tile only), **Receive only** (passes what it hears to the internet, never transmits), or **Two-way** (also sends messages from the internet to nearby stations, and beacons every 30 minutes) |
| SSID | -10 unless you pick another |
| Position | Grid square centre, unless you type a latitude and longitude |

Start with **Receive only**, the ID-5100's VOX off and its volume fairly low. The
page shows the APRS-IS connection and how many packets were heard and passed.

---

## 17. Meshtastic and MeshCore

LoRa text messaging on their own small radios, separate from the station's radio.

1. Plug the node in by USB, or turn on its Bluetooth.
2. Tap **Meshtastic** or **MeshCore** (Mesh & APRS folder).
3. With no USB node, it searches for Bluetooth radios for 10 seconds and asks which.
   The first time, it pairs and asks for the PIN: Meshtastic shows it on its screen
   (or uses 123456 on a node without one); MeshCore uses 123456 unless you changed
   it.

Meshtastic opens `contact`, a full-screen text client for messages, nodes and
settings. MeshCore opens `meshcore-cli`; type `?` for its commands.

⚠ **Bluetooth pairing not yet tested on this station.**

---

## 18. Map

An offline map with grid squares, your station, Winlink gateways (blue HF, green
VHF/UHF; tap for frequencies, modes and hours), stations heard on JS8Call and
WSJT-X, and stations that heard you (purple).

Checkboxes add:

- **Aircraft:** live ADS-B from the dongle picked in Settings > Devices > ADS-B
  receiver; emergencies in red. ⚠ Not yet tested on this station.
- **Warnings:** NWS watch, warning and advisory areas, shaded by severity; tap for
  details. Kept offline until each ends.
- **Mesh:** Meshtastic and MeshCore nodes that sent a position.

**Map / Streets / Satellite / Topo** switch the background. Only **Map** works
offline.

---

## 19. Online, Browser and Library

### Online (tile or F7)

Data from internet services, saved so the last answer still shows offline. Each
section says when it was last updated.

- **Weather alerts** for your grid (NWS), most severe first.
- **Propagation:** solar flux, K index, NOAA scales and band conditions.
- **Who heard me:** PSKReporter reports of your signal in the last six hours.
- **Callsign lookup:** QRZ (or HamQTH) and aprs.fi.

### Browser

Chromium with a ham radio bookmarks bar. (In desktop mode, your own browser with a
page of the same bookmarks.)

### Library

Offline books from Kiwix, readable with no internet: WikEM, post-disaster and water
guides, Wikipedia's medical articles and more. **Download** next to a book needs the
internet; any `.zim` on a USB stick shows up too.

---

## 20. CHIRP

Programs handhelds and mobiles over their programming cable. The station keeps
`~/My frequencies for CHIRP.csv` up to date with the FM channels from My
frequencies. In CHIRP: download from the radio first, then **File > Import** that
file, then upload to the radio.

---

## 21. Settings

**Settings** (⏻ > Settings, or F3) is a page of tiles:

| Tile | What's there |
| --- | --- |
| User | Callsign, grid square (**From GPS** fills it in), time zone |
| Radio | Preset, or manufacturer and model; CAT port and baud rate; PTT method and port; sound card. **Save and restart rig control** |
| Devices | GPS port, what's plugged in, **Free the SDR receiver**, **ADS-B receiver** |
| Display | Colours (Amber dark, Light, Slate blue, Night red, Sunlight), resolution, text size, rotation, start-up screen |
| Wi-Fi | Networks (also F6) |
| Accounts | QRZ, HamQTH, aprs.fi key, contact email |
| Backup | Save settings and lists to a USB stick, or restore |
| Update station | Latest Emcomm-CNC and apps |
| Audio | Radio sound card, Levels, Listening speaker, Playing now |
| APRS iGate | Second radio for APRS |
| Power | Restart or shut down (desktop: exit) |
| Home tiles | Arrange and group the apps |

### Radio presets

| Radio | Preset | CAT | PTT | Sound card |
| --- | --- | --- | --- | --- |
| Yaesu FT-710 | Yaesu FT-710 | Radio's USB (Enhanced port), 38400 | CAT | Radio's built-in **USB Audio Device** |
| Yaesu FT-891 | Yaesu FT-891 + Digirig | Radio's USB (Enhanced port), 38400 | RTS on the Digirig's serial port | Digirig |

Set the radio's own CAT RATE menu to the same baud rate.

<!-- TODO: radio menu settings (FT-710, FT-891, ID-5100), pending the user's answer. -->

---

## 22. Diagnostics

**Diagnostics** (⏻ > Diagnostics, or F2): USB devices, radio ports, sound cards,
services, recent USB events and GPS.

- **Read frequency:** asks the radio for its frequency through rig control.
- **PTT test (2 s):** keys the radio for two seconds.
- **Audio levels:** opens Settings > Audio.
- **Rig control log:** what rigctld has been doing.
- **Terminal:** a command line, for when you're asked to run something.

The same report is available over SSH with `emcomm-diag`.

---

## 23. Troubleshooting

| Problem | Check |
| --- | --- |
| Read frequency fails | Radio on and USB plugged in; Settings > Radio baud rate matches the radio's CAT RATE menu; **Save and restart rig control** |
| An app says it can't reach the radio | It's set to **Hamlib NET rigctl, 127.0.0.1:4532**, not FLRig or the radio's own model |
| Radio doesn't transmit | Diagnostics > PTT test; the app's PTT method is CAT |
| Transmits but no audio goes out | Settings > Audio > Radio sound card names the radio; To radio level isn't at zero; Settings > Audio > Playing now shows the app on the radio |
| Tones come out of the computer's speaker | Is Emcomm-CNC open? With it closed in desktop mode set to Never, pick the radio's **USB Audio Device** in the app. |
| The radio's sound card keeps disappearing and coming back | Diagnostics > recent USB events. Usually RF on the USB cable or a weak USB port: add clip-on ferrites at both ends, plug straight into the computer rather than a hub, and try another port |
| ALC high, signal distorted | Lower **To radio** |
| FT8 or JS8 decodes nothing | Clock (UTC in the top bar); From radio level; radio on the right dial frequency in USB/DATA |
| Pat won't connect | Modem open first; one modem only; see [When it doesn't connect](#when-it-doesnt-connect) |
| Scanner or Gqrx says the receiver is busy | Settings > Devices > **Free the SDR receiver** |
| A tile says **Didn't start** | Try again; if it repeats, Logs > Station updates, then Update station |
| Something stopped working after an update | Logs > **Station updates** shows which step failed |

---

## 24. Where things are kept

| What | Where |
| --- | --- |
| Station settings | `/etc/emcomm/station.json` |
| Your Emcomm-CNC settings | `~/.config/emcomm/` |
| My frequencies | `~/.local/share/emcomm/reference/My frequencies.csv` |
| Scanner list | `~/Scanner channels.csv` |
| Net logs | `~/.local/share/emcomm/nets` |
| ICS-309 and ICS-205 | `~/ICS forms` |
| ICS-213 messages | `~/.nbems/ICS/messages` (written), `~/.nbems/WRAP/recv` (received), `~/.nbems/WRAP/send` (sent) |
| Recordings | `~/Recordings` |
| Library books | `~/Library` |
| Pat (Winlink) | `~/.config/pat/config.json` |
| Update log | `/var/log/emcomm-update.log` |

**Settings > Backup** saves your settings, lists and tile arrangement to a USB stick.
