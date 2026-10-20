# Emcomm-CNC

*Emcomm command and control.*

Turns a fresh minimal Debian 13 install into a dedicated emcomm station: it boots
straight into a full-screen touch launcher for the radio apps, with no desktop
environment.

![Home screen](docs/home.png)

## What's in it so far

- **Base system:** a `radio` user, SSH for remote troubleshooting, PipeWire audio.
- **Settings screen:** a page of large tiles: User (callsign and grid), Radio,
  Devices (GPS, and what's plugged in), Display, Wi-Fi, Accounts,
  Backup, Update station, Diagnostics, Power and Home tiles. User opens
  automatically on first boot. Any radio Hamlib supports can be picked by
  manufacturer and model; the CAT port, PTT port and sound card are picked from the
  USB devices that are plugged in, with a Rescan button. Saving gives those devices
  stable names (`/dev/rig-cat`, `/dev/rig-ptt`, ALSA card `rigaudio`) and restarts
  Hamlib's `rigctld`, which every app uses to reach the radio on `127.0.0.1:4532`.
  `rigctld` starts by itself whenever the radio is plugged in.
- **GPS time and position:** plug in a USB GPS (any u-blox puck works with no
  setup; for another kind, pick its port under **GPS** in Settings). gpsd reads it
  and chrony sets the clock from it, so FT8, JS8Call and the logs keep the right
  time with no internet. The top bar shows the GPS grid square; when it differs from
  the saved one it says "tap to use", and tapping it (or **From GPS** next to the
  grid in Settings) fills in the new grid, ready to save. Diagnostics shows the
  fix and whether the clock is following the GPS.
- **Presets** (`radios/`): Yaesu FT-891 with a Digirig, and Yaesu FT-710. Optional
  shortcuts that fill in every radio field at once, even before the radio is plugged in.
- **Kiosk:** auto-login on the console, X with Openbox only, screen blanking off.
  The station starts with a spinner instead of scrolling text and goes straight
  to the launcher (the GRUB menu still shows briefly, for recovery mode). Apps
  open maximized under a thin **Home bar** across the top of the screen: **⌂ Home**
  brings the launcher back, each open app has a button to bring it to the front
  (and ✕ to close it), and the bar shows the callsign and UTC time. Tapping the
  tile of an app that's already open brings it to the front instead of starting a
  second copy. With a keyboard, Alt+Tab also switches apps.
- **Several apps at once:** every app reaches the radio's sound card through
  PipeWire, so they can all listen together (JS8Call and the recorder, say).
  Transmit from one app at a time: there's one radio, and each app keys it and
  sets its frequency through the same rig control.
- **On-screen keyboard:** ⌨ in the launcher's top bar or **Keyboard** on the Home
  bar shows or hides Onboard, docked along the bottom of the screen. Tapping a text
  box in the launcher on a touchscreen brings it up by itself, and it goes away
  when you're done typing.
- **Launcher:** the home screen above. Works by touch, mouse or keyboard: Tab moves
  between buttons, 1–9 open tiles, Esc/F1 goes Home, F2 Diagnostics, F3 Settings,
  F4 Logs, F5 Reference, F6 Wi-Fi, F7 Online, F8 Net control, F9 ICS-213 messages. A tile for an app that isn't installed says "tap to install". To use
  your own picture on a tile, long-press it (or right-click, or press the Menu key)
  and pick an SVG, PNG or JPG from a USB stick or `~/Downloads`; "Use the standard
  icon" puts it back. **Rename** in the same menu gives a tile (or a folder) your own
  name, and "Use the standard name" undoes it; names are kept in
  `~/.config/emcomm/tile-names.json`. To put the tiles in your own order, pick **Arrange tiles** from
  that same menu (or **Home tiles** in Settings), tap a tile, then tap where it
  should go; **Add a gap** leaves an empty space to group tiles into rows, and
  **Standard order** puts them back. Home holds 18 tiles a page (six across,
  three down) and tiles stay that size: with more apps, or after **New page**,
  swipe sideways, tap ◀ ▶ under the tiles or press Page Up/Down to change page.
  While arranging, pick a tile, go to another page and tap a tile or an empty
  place to move it there; **Remove page** folds the page shown into the one
  before it. Folders hold related apps under one tile: **Email** (Winlink mail,
  VARA HF, VARA FM) and **Mesh & APRS** (Meshtastic, MeshCore, APRS) come as
  standard. Tap a folder to open it; Esc or ‹ Home closes it. While arranging,
  tap an app then a folder to put it in, **New folder** makes one (holding the
  app picked, if any), and a picked folder can be opened (to reorder or **Take
  out of folder** what's inside), renamed or removed (its apps go back on Home
  where it was). The order, pages and folders are kept in
  `~/.config/emcomm/tiles.json` (and in USB backups), and the 1–9 keys open the
  first nine tiles of the page or folder shown. **Display** in Settings sets the colours (dark, or light for
  daylight), the screen resolution (Automatic picks the screen's own), the text
  size (Normal, Large or Extra large, for bigger screens; other apps follow it
  too) and the rotation, for a screen mounted on its side or upside down. A
  touchscreen turns with the screen. A change to the screen goes back by itself
  after 15 seconds unless you tap **Keep**, so a setting the screen can't show
  can't lock you out.
- **Radio apps:** JS8Call, WSJT-X, fldigi with flamp, flmsg (ICS-213 forms), Pat for
  Winlink mail, VARA HF and VARA FM (under Wine), ARDOP (ardopcf), Direwolf for
  packet, Xastir for APRS, and the Meshtastic (`contact`) and MeshCore
  (`meshcore-cli`) clients for LoRa mesh radios, and CHIRP for programming
  handhelds and mobiles. Every app reaches the radio through `rigctld`, so CAT and PTT are set up
  once, in Settings. Callsign and grid are filled in for each app.
- **Library** (tile): offline books from Kiwix, readable with no internet. With
  internet, tap **Download** next to a suggested book: WikEM (emergency medicine),
  post-disaster and water guides, Wikipedia's medical articles, Amateur Radio
  Stack Exchange and iFixit repair guides. Books are saved in `~/Library`. Any
  Kiwix `.zim` file on a plugged-in USB stick shows up too and is read straight
  from the stick, which is the way to carry big ones such as all of Wikipedia
  (get them from library.kiwix.org on another computer). **Open library** shows
  every book in a window with search.
- **Logs:** JS8Call messages and activity, WSJT-X contacts and Winlink mail in one
  place, plus a box to note a voice or other contact. Notes get the UTC time,
  frequency and mode from the radio.
- **Net control** (F8, or the button on Logs): name the net and tap **Start net**.
  Type each callsign and press Enter to check it in, or fill in From, To and Message
  and tap **Log** for traffic; every entry gets the UTC time, and **Undo** removes
  the last one. **ICS-309 log** fills in the Communications Log for the open (or
  last) net, and **ICS-205 plan** fills in the Radio Communications Plan from My
  frequencies (receive and transmit frequency, tone, and the note as the
  assignment). Both are saved in `~/ICS forms` and open with a **Print** button;
  the print dialog can also save a PDF to a USB stick. Nets are kept in
  `~/.local/share/emcomm/nets`.
- **ICS-213 messages** (F9, or the button on Logs): every ICS-213 in flmsg, the
  ones you wrote and the ones fldigi received, shown on FEMA's own General Message
  form (ICS 213), the same layout as the paper form. Pick one on the left to see
  it; **Print** prints it (or saves a PDF), **Reply or edit in flmsg** opens it in
  flmsg to fill in the reply, and **New message** opens flmsg to write one. The
  filled-in form is also saved as a PDF in `~/ICS forms`.
- **Recorder** (the **Rec** button at the top of the screen, or on the Logs page):
  records the radio's receive audio to `~/Recordings`, each file named with the
  UTC time, frequency and mode. **Record when there's a signal** keeps only the
  parts with audio, so a frequency can be monitored for hours; **Record
  everything** records continuously in hourly files. Recording starts when you
  tap one of those and runs until **Stop**; turn on **Start recording when the
  station starts** to have it come back on by itself after a restart or power
  cut. **Rec** turns red while it records, in the launcher's top bar and in the
  Home bar above every app. Recordings play on headphones or a speaker, never
  through the radio, so they can't key it by VOX.
- **Broadcastify** (on the Recorder page): streams the same receive audio to a
  Broadcastify feed. Apply for a feed at broadcastify.com; once it's approved,
  type its server, port, mount and password into **Feed settings** and tap **Go
  live**. It sends MP3 at 16 kbit/s mono as Broadcastify asks, reconnects by
  itself if the internet drops, and **At start-up** brings it back after a
  restart. **Live** shows next to **Rec** while it streams. The password stays
  in `~/.config/emcomm/broadcastify.json`, readable only by the station user.
- **Reference** (F5): the US band plan with a which-band-when guide, emergency and
  calling frequencies (IARU emergency centres of activity, Hurricane Watch Net,
  SATERN, 60 m channels, simplex calling, APRS), and JS8Call and FT8 dial
  frequencies. **Tune** puts the radio on that frequency and mode. **Add
  frequency** saves the radio's current frequency (or one you type) to **My
  frequencies** with a name and note, for local nets and repeaters. For a repeater,
  also give its offset (for example -0.6, or +5 on 70 cm) and CTCSS tone; **Tune**
  then sets the radio to FM with that offset and tone, on radios and bands that
  support it. The lists are CSV files (`MHz,Mode,Name,Note,Offset,Tone`; Offset and
  Tone may be left out) in `/usr/share/emcomm/reference`; a file of the same name in
  `~/.local/share/emcomm/reference` replaces the standard one. My frequencies is
  `~/.local/share/emcomm/reference/My frequencies.csv`, so a list made on a computer
  can be copied in from a USB stick.
- **Nearest Winlink gateways** (on the Reference page): every gateway channel from
  Pat's list, nearest to your grid first, with distance, bearing, mode and hours.
  Pick VARA HF, ARDOP, VARA FM or Packet to narrow it, and **Tune** puts the radio
  on the gateway's dial frequency (centre minus 1.5 kHz on HF, as Pat does). It
  works offline from Pat's saved list; **Update list** downloads a fresh one when
  the station has internet. The nearest HF gateway isn't always the easiest to
  reach: within about 300 miles, NVIS on 80 m or 40 m (or 60 m) works best.
- **Map** (tile): an offline map (countries, states, US counties, highways and towns
  from Natural Earth) with Maidenhead grid squares, your station, every Winlink
  gateway (blue HF, green VHF/UHF; tap one for its dial frequencies, modes and
  hours) and stations heard on JS8Call and WSJT-X with their grids. The gateway
  list is Pat's: it works offline from the copy built into Pat, and is refreshed
  when it's over a week old and the station is online. It also shows the stations
  that heard you (purple, with a line to each), as the Online page last saved them.
- **Online** (F7): data from internet services, saved so the last answer still
  shows offline. Each section says when it was last updated.
  - **Weather alerts** for your grid from the National Weather Service (US only),
    most severe first; **Details** shows the full text. Alerts in force also show in
    the top bar; tap there to read them. Checked every ten minutes when online.
  - **Propagation:** solar flux, K index and the NOAA R/S/G scales from NOAA's Space
    Weather Prediction Center, and day/night HF band conditions from N0NBH
    (hamqsl.com), with a line on what the numbers mean.
  - **Who heard me:** stations that reported your signal to PSKReporter in the last
    six hours, with distance, band, mode and SNR. Transmit FT8, JS8 or another
    digital mode first; reports come from stations that are online.
  - **Callsign lookup:** name, address, grid, distance and licence from QRZ (or
    HamQTH if there's no QRZ login), plus the last APRS position from aprs.fi.
    Callsigns looked up before still show offline.
  - **Accounts:** QRZ and HamQTH logins, a contact email (sent to NOAA and
    PSKReporter so they know who's asking) and the aprs.fi API key. They're saved in
    `~/.config/emcomm/accounts.json`, readable only by the station user. Alerts,
    propagation and PSKReporter need no account. QRZ gives full records only to
    XML Logbook Data subscribers.
- **NOAA Weather Radio alerts, no internet needed:** plug in an RTL-SDR dongle
  (any RTL2832U stick, about $30) with an antenna for 162 MHz, then tap the
  **NOAA alerts** tile on Home (or **Set up** next to NOAA Weather Radio on the
  Online page's Weather alerts), pick your
  nearest transmitter's channel (weather.gov/nwr lists them), then pick a state
  and county and tap **Add county** for each county you want alerts for. Every
  US county, parish and territory district is listed; a code for part of a
  county (first digit not 0) can be typed in instead. The station decodes the SAME burst at the start of every
  alert: alerts for your counties join the internet ones in the list and the top
  bar, and warnings pop up on screen. The weekly test is noted but not shown as an
  alert, so you can see the receiver is working.
- **Browser** (tile): Chromium, with a Ham radio bookmarks bar (World Radio League,
  QRZ, PSKReporter, aprs.fi, RepeaterBook, NWS, space weather, Winlink, WebSDR,
  LoTW). The list is `apps_browser_bookmarks` in `roles/apps/defaults/main.yml`.
- **Wi-Fi** (F6, the **Wi-Fi** button in Settings, or tap the network status at the
  top): lists nearby networks by signal strength; tap **Connect** and type the
  password. The station remembers networks it has joined. If the Debian installer
  set up Wi-Fi itself (installing over Wi-Fi), the page says so: remove the Wi-Fi
  lines from `/etc/network/interfaces` and restart to manage it here instead.
- **Update station** (in Settings): downloads the latest Emcomm-CNC and installs
  anything missing, with progress on screen. No terminal or password needed.
- **Diagnostics:** USB devices with vendor:product IDs, radio ports, sound cards,
  services, recent USB events, a read-frequency check and a 2-second PTT test.
  The same report is available over SSH with `emcomm-diag`.

![Home screen in light mode](docs/home-light.png)

![Settings](docs/settings.png)

![Diagnostics](docs/diag.png)

![Logs](docs/logs.png)

![Reference](docs/reference.png)

![Wi-Fi](docs/wifi.png)

![Map](docs/map.png)

![Nearest Winlink gateways](docs/gateways.png)

![Online: weather alerts](docs/online-alerts.png)

![Online: propagation](docs/online-propagation.png)

## Using the apps

- **Winlink over VARA:** tap VARA HF (or FM) first. The first tap sets up Wine and
  installs VARA from a setup .zip in `~/Downloads` or on a USB stick; if there isn't
  one, it opens Winlink's download page so you can tap the file. VARA uses the default sound card, which is the radio. Then
  open Winlink mail (Pat), which keys the radio through `rigctld`. On first use, set
  your Winlink password in Pat's configuration page.
- **Winlink over ARDOP or packet:** start ARDOP or Packet from their tiles, then use
  Pat as above.
- **JS8Call and WSJT-X** start with your callsign, grid and rig control filled in
  (radio "Hamlib NET rigctl", PTT by CAT).
- **Audio:** whenever the radio's sound card is plugged in, the station makes it the
  default speaker and microphone, so apps left on their "default" sound device use
  the radio. (`emcomm-audio-default` does this; Diagnostics shows the current default.)
- **APRS:** the APRS tile starts Direwolf (1200 baud, for 2 m APRS on 144.390 MHz
  in North America) and opens Xastir with your callsign, and your position taken
  from the centre of your grid square. Direwolf stops when Xastir closes. Xastir
  only fills in its radio connection the first time, so changes you make in
  Interface Control stick. For HF APRS at 300 baud, put your own Direwolf settings
  in `~/.config/emcomm/direwolf.custom.conf`.
- **Meshtastic and MeshCore:** plug the node in by USB, or turn on its Bluetooth,
  and tap its tile. The tile finds the node's USB port (skipping the radio's CAT
  and PTT ports). With no USB node it searches for Bluetooth radios for 10 seconds
  and asks which one; the first time, it pairs and asks for the radio's PIN
  (Meshtastic shows it on its screen, or uses 123456 on a node without one;
  MeshCore uses 123456 unless you changed it). After that the paired radio is
  offered by name, next to any USB nodes and "Search for a Bluetooth radio".
  Bluetooth needs an adapter in the station computer (most mini-PCs and laptops
  have one). Meshtastic opens `contact`, a full-screen
  text client for messages, nodes and settings; MeshCore opens `meshcore-cli`,
  where `?` lists its commands.
- **CHIRP:** for programming a handheld or mobile over its programming cable (the
  FT-710 and FT-891 don't need it). The station keeps
  `~/My frequencies for CHIRP.csv` up to date with the FM channels from My
  frequencies, offset and tone included. In CHIRP, download from the radio first,
  then use File > Import to add that file's channels, and upload to the radio.
  CHIRP is built from its source on GitHub, the same code as its daily builds
  (set `apps_chirp_version` in `roles/apps/defaults/main.yml` to a commit or tag
  to stay on one). Its download site turns away scripts, so it isn't used.
- **Scanner** (tile, any SDR): plug in an SDR receiver with a VHF/UHF antenna
  and tap Scanner. It scans `~/Scanner channels.csv`, which starts as Vermont's
  emergency channels (law enforcement, fire/EMS, interop/EOC, 347 channels), and
  stops on any channel with a signal. Tick or untick groups on the left, and pick
  how far away to listen (10, 25, 50, 100 miles or everywhere) from the grid
  square in Settings > User; statewide channels with no site are always kept.
  **Hold** stays on the channel, tapping a channel in the list holds there,
  **Skip** moves on, **Lock out** (or untick a channel) leaves it out of the scan.
  **Tune** opens a keypad to listen on any frequency the receiver reaches, and
  **Save to list** adds it to your list in the group My channels; the − and +
  beside the frequency step 12.5 kHz (5 kHz below 50 MHz).
  **Tone squelch** only stops when the channel's own PL tone is there, so other
  users of the frequency are skipped (DPL channels stop on any signal). Squelch 1
  opens on almost anything, 9 needs a strong signal; 4 suits most antennas.
  **Load a list** takes any CSV with a Frequency column (MHz), for example a
  RadioReference export, from a USB stick; Alpha Tag, Group, Agency, County,
  Tone, Mode, Latitude and Longitude columns are used when present. Analog FM
  only: P25, DMR and other digital channels are listed but not scanned.
  **Receiver** picks which SDR to use (Automatic takes an RTL-SDR, or another
  receiver when the weather radio has the RTL-SDR) and sets the gain and
  frequency correction (ppm). Audio plays on the station's speaker.
- **Gqrx** (tile, any SDR): a waterfall receiver for receive-only listening
  anywhere a receiver reaches, HF included, with the scanner's channel list as its
  bookmarks (one tag per group). With more than one receiver plugged in it asks
  which; each keeps its own Gqrx settings. Receivers that work: RTL-SDR (VHF/UHF;
  an RTL-SDR Blog V4 also does HF, and other RTL-SDR dongles get an "on HF (direct
  sampling)" choice for 0.5 to 28.8 MHz with the antenna on the dongle's input),
  Airspy HF+ and Discovery, Airspy R2/Mini, HackRF, LimeSDR, bladeRF, and any
  other SoapySDR receiver. SDRplay receivers need SDRplay's own API and the
  SoapySDRPlay3 driver installed by hand (SDRplay doesn't allow Debian to ship
  them). Airspy HF+ support depends on Debian packaging its SoapySDR driver.
  The weather radio alert listener uses the first RTL-SDR: while the Scanner or
  Gqrx has that dongle, alerts pause (the Online page says so) and resume when it
  closes; with a second receiver plugged in, the Scanner uses that instead.
  Settings > Devices lists the SDR receivers plugged in.
- **fldigi:** in Configure > Rig control > Hamlib, pick "Hamlib NET rigctl" with
  device `localhost:4532`, and pick the sound card under Audio.

Running more than one sound-card app at a time doesn't work: close one before
opening the next.

## Install

You need an x86-64 computer (a mini PC or laptop; VARA won't run on a Raspberry
Pi), a USB stick of 2 GB or more for the installer, and a wired internet
connection for the install if you can (Wi-Fi works too, see step 2).

### 1. Make the Debian installer stick

1. On any computer, download the Debian 13 "netinst" image for **amd64** from
   <https://www.debian.org/distrib/netinst>.
2. Write it to the USB stick with [balenaEtcher](https://etcher.balena.io/),
   [Raspberry Pi Imager](https://www.raspberrypi.com/software/) ("Use custom") or
   Rufus on Windows (choose "DD image" if it asks). This erases the stick.

### 2. Install Debian

Boot the station from the stick (usually F12, F2 or Esc at power-on opens the boot
menu) and choose **Install** (text) or **Graphical install**. Answer the questions
like this; anything not listed can be left at its default.

| Installer question | Answer |
| --- | --- |
| Language, location, keyboard | Yours |
| Network | Pick the wired port if plugged in, or your Wi-Fi network and password. Wi-Fi set up here keeps working after the install. |
| Hostname | `emcomm` (or any name). Leave the domain blank. |
| Root password | Either works. **Set one** and you'll use `su -` to become root. **Leave it blank** and Debian instead gives your admin user `sudo`, and you'll use `sudo -i`. |
| Full name / username / password | Your own admin account, for example `admin`. **Don't** call it `radio`: the build creates that user for the station screen. |
| Partitioning | Guided – use entire disk → the station's disk → All files in one partition → Finish → Yes. This erases that disk. |
| Package mirror | Your country → `deb.debian.org`, no proxy |
| Popularity contest | No |
| Software selection | **Untick** "Debian desktop environment" and "GNOME". **Tick only** "SSH server" and "standard system utilities". |
| Install GRUB | Yes, on the station's disk |

Remove the stick when it says the installation is complete, and let it reboot to a
text login prompt.

### 3. Build the station

Log in as your admin user, then become root: `su -` (and the root password) if you
set one in step 2, or `sudo -i` (and your own password) if you left it blank. Then
run the build:

```sh
apt update
apt install -y ansible git
git clone https://github.com/ac1sb/emcomm-station.git /root/emcomm-station
cd /root/emcomm-station
ansible-playbook site.yml
reboot
```

The build downloads about 1–2 GB (the radio apps and Wine), so it takes a while.
It ends with a summary where `failed=0` means it worked. If it stops with an error,
run `ansible-playbook site.yml` again; it picks up where it left off.

Keep the checkout at `/root/emcomm-station`, owned by root: Update station rebuilds
from there and refuses a folder that other users could change.

### 4. First boot: Settings

The station boots straight into the Settings screen.

1. Set the radio's CAT baud rate in its menu (on the FT-891 and FT-710: CAT RATE,
   38400 is a good choice), connect it by USB (and the Digirig, if you use one), and
   switch it on.
2. Enter your **callsign** and **grid square**.
3. Pick a **preset** if there's one for your setup, or pick the radio's
   **manufacturer** and **model**, then the **CAT port**, **PTT** method and port, and
   the **sound card** from the lists of plugged-in devices. Leave **GPS** on
   Automatic unless your GPS isn't a u-blox. Tap **Rescan devices** if
   you plugged something in after opening Settings.
4. Check the **baud rate** matches the radio and tap **Save and restart rig control**.

### 5. Check the radio

Open **Diagnostics** (F2). "Read frequency" should show the radio's frequency, the
sound card should be listed as `rigaudio`, and "PTT test" should key the radio for 2
seconds (connect an antenna or dummy load first).

### 6. Set up the apps

- **VARA HF / VARA FM:** tap the tile. The first time, Winlink's download page
  opens: tap "VARA HF … setup.zip" (or VARA FM). A green "Saved" bar shows and the
  window closes by itself, then setup carries on (Wine takes several
  minutes the first time). Winlink doesn't allow scripted downloads, which is why
  this step is yours. Without internet on the station, download the .zip on another
  computer, put it on a USB stick, plug it in and tap the tile.
- **Winlink mail (Pat):** open it and, on Pat's configuration page, enter your
  Winlink password. Callsign, grid and rig control are already filled in.
- **JS8Call, WSJT-X, Forms, Packet, ARDOP, APRS, Meshtastic and MeshCore** are
  ready to use once installed from their tiles. fldigi needs its rig
  control pointed at `localhost:4532` once (see "Using the apps" above).

### Backing up

Plug in a USB stick, open **Settings** and tap **Backup**, then **Back up now**. The
backup (`EmcommBackup/emcomm-backup-CALL-DATE.tar.gz` on the stick) holds the
station settings, contact notes, nets, ICS forms, My frequencies, tile pictures,
Winlink mail, and the apps' settings and logs. To move to a rebuilt or spare
station, plug the stick in there, tap **Backup** and **Restore** next to the
backup. Passwords and keys aren't in the backup, so a lost stick gives none away:
enter them again after a restore (Accounts on the Online page, and Pat's Winlink
password).

### Updating

Tap **Update station** in Settings. It downloads the latest Emcomm-CNC and installs
anything new or missing; settings are kept. You can also re-run the build by hand
as root: `cd /root/emcomm-station && git pull && ansible-playbook site.yml`.

### Accounts

The station user (`radio`) logs in automatically, has no password and can't use
`sudo` or `apt` in the terminal. That's deliberate: installing apps and updating go
through the launcher's buttons. For anything else, open the terminal in Diagnostics
and run `su -` (root password), or, if you left the root password blank,
`su - admin` (your admin username) followed by `sudo -i`. You can also log in over
SSH from another computer as your admin user; `hostname -I` in the Diagnostics
terminal shows the station's address.

Ubuntu Server 24.04 should also work if your hardware needs newer drivers.

### If something goes wrong

- **Update station (or installing an app) fails:** the end of the window says
  which step stopped and why. Everything it printed is saved in
  `/var/log/emcomm-update.log` (the run before in `.1`) and shown on the Logs page
  under **Station updates**. If CHIRP can't install, the rest of the update still
  carries on and the end of the window says so.
- **`su -` says "Authentication failure" with the right password:** the keyboard
  layout may not match what you typed during install (common in VM consoles). Type
  the password in a visible place first, such as the login prompt's username field,
  to check the characters. Or reboot, pick "Advanced options" > "recovery mode" in
  the boot menu, log in there as root and run `dpkg-reconfigure keyboard-configuration`.
- **`ansible-playbook` says it can't find `site.yml`, or the folder only has a
  README:** the copy is out of date. Run `cd /root/emcomm-station && git pull`
  and try again.
- **Update station says the folder "can be changed by" someone, or isn't owned by
  root:** as root, run
  `chown -R root:root /root/emcomm-station && chmod 755 /root/emcomm-station`.
- **Anything about a package that "is not available":** run `apt update`, then the
  build again. If it still fails, note the package name and open an issue.

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
python3 tests/test_app_setup.py
```
