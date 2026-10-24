"""Drive the real launcher, headless, through the Forms page: the list of messages, nets
and forms, the ICS-213 editor, Send over the radio against a fake fldigi, ICS-309 and
ICS-205, and Net control. Catches what the unit tests can't: a page that doesn't build,
a button that doesn't show, a dialog that doesn't come back.

Needs python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-poppler-0.18 and an X display:
    xvfb-run -a python3 tests/smoke_launcher.py
Without them it says so and passes, unless EMCOMM_SMOKE_REQUIRED=1 (CI).
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import xmlrpc.server

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = os.path.join(REPO, "roles/launcher/files")


def skip(reason):
    if os.environ.get("EMCOMM_SMOKE_REQUIRED"):
        print("FAIL " + reason)
        sys.exit(1)
    print("skipped: " + reason)
    sys.exit(0)


def yaml_to_json(src, dest, key=None):
    """Convert with PyYAML from whichever python3 has it (the system one may not)."""
    code = ("import json, sys, yaml; d = yaml.safe_load(open(sys.argv[1]));"
            "json.dump(d[sys.argv[3]] if sys.argv[3] else d, open(sys.argv[2], 'w'))")
    for py in (sys.executable, "python3"):
        if subprocess.run([py, "-c", code, src, dest, key or ""], capture_output=True, check=False).returncode == 0:
            return
    skip("PyYAML isn't available to read group_vars/all.yml")


def make_station(root):
    """A scratch station: the standard tiles, a callsign, one message, one net, one form, a frequency."""
    home, etc, presets = (os.path.join(root, d) for d in ("home", "etc", "presets"))
    for d in (os.path.join(home, ".nbems/ICS/messages"), os.path.join(home, ".local/share/emcomm/nets"),
              os.path.join(home, ".local/share/emcomm/reference"), os.path.join(home, "ICS forms"), etc, presets):
        os.makedirs(d)
    with open(os.path.join(home, ".local/share/emcomm/reference/My frequencies.csv"), "w", encoding="utf-8") as f:
        f.write("Name,MHz,Mode,Offset,Tone,Note\nCounty ARES,146.940,FM,-0.6,100.0,Net Sunday 1900\n")
    yaml_to_json(os.path.join(REPO, "group_vars/all.yml"), os.path.join(etc, "vars.json"))
    with open(os.path.join(etc, "vars.json"), encoding="utf-8") as f:
        g = json.load(f)
    with open(os.path.join(etc, "launcher.json"), "w", encoding="utf-8") as f:
        json.dump({"apps": g["launcher_apps"], "folders": g["launcher_folders"]}, f)
    with open(os.path.join(etc, "station.json"), "w", encoding="utf-8") as f:
        json.dump({"callsign": "AC1SB", "grid": "FN31", "radio_name": "FT-710"}, f)
    with open(os.path.join(etc, "mode"), "w", encoding="utf-8") as f:
        f.write("desktop\n")
    with open(os.path.join(etc, "fake-devices.json"), "w", encoding="utf-8") as f:
        json.dump({"serial": [], "sound": [], "aprs_sound": []}, f)
    for name in os.listdir(os.path.join(REPO, "radios")):
        if name.endswith(".yml"):
            yaml_to_json(os.path.join(REPO, "radios", name), os.path.join(presets, name[:-4] + ".json"))
    message = {"to": "J. Smith", "p1": "Logistics", "fm": "A. Brown", "p2": "Shelter", "sb": "Cots - 50",
               "d1": "2026-10-20", "t1": "1405Z", "mg": "Need 50 cots at the high school by 1800."}
    subprocess.run(["python3", os.path.join(FILES, "emcomm-ics"), "213", "--save",
                    os.path.join(home, ".nbems/ICS/messages/ICS213-20261020-140500Z Cots.213"), "AC1SB"],
                   input=json.dumps(message), text=True, check=True, capture_output=True)
    net = {"name": "County ARES", "incident": "Flood", "operator": "Pat", "callsign": "AC1SB",
           "started": 1760896800, "closed": 1760900400,
           "entries": [{"time": 1760896800, "from": "AC1SB", "to": "", "message": "Net opened"},
                       {"time": 1760897100, "from": "W1AW", "to": "AC1SB", "message": "Checked in", "checkin": True}]}
    with open(os.path.join(home, ".local/share/emcomm/nets/20251019-180000.json"), "w", encoding="utf-8") as f:
        json.dump(net, f)
    with open(os.path.join(home, "ICS forms/ICS-309 2025-10-19 1800Z County ARES.html"), "w", encoding="utf-8") as f:
        f.write("<html><body>log</body></html>")
    os.environ.update({
        "HOME": home, "EMCOMM_LAUNCHER_CONFIG": os.path.join(etc, "launcher.json"),
        "EMCOMM_STATION": os.path.join(etc, "station.json"), "EMCOMM_MODE": os.path.join(etc, "mode"),
        "EMCOMM_FAKE_DEVICES": os.path.join(etc, "fake-devices.json"), "EMCOMM_PRESETS": presets,
        "EMCOMM_ICONS": os.path.join(FILES, "icons"), "EMCOMM_FORMS": os.path.join(FILES, "forms"),
        "EMCOMM_ICS": os.path.join(FILES, "emcomm-ics"), "EMCOMM_REFERENCE": os.path.join(FILES, "reference"),
        "EMCOMM_SAME_CODES": os.path.join(FILES, "same-codes.csv"), "EMCOMM_LAUNCHER_WINDOWED": "1",
        "EMCOMM_ONLINE": "/bin/false", "EMCOMM_RECORDER": "/bin/false", "EMCOMM_STREAM": "/bin/false",
        "EMCOMM_DISPLAY": "/bin/true", "EMCOMM_BACKUP": "/bin/false", "EMCOMM_KEYBOARD": "/bin/true",
    })
    return home


def fake_fldigi(calls):
    """An XML-RPC server answering as fldigi does; `calls` records what it was asked."""
    server = xmlrpc.server.SimpleXMLRPCServer(("127.0.0.1", 0), logRequests=False)
    server.register_function(lambda: "4.2.06", "fldigi.version")
    server.register_function(lambda: calls[-1][1] if calls and calls[-1][0] == "modem" else "BPSK31", "modem.get_name")
    server.register_function(lambda: ["BPSK31", "MT63-2000L", "MFSK32", "CW"], "modem.get_names")
    server.register_function(lambda: "TX" if calls and calls[-1][0] == "tx" and time.time() - calls[-1][1] < 3
                             else "RX", "main.get_trx_state")
    server.register_function(lambda name: calls.append(("modem", name)) or 0, "modem.set_by_name")
    server.register_function(lambda text: calls.append(("queue", text)) or 0, "text.add_tx_queu")
    server.register_function(lambda: calls.append(("tx", time.time())) or 0, "main.tx")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    if not os.environ.get("DISPLAY"):
        skip("no X display (run under xvfb-run)")
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk
    except (ImportError, ValueError) as exc:
        skip(f"GTK's Python bindings aren't installed ({exc})")

    tmp = tempfile.TemporaryDirectory()
    home = make_station(tmp.name)
    # emcomm-audio as it answers with the radio, a built-in speaker and two apps playing.
    fake_audio = os.path.join(tmp.name, "emcomm-audio")
    status = {"radio_sink": "alsa_output.usb-radio", "radio_source": "alsa_input.usb-radio",
              "speaker": "alsa_output.pci-analog", "volumes": {"to_radio": 40, "from_radio": 55, "speaker": 70},
              "speakers": [{"name": "alsa_output.pci-analog", "description": "Built-in Audio Analog Stereo",
                            "kind": "builtin"},
                           {"name": "alsa_output.usb-headset", "description": "USB Headset", "kind": "usb"}],
              "streams": [{"index": 7, "app": "WSJT-X", "key": "wsjt-x", "radio_app": True, "place": "radio",
                           "sink": "FT-710"},
                          {"index": 8, "app": "Scanner", "key": "scanner", "radio_app": False, "place": "speaker",
                           "sink": "Built-in Audio Analog Stereo"}]}
    with open(fake_audio, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\ncase \"$1\" in\n  status) cat <<'EOF'\n" + json.dumps(status) + "\nEOF\n;;\n"
                "  target|speaker) echo alsa_output.pci-analog ;;\n  watch) exec sleep 20 ;;\nesac\n")
    os.chmod(fake_audio, 0o755)
    os.environ["EMCOMM_AUDIO"] = fake_audio
    loader = importlib.machinery.SourceFileLoader("emcomm_launcher", os.path.join(FILES, "emcomm-launcher"))
    spec = importlib.util.spec_from_loader("emcomm_launcher", loader)
    L = importlib.util.module_from_spec(spec)
    loader.exec_module(L)
    if L.Poppler is None:
        skip("gir1.2-poppler-0.18 isn't installed")
    failures = []

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(0.02)

    def check(cond, what):
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)

    def rows():
        return [r for r in win.forms_list.get_children() if hasattr(r, "item")]

    def dialogs():
        return [w for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.Dialog) and w.get_visible()]

    def fits(what):
        # The station's screen is 1024 px wide: the window mustn't ask for more.
        width = win.get_preferred_width()[0]
        check(width <= 1024, f"{what}: fits 1024 px (needs {width})")

    def visible_buttons():
        return sorted(b.get_label() for btns in win.forms_kind_btns.values() for b in btns if b.get_visible())

    win = L.Launcher(L.load_config())
    win.show_all()
    pump(1)

    # ---- the Forms list: a message, a net and a form, each with its own preview and buttons ----
    win.stack.set_visible_child_name("forms")
    pump(3)
    check(sorted(r.item["kind"] for r in rows()) == ["213", "309", "net"], f"list kinds {[r.item['kind'] for r in rows()]}")
    wanted = {"213": ["More  ▾", "Reply / Edit", "Send by radio"],
              "net": ["ICS-309 log", "Net control  F8"], "309": ["Open / Print"]}
    for row in rows():
        win.forms_list.select_row(row)
        pump(0.5)
        kind = row.item["kind"]
        check(win.forms_item is row.item, f"{kind}: selected")
        check(win.forms_view.get_visible_child_name() == ("pdf" if kind == "213" else "text"), f"{kind}: preview")
        check(visible_buttons() == wanted[kind], f"{kind}: buttons {visible_buttons()}")
        fits(f"Forms with a {kind} picked")
        if kind == "213":
            check(win.f213_doc is not None and win.f213_send_btn.get_sensitive(), "213: form drawn, Send enabled")
        if kind == "net":
            buf = win.forms_text.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            check("County ARES" in text and "W1AW" in text, "net: log shown")
    win.forms_filter.set_active_id("net")
    pump(0.5)
    check(len(rows()) == 1 and rows()[0].item["kind"] == "net", "filter: nets only")
    win.forms_filter.set_active_id("all")
    pump(0.5)

    # ---- New ▾ ICS-213: typed on the form, saved, picked in the list ----
    win._ics213_write(None)
    pump(0.5)
    check(win.stack.get_visible_child_name() == "ics213-edit", "editor opened")
    check(win._ics213_field("t1").endswith("Z"), "time in UTC")
    fits("ICS-213 editor")
    # The form follows the window's width, so check the editor's buttons on their own too.
    header = win.f213e_title.get_parent().get_preferred_width()[0]
    check(header <= 1024 - 40, f"ICS-213 editor buttons fit (need {header})")
    win.f213e_fields["to"].set_text("W1AW")
    win.f213e_fields["sb"].set_text("Smoke test")
    win.f213e_fields["mg"].get_buffer().set_text("Hello from the smoke test")
    path = win._ics213_editor_save()
    check(bool(path) and os.path.exists(path), "saved in flmsg's messages folder")
    win.stack.set_visible_child_name("forms")
    pump(5)
    check(rows() and rows()[0].item["title"] == "Smoke test", "new message tops the list")
    check(win.forms_item is rows()[0].item and win.f213_path == path, "and is picked, ready to send")

    # ---- Send over the radio: fldigi not running ----
    win._forms_send()
    pump(3)
    check(len(dialogs()) == 1, "send dialog opens")
    if dialogs():
        d = dialogs()[0]
        status = [c for c in d.get_content_area().get_children() if isinstance(c, Gtk.Label)][1]
        start, send = d.get_widget_for_response(1), d.get_widget_for_response(Gtk.ResponseType.OK)
        check("isn't running" in status.get_text() and start.get_visible() and not send.get_sensitive(),
              f"offline: {status.get_text()[:70]}")
        d.response(Gtk.ResponseType.CLOSE)
        pump(0.5)
    check(not dialogs(), "dialog closes")

    # ---- Send over the radio: a fake fldigi answers ----
    calls = []
    server = fake_fldigi(calls)
    os.environ["EMCOMM_FLDIGI"] = f"http://127.0.0.1:{server.server_address[1]}/"
    win._forms_send()
    pump(3)
    check(len(dialogs()) == 1, "send dialog opens with fldigi up")
    if dialogs():
        d = dialogs()[0]
        status = [c for c in d.get_content_area().get_children() if isinstance(c, Gtk.Label)][1]
        send = d.get_widget_for_response(Gtk.ResponseType.OK)
        modem = next(w for box in d.get_content_area().get_children() if isinstance(box, Gtk.Box)
                     for w in box.get_children() if isinstance(w, L.PickList))
        check("fldigi is running" in status.get_text() and send.get_sensitive(), f"online: {status.get_text()[:60]}")
        check(modem.get_active_id() == "BPSK31", "modem defaults to the one fldigi is on")
        modem.set_active_id("MT63-2000L")
        d.response(Gtk.ResponseType.OK)
        pump(2)
        check("transmit buffer" in status.get_text() or "Transmitting" in status.get_text(),
              f"sending: {status.get_text()[:60]}")
        pump(6)
        check("back on receive" in status.get_text(), f"done: {status.get_text()[:60]}")
        check([c[0] for c in calls] == ["modem", "queue", "tx"] and calls[0][1] == "MT63-2000L",
              f"fldigi asked to {[c[0] for c in calls]}")
        check("[WRAP:fn " in calls[1][1] and calls[1][1].endswith("[WRAP:end]\n... end\n\n\n^r"), "wrapped text queued")
        check(os.path.exists(os.path.join(home, ".nbems/WRAP/send", os.path.basename(path) + ".wrap")), "copy kept")
        check(win.f213_status.get_text().startswith("Sent "), f"page says: {win.f213_status.get_text()[:60]}")
        d.response(Gtk.ResponseType.CLOSE)
        pump(0.5)
    server.shutdown()
    server.server_close()

    # ---- ICS-309 for the net picked; ICS-205 ----
    win.forms_list.select_row(next(r for r in rows() if r.item["kind"] == "net"))
    pump(0.5)
    win._forms_ics309()
    pump(0.5)
    form = os.path.join(home, "ICS forms/ICS-309 2025-10-19 1800Z County ARES.html")
    check(win.f213_status.get_text().startswith("Saved to") and time.time() - os.path.getmtime(form) < 10,
          f"309: {win.f213_status.get_text()[:60]}")
    win._forms_ics205()
    pump(0.5)
    check(win.f213_status.get_text().startswith("Saved to"), f"205: {win.f213_status.get_text()[:60]}")

    # ---- New ▾ Net log: Net control, a check-in, the open net tops the Forms list ----
    win._forms_new_net()
    pump(0.5)
    check(win.stack.get_visible_child_name() == "net", "Net control opened")
    win.ncs_name.set_text("Smoke net")
    win._net_start_or_close()
    pump(0.3)
    win.ncs_from.set_text("K1ABC")
    win._net_add(checkin=True)
    pump(0.3)
    check(win.ncs is not None and len(win.ncs["entries"]) == 2, "net started and a check-in logged")
    win.stack.set_visible_child_name("forms")
    pump(5)
    check(rows() and rows()[0].item["kind"] == "net" and rows()[0].item.get("open"), "open net tops the list")
    # With a net open the list stays put (it isn't rebuilt every check) and a note isn't overwritten.
    win._forms_ics205()
    pump(5)  # the new ICS-205 file joins the list once
    before = rows()
    pump(9)
    check(rows() == before, "open net: list not rebuilt")
    check(win.f213_status.get_text().startswith("Saved to"), f"205 note kept: {win.f213_status.get_text()[:60]}")
    win.stack.set_visible_child_name("logs")
    pump(0.5)
    check(win.stack.get_visible_child_name() == "logs", "Logs page")

    # ---- Reference: the lists, the search and band filter, the row the radio is on ----
    win.stack.set_visible_child_name("reference")
    pump(1)
    for section in list(win.ref_sections) + [None]:
        if section:
            win.ref_combo.set_active_id(section)
            pump(0.3)
        header = win.stack.get_child_by_name("reference").get_children()[0]
        room = win.get_allocated_width() - 40
        # The minimum: the status line is cut with "…" rather than widening the window.
        check(header.get_preferred_width()[0] <= room,
              f"Reference header fits ({header.get_preferred_width()[0]} of {room}) on {win.ref_sections.get(section, 'start')}")
    titles = list(win.ref_sections.values())
    check("Other services (listen)" in titles and "Emergency and calling" in titles, f"sections {titles}")
    check(win.ref_hint.get_text().split(" at ")[0] in ("Day", "Night", "Dusk or dawn"), f"hint: {win.ref_hint.get_text()[:60]}")
    emergency = next(p for p, t in win.ref_sections.items() if t == "Emergency and calling")
    win.ref_combo.set_active_id(emergency)
    pump(0.5)
    ref_rows = lambda: [c for c in win.ref_list.get_children() if hasattr(c.get_child(), "mhz")]
    check(len(ref_rows()) == 22, f"emergency list rows {len(ref_rows())}")
    win.ref_search.set_text("hurricane")
    pump(0.5)
    check(len(ref_rows()) == 2, f"search narrows to {len(ref_rows())}")
    win.ref_search.set_text("")
    win.ref_band.set_active_id("2 m")
    pump(0.5)
    check([c.get_child().mhz for c in ref_rows()] == [144.2, 146.52, 144.39], f"band filter {[c.get_child().mhz for c in ref_rows()]}")
    win.ref_band.set_active_id("all")
    pump(0.3)
    win.rig_hz = 146_520_000
    win._reference_mark_current()
    lit = [c.get_child().mhz for c in ref_rows() if c.get_child().get_style_context().has_class("current")]
    check(lit == [146.52], f"radio's row highlighted {lit}")
    row = next(c.get_child() for c in ref_rows() if c.get_child().mhz == 146.52)
    save = [b for b in row.get_children() if isinstance(b, Gtk.Button) and b.get_label() == "Save to mine"][0]
    save.clicked()
    pump(0.5)
    check(win.ref_status.get_text().startswith("Saved "), f"save to mine: {win.ref_status.get_text()[:50]}")
    save.clicked()
    pump(0.3)
    check("already" in win.ref_status.get_text(), "saving twice is noticed")
    win.ref_combo.set_active_id(L.MY_FREQS)
    pump(0.5)
    mine_buttons = [b.get_label() for b in ref_rows()[0].get_child().get_children() if isinstance(b, Gtk.Button)] if ref_rows() else []
    # 146.940 was there from the start (the ICS-205 needs a list); 146.520 was just saved.
    check([c.get_child().mhz for c in ref_rows()] == [146.94, 146.52] and sorted(mine_buttons) == ["Edit", "Tune"],
          f"My frequencies: {[c.get_child().mhz for c in ref_rows()]}, {mine_buttons}")
    tune = [b for b in ref_rows()[0].get_child().get_children() if isinstance(b, Gtk.Button) and b.get_label() == "Tune"][0]
    tune.clicked()
    pump(3)
    check("didn't take" in win.ref_status.get_text(), f"tune without a rig: {win.ref_status.get_text()[:50]}")
    # importing a CHIRP export and a RepeaterBook-style download
    chirp = os.path.join(home, "chirp.csv")
    with open(chirp, "w", encoding="utf-8") as f:
        f.write("Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment\n"
                "0,W1XYZ,146.940000,-,0.600000,Tone,100.0,100.0,023,NN,FM,5.00,,Command\n"
                "1,SIMPLEX,146.520000,,0.600000,,88.5,88.5,023,NN,NFM,5.00,,\n"
                "2,BAD,,,,,,,,,,,,\n")
    rows = L.import_freqs(chirp)
    check([(r["MHz"], r["Offset"], r["Tone"], r["Mode"]) for r in rows] == [(146.94, -0.6, 100.0, "FM"), (146.52, None, None, "FM")],
          f"CHIRP import {[(r['MHz'], r['Offset'], r['Tone']) for r in rows]}")
    rb = os.path.join(home, "repeaterbook.csv")
    with open(rb, "w", encoding="utf-8") as f:
        f.write("Frequency,Offset,Uplink Tone,Call Sign,Nearest City,Mode\n3945,,,,Net,LSB\n448.325,-5,123.0 PL,KC1ABC,Rutland,FM\n")
    rows = L.import_freqs(rb)
    check([(r["MHz"], r["Mode"], r["Offset"], r["Tone"], r["Name"], r["Note"]) for r in rows]
          == [(3.945, "LSB", None, None, "3.945 MHz", "Net"), (448.325, "FM", -5.0, 123.0, "KC1ABC", "Rutland")],
          f"RepeaterBook import {rows}")
    merged, added, skipped = L.merge_freqs(L.read_freqs(L.MY_FREQS), rows + L.import_freqs(chirp))
    check((added, skipped, len(merged)) == (2, 2, 4), f"merge added {added} skipped {skipped} (146.94 and 146.52 were there)")
    # 23 cm stays in MHz, 160 m in kHz comes down; CHIRP's TSQL tone is cToneFreq; a Windows-saved file
    odd = os.path.join(home, "odd.csv")
    with open(odd, "wb") as f:
        f.write("Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,Mode,Comment\n"
                "0,W1GHZ,1293.100000,-,12.000000,TSQL,88.5,123.0,FM,Montr\u00e9al\n"
                "1,TOPBAND,1850,,,,88.5,88.5,LSB,\n".encode("cp1252"))
    rows = L.import_freqs(odd)
    check([(r["MHz"], r["Offset"], r["Tone"], r["Note"]) for r in rows] == [(1293.1, -12.0, 123.0, "Montr\u00e9al"),
                                                                           (1.85, None, None, "")],
          f"23 cm, kHz, TSQL, cp1252 {[(r['MHz'], r['Offset'], r['Tone'], r['Note']) for r in rows]}")
    # Save to mine from the gateway finder: just the list's columns, and no "open now" kept
    gateway = {"MHz": 145.05, "Mode": "FM", "Name": "W1GW  ·  Packet", "Note": "Rutland · hours 00-23 UTC · open now",
               "miles": 12.0}
    win._save_to_mine(gateway)
    saved = [r for r in L.read_freqs(L.MY_FREQS) if r["MHz"] == 145.05]
    check(saved and saved[0]["Note"] == "Rutland · hours 00-23 UTC", f"gateway saved: {saved}")
    # receive-only rows stay out of CHIRP's copy (it could transmit on them)
    chirp_out = os.path.join(home, "chirp-out.csv")
    L.export_chirp([{"MHz": 162.55, "Mode": "FM", "Name": "WX1", "Note": "Receive only", "Offset": None, "Tone": None},
                    {"MHz": 146.52, "Mode": "FM", "Name": "Calling", "Note": "", "Offset": None, "Tone": None}], chirp_out)
    with open(chirp_out, encoding="utf-8") as f:
        out = f.read()
    check("146.52" in out and "162.55" not in out, "CHIRP copy leaves out receive-only rows")
    try:
        L.import_freqs(os.path.join(home, "ICS forms", "ICS-309 2025-10-19 1800Z County ARES.html"))
        check(False, "a file with no frequency column is refused")
    except ValueError:
        check(True, "a file with no frequency column is refused")
    # the sun, and the which-band hint
    noon = L.sun_elevation(43.0, -73.0, 1750525200)  # 2025-06-21 17:00Z: 1 pm in Vermont, sun about 70 degrees up
    evening = L.sun_elevation(43.0, -73.0, 1750550400)  # 00:00Z: 8 pm, half an hour before sunset
    night = L.sun_elevation(43.0, -73.0, 1750572000)  # 06:00Z: 2 am
    check(60 < noon < 75 and 0 < evening < 10 and night < -15, f"sun elevation {noon:.0f} / {evening:.0f} / {night:.0f}")
    check(L.band_hint("FN31", when=1750510800).startswith("Day at FN31: nearby 40 m"), L.band_hint("FN31", when=1750510800))
    check(L.band_hint("FN31", when=1750572000).startswith("Night at FN31"), L.band_hint("FN31", when=1750572000))
    check("Online: 80m-40m Good" in L.band_hint("FN31", when=1750510800, conditions={"80m-40m": {"day": "Good"}}), "hint with conditions")
    check(L.band_hint("") .startswith("Set your grid"), "hint without a grid")
    check((L.gateway_open("00-23"), L.gateway_open("?"), L.gateway_open("22-04", now=1750510800)) == ("open now", "", "opens 2200Z"),
          "gateway hours")

    # ---- Settings > Audio: levels, the listening speaker, what's playing where ----
    win.stack.set_visible_child_name("audio")
    pump(2)
    check(all(sc.get_sensitive() for sc in win.audio_sliders.values()), "audio level sliders usable")
    check([round(win.audio_sliders[k].get_value()) for k in ("to_radio", "from_radio", "speaker")] == [40, 55, 70],
          "audio levels read back")
    check(win.audio_speaker_pick.get_active_text() == "Automatic (Built-in Audio Analog Stereo)",
          f"listening speaker: {win.audio_speaker_pick.get_active_text()}")
    check(len(win.audio_speaker_pick.items) == 3, "speakers listed, the USB headset among them")
    rows_now = win.audio_streams_box.get_children()
    check(len(rows_now) == 2, f"apps playing now: {len(rows_now)} rows")
    fits("Settings > Audio")
    win.stack.set_visible_child_name("home")
    pump(0.3)
    check(not win.audio_meter_procs, "level meters stop when the page closes")

    # ---- tapping a tile: a flash, then "Opening…" until the app's window appears ----
    win.stack.set_visible_child_name("home")
    pump(0.5)
    windows = []
    L.open_windows = lambda: list(windows)  # no window manager here: say which windows are up
    L.OPENING_TIMEOUT = 3
    tile = win._tile({"code": "TST", "name": "Test app", "command": "sleep", "run": ["sleep", "30"],
                      "detail": "A test"})
    tile.show_all()
    tile.clicked()
    check(tile.get_style_context().has_class("tapped"), "tap flashes the tile")
    first = win.started.get("TST")
    check(tile.opening and tile.spinner.get_visible() and tile.detail.get_text() == "Opening…",
          f"opening shown: {tile.detail.get_text()}")
    pump(0.5)
    check(not tile.get_style_context().has_class("tapped"), "flash fades")
    tile.clicked()
    check(win.started.get("TST") == first, "a second tap while opening doesn't start a second copy")
    windows.append({"id": 1, "pid": first, "cls": "sleep.Sleep", "title": "Test app"})
    pump(1.5)
    check(not tile.opening and not tile.spinner.get_visible() and tile.detail.get_text() == "A test",
          f"window up: {tile.detail.get_text()}")
    os.kill(first, 15)
    windows.clear()
    failing = win._tile({"code": "BAD", "name": "Bad app", "command": "false", "run": ["false"], "detail": "x"})
    failing.show_all()
    failing.clicked()
    pump(1.5)
    check(not failing.opening and failing.detail.get_text() == "Didn't start", f"failed: {failing.detail.get_text()}")
    slow = win._tile({"code": "SLOW", "name": "Slow app", "command": "sleep", "run": ["sleep", "10"], "detail": "x"})
    slow.show_all()
    slow.clicked()
    pump(4)
    check(not slow.opening and slow.detail.get_text() == "No window yet", f"no window: {slow.detail.get_text()}")
    os.kill(win.started["SLOW"], 15)
    folder = next((t for t in win.slots if getattr(t, "kind", None) == "folder"), None)
    if folder is not None:
        folder.clicked()
        check(folder.get_style_context().has_class("tapped") and win.stack.get_visible_child_name() == "folder",
              "folder tap flashes and opens")

    win.destroy()
    pump(0.2)
    tmp.cleanup()
    print("FAILURES:", failures or "none")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
