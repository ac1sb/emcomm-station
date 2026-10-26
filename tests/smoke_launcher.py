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
import socketserver
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
        json.dump({"callsign": "AC1SB", "grid": "FN31", "radio_name": "FT-710", "rig_model": 1049, "cat_baud": 38400,
                   "cat_match": {"vendor": "10c4", "product": "ea70", "interface": "00"}, "ptt_method": "CAT",
                   "ptt_match": None, "audio_match": None, "data_mode": "data"}, f)
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


def fake_rigctld(commands, freq="14074000"):
    """A TCP server answering as rigctld does for a radio on 14.074 MHz; `commands` records each line."""
    state = {"ptt": "0"}

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            for raw in self.rfile:
                cmd = raw.decode().strip()
                commands.append(cmd)
                if cmd == "f":
                    reply = freq
                elif cmd == "m":
                    reply = "PKTUSB\n3000"
                elif cmd == "v":
                    reply = "VFOA"
                elif cmd == "t":
                    reply = state["ptt"]
                elif cmd.startswith("T "):
                    state["ptt"], reply = cmd[2:], "RPRT 0"
                else:
                    reply = "RPRT -11"
                self.wfile.write((reply + "\n").encode())

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    if not os.environ.get("DISPLAY"):
        skip("no X display (run under xvfb-run)")
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import GLib, Gtk
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
    # Rig control: a fake rigctld, Save through a fake emcomm-apply-settings that installs the
    # settings as given, and a fake emcomm-app-setup reporting what it set up.
    rig_commands = []
    rigctld = fake_rigctld(rig_commands)
    os.environ["EMCOMM_RIGCTLD"] = f"127.0.0.1:{rigctld.server_address[1]}"
    rig2_commands = []
    rigctld2 = fake_rigctld(rig2_commands, freq="146520000")
    os.environ.update({"EMCOMM_RIGCTLD2": f"127.0.0.1:{rigctld2.server_address[1]}",
                       "EMCOMM_RADIO2": os.path.join(tmp.name, "radio2.json"),
                       "EMCOMM_RIG2_CAT": os.path.join(tmp.name, "rig2-cat")})
    fake_apply = os.path.join(tmp.name, "emcomm-apply-settings")
    with open(fake_apply, "w", encoding="utf-8") as f:
        f.write(f"#!/bin/sh\nif [ \"$1\" = --radio2 ]; then cp \"$2\" {tmp.name}/radio2.json && echo Saved radio 2.; "
                f"exit; fi\ncp \"$1\" {os.environ['EMCOMM_STATION']} && echo Saved.\n")
    fake_setup = os.path.join(tmp.name, "emcomm-app-setup")
    with open(fake_setup, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n[ \"$1\" = radio ] || exit 2\n"
                "echo '{\"app\": \"wsjtx\", \"name\": \"WSJT-X\", \"state\": \"updated\", \"backup\": null}'\n"
                "echo '{\"app\": \"fldigi\", \"name\": \"fldigi\", \"state\": \"unchanged\", \"backup\": null}'\n"
                "echo '{\"app\": \"js8call\", \"name\": \"JS8Call\", \"state\": \"open\", \"backup\": null}'\n")
    for path in (fake_apply, fake_setup):
        os.chmod(path, 0o755)
    fake_find = os.path.join(tmp.name, "emcomm-find-radio")
    with open(fake_find, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\necho \"$@\" > " + os.path.join(tmp.name, "find-args") + "\n"
                "echo '{\"found\": true, \"model\": 1036, \"name\": \"FT-891\", \"baud\": 38400, "
                "\"freq\": \"7074000\"}'\n")
    os.chmod(fake_find, 0o755)
    os.environ["EMCOMM_FIND"] = fake_find
    os.environ.update({"EMCOMM_APPLY": fake_apply, "EMCOMM_APP_SETUP": fake_setup,
                       "EMCOMM_RIG_CAT": os.path.join(tmp.name, "rig-cat")})
    # The offline callsign list, built from the unit test's small FCC file.
    sys.path.insert(0, os.path.join(REPO, "tests"))
    import test_callsign
    fcc_zip = os.path.join(tmp.name, "l_amat.zip")
    test_callsign.fake_zip(fcc_zip)
    os.environ["EMCOMM_CALLSIGN_DB"] = os.path.join(tmp.name, "callsigns.db")
    test_callsign.cs.build(fcc_zip, os.environ["EMCOMM_CALLSIGN_DB"])
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
    win.ncs_from.set_text("K1OLD")
    pump(0.2)
    check("licence expired" in win.ncs_lookup.get_text()
          and win.ncs_lookup.get_style_context().has_class("error"), f"lookup: {win.ncs_lookup.get_text()}")
    win.ncs_from.set_text("KC1ABC")
    pump(0.2)
    check(win.ncs_lookup.get_text().startswith("KC1ABC · John Q Smith · Manchester Center, VT")
          and not win.ncs_lookup.get_style_context().has_class("error"), f"lookup: {win.ncs_lookup.get_text()}")
    win._net_add(checkin=True)
    pump(0.3)
    check(win.ncs is not None and len(win.ncs["entries"]) == 2, "net started and a check-in logged")
    check(win.ncs["entries"][-1].get("name") == "John Q Smith" and win.ncs["entries"][-1].get("state") == "VT",
          f"check-in has the name: {win.ncs['entries'][-1]}")
    check("John Q Smith, Manchester Center VT" in win.ncs_view.get_buffer().props.text, "net log shows the name")
    if os.environ.get("EMCOMM_SHOT"):  # a picture of Net control for the docs
        from gi.repository import Gdk
        win.ncs_from.set_text("K1OLD")
        pump(0.5)
        gdkwin = win.get_window()
        Gdk.pixbuf_get_from_window(gdkwin, 0, 0, gdkwin.get_width(), gdkwin.get_height()).savev(
            os.environ["EMCOMM_SHOT"], "png", [], [])
        win.ncs_from.set_text("")
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

    # ---- Settings > Radio: profiles, the rig control light, Test CAT, Test PTT, Save ----
    def answer_dialog(fill):
        """Answer the next modal dialog (its run() blocks the test): fill(dialog) returns a response."""
        def look():
            if not dialogs():
                return True
            dialog = dialogs()[0]
            dialog.response(fill(dialog))
            return False
        GLib.timeout_add(300, look)

    def dialog_widgets(dialog, kind):
        found = []

        def walk(widget):
            if isinstance(widget, kind):
                found.append(widget)
            if isinstance(widget, Gtk.Container):
                widget.foreach(walk)
        walk(dialog.get_content_area())
        return found

    win.stack.set_visible_child_name("station-radio")
    pump(2.5)
    check(win.profile_combo.get_active_id() == "FT-710", f"profile in use shown: {win.profile_combo.get_active_id()}")
    check(win.model_combo.get_active_id() == "1049" or not win.models, "FT-710's Hamlib model picked")
    check("Rig control working" in win.rig_line.get_text() and "14.074.000" in win.rig_line.get_text(),
          f"light: {win.rig_line.get_text()}")
    check(win.test_ptt_btn.get_sensitive(), "Test PTT offered while the radio answers")
    fits("Settings > Radio")
    # The window is taller than the virtual screen here; on the station the page gets 600 px less the top bar.
    room = 600 - (win.get_allocated_height() - win.stack.get_allocated_height())
    height = win.stack.get_child_by_name("station-radio").get_preferred_height()[0]
    check(height <= room, f"Settings > Radio: fits 1024x600 (needs {height} px of {room})")
    win._test_cat()
    pump(1.5)
    message = win.settings_messages[0].get_text()
    check(message.startswith("CAT works") and "14.074.000, PKTUSB on VFOA" in message, f"Test CAT: {message}")

    answer_dialog(lambda d: Gtk.ResponseType.CANCEL)
    win._test_ptt()
    pump(0.5)
    check(not any(c.startswith("T ") for c in rig_commands), "Test PTT cancelled: nothing keyed")
    answer_dialog(lambda d: Gtk.ResponseType.OK)
    win._test_ptt()
    pump(0.6)
    check("Transmitting" in win.rig_line.get_text(), f"light while keyed: {win.rig_line.get_text()}")
    pump(2.5)
    message = win.settings_messages[0].get_text()
    keys = [c for c in rig_commands if c.startswith("T ")]
    check(keys == ["T 1", "T 0"] and message.startswith("PTT works"), f"Test PTT: {keys} {message}")

    def new_from_id5100(dialog):
        dialog_widgets(dialog, Gtk.Entry)[0].set_text("ID-5100 mobile")
        start = dialog_widgets(dialog, L.PickList)[0]
        start.set_active_id("preset:id-5100-digirig")
        return Gtk.ResponseType.OK
    answer_dialog(new_from_id5100)
    win._new_profile()
    pump(0.5)
    check(win.profile_combo.get_active_id() == "ID-5100 mobile", "new profile picked")
    check(win.model_combo.get_active_id() == "3071" or not win.models, "ID-5100's Hamlib model filled in")
    check(win.data_mode_combo.get_active_id() == "none" and win.ptt_combo.get_active_id() == "RTS",
          "ID-5100: FM mode left alone, PTT by RTS")
    saved = json.load(open(L.PROFILES_PATH))["profiles"]
    check(sorted(saved) == ["FT-710", "ID-5100 mobile"], f"profiles saved: {sorted(saved)}")
    check(not win.delete_profile_btn.get_sensitive() or win.profile_combo.get_active_id() != "FT-710",
          "the profile in use can't be deleted")
    win.profile_combo.set_active_id("FT-710")
    pump(0.3)
    check(win.ptt_combo.get_active_id() == "CAT" and win.data_mode_combo.get_active_id() == "data",
          "switching back shows the FT-710")
    check(not win.allow_apps_check.get_active(), "other apps aren't changed until allowed")
    answer_dialog(lambda d: Gtk.ResponseType.CANCEL)
    win.allow_apps_check.set_active(True)
    pump(0.6)
    check(not win.allow_apps_check.get_active() and not os.path.exists(L.APP_RADIO_PATH),
          "notice declined: still not allowed")
    answer_dialog(lambda d: Gtk.ResponseType.OK)
    win.allow_apps_check.set_active(True)
    pump(0.6)
    check(win.allow_apps_check.get_active() and json.load(open(L.APP_RADIO_PATH))["allowed"] is True,
          "notice accepted: allowed")
    win.data_mode_combo.set_active_id("usb")
    win._save_settings()
    pump(2)
    message = win.settings_messages[0].get_text()
    station = json.load(open(os.environ["EMCOMM_STATION"]))
    check(station["data_mode"] == "usb" and station["radio_name"] == "FT-710", "Save installs the radio")
    check("Set up for this radio: WSJT-X and fldigi." in message and "Not changed while open: JS8Call" in message,
          f"Save says what it did to the apps: {message}")
    check(json.load(open(L.PROFILES_PATH))["profiles"]["FT-710"]["data_mode"] == "usb", "profile updated on Save")

    # ---- Find radio: the radio on the CAT port names itself; its model and baud rate are filled in ----
    ft891_port = {"vendor": "10c4", "product": "ea70", "serial": "FT891", "interface": "00"}
    devices = os.environ["EMCOMM_FAKE_DEVICES"]
    with open(devices, "w", encoding="utf-8") as f:
        json.dump({"serial": [["USB 10c4:ea70 port 0 · ttyUSB0 · CP2105", ft891_port]], "sound": [],
                   "aprs_sound": [], "serial_links": [[ft891_port, "/dev/serial/by-id/usb-Silicon_Labs_FT891-if00"]]}, f)
    win._rescan_devices()
    win.cat_combo.set_active_id("d0")
    answer_dialog(lambda d: Gtk.ResponseType.OK)
    win._find_radio()
    pump(1.5)
    message = win.settings_messages[0].get_text()
    args = open(os.path.join(tmp.name, "find-args")).read().split()
    check(args[0] == "/dev/serial/by-id/usb-Silicon_Labs_FT891-if00", f"Find radio asks about the CAT port: {args}")
    check(message.startswith("Found FT-891 at 38400 baud, on 7.074.000"), f"Find radio: {message}")
    check(win.baud_combo.get_active_id() == "38400", "baud rate filled in")
    check(win.model_combo.get_active_id() == "1036" or not win.models, "model filled in")
    win._fill_settings()

    # ---- A saved radio plugged in while another is in use: offer to switch ----
    win.profiles["FT-710"]["cat_match"] = {"vendor": "10c4", "product": "ea70", "serial": "FT710", "interface": "00"}
    win.profiles["FT-891 home"] = {"rig_model": 1036, "cat_baud": 38400, "cat_match": ft891_port, "ptt_method": "RTS",
                                   "ptt_match": None, "audio_match": None, "data_mode": "data"}
    with open(devices, "a", encoding="utf-8"):
        os.utime(devices, None)
    win._devices_seen = "before"
    win._poll_status()
    pump(2)
    offer = win._switch_dialog
    check(offer is not None and "FT-891 home is plugged in" in (offer.get_property("text") or ""),
          "offered to switch to the radio plugged in")
    if offer is not None:
        offer.response(Gtk.ResponseType.OK)
        pump(2.5)
        check(json.load(open(os.environ["EMCOMM_STATION"]))["radio_name"] == "FT-891 home", "switched to it")
        check(win.profile_combo.get_active_id() == "FT-891 home", "Radio page shows it in use")
    for d in dialogs():
        d.response(Gtk.ResponseType.OK)  # the note shown when switching away from the Radio page
    pump(0.3)

    # ---- Radio 2: a second radio alongside, its own rig control, apps picked for it ----
    win.radio_tabs[2].set_active(True)
    pump(1)
    check(win.profile_combo.get_active_id() == L.RADIO2_OFF and "Off: no second radio" in win.rig_line.get_text(),
          f"radio 2 starts off: {win.rig_line.get_text()}")
    check(not win.test_ptt_btn.get_sensitive(), "no Test PTT without a second radio")
    win.profile_combo.set_active_id("FT-710")
    pump(0.3)
    win._save_settings()
    pump(2)
    radio2 = json.load(open(os.environ["EMCOMM_RADIO2"]))
    check(radio2["radio_name"] == "FT-710", f"radio 2 saved: {win.settings_messages[0].get_text()}")
    check(json.load(open(os.environ["EMCOMM_STATION"]))["radio_name"] == "FT-891 home", "radio 1 unchanged")
    pump(3.5)
    check("146.520.000" in win.rig_line.get_text(), f"radio 2's own rig control: {win.rig_line.get_text()}")
    win._test_cat()
    pump(1.5)
    check(win.settings_messages[0].get_text().startswith("CAT works: the radio says 146.520.000"),
          f"Test CAT on radio 2: {win.settings_messages[0].get_text()}")
    check("v" in rig2_commands, "Test CAT asked radio 2's rigctld")

    def tick_packet(d):
        for c in dialog_widgets(d, Gtk.CheckButton):
            if c.get_label().startswith("Packet and APRS"):
                c.set_active(True)
        return Gtk.ResponseType.OK
    answer_dialog(tick_packet)
    win._radio_apps_dialog()
    pump(0.5)
    check(json.load(open(L.APP_RADIO_PATH))["radio2_apps"] == ["direwolf"] and
          json.load(open(L.AUDIO_PATH))["radio2_apps"] == ["direwolf"], "Packet and APRS put on radio 2")
    win.radio_tabs[1].set_active(True)
    pump(0.5)
    check(win.profile_combo.get_active_id() == "FT-891 home", "radio 1 tab shows radio 1")
    labels = [label for _id, label in win.profile_combo.items] if hasattr(win.profile_combo, "items") else []
    check(any("(radio 2)" in str(x) for x in labels) or not labels, f"profiles marked by radio: {labels}")
    win.profile_combo.set_active_id("FT-710")
    pump(0.3)
    win._save_settings()
    pump(0.5)
    check("radio 2's" in win.settings_messages[0].get_text(), "radio 2's profile can't also be radio 1")
    win._fill_settings()
    rigctld2.shutdown()
    rigctld2.server_close()
    rigctld.shutdown()
    rigctld.server_close()
    pump(3)
    check("No rig control" in win.rig_line.get_text(), f"light with rigctld gone: {win.rig_line.get_text()}")
    check(not win.test_ptt_btn.get_sensitive(), "no Test PTT without rig control")

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

    # a tile added after the operator arranged Home joins its standard folder
    apps = [{"code": c} for c in ("MSH", "MSD", "APR", "WEB")]
    std = [{"name": "Mesh & APRS", "apps": ["MSH", "MSD", "APR"]}]
    slots = L.arrange_tiles(apps, ["WEB", {"folder": "Mesh", "apps": ["APR", "MSH"]}], std)
    check([a["code"] for a in slots[1]["apps"]] == ["APR", "MSH", "MSD"] and len(slots) == 2,
          f"new tile in its folder: {slots}")
    slots = L.arrange_tiles(apps, ["WEB", "MSH", "APR"], std)
    check([s.get("code") for s in slots] == ["WEB", "MSH", "APR", "MSD"], f"no folder, new tile at the end: {slots}")
    check(L.window_app({"pid": 2, "cls": "org-meshtastic-desktop-MainKt.org-meshtastic-desktop-MainKt"},
                       [{"code": "MSD", "command": "meshtastic-desktop", "window": "meshtastic"}], {}) is not None
          and L.window_app({"pid": 2, "cls": "xterm.XTerm"}, [{"code": "MSD", "command": "meshtastic-desktop",
                                                               "window": "meshtastic"}], {}) is None,
          "a Flatpak window is matched by its class")

    # Diagnostics: a searchable list of checks, the mesh radio only when picked.
    win.stack.set_visible_child_name("home")
    pump(0.2)
    win.stack.set_visible_child_name("diagnostics")
    pump(0.5)
    check(win.diag_check.get_active_id() == "all" and "mesh" in [i for i, _ in win.diag_check.items],
          "Diagnostics: list of checks, Everything first")
    check(win.output.get_buffer().get_text(*win.output.get_buffer().get_bounds(), False).startswith(
        "$ emcomm-diag all"), "Diagnostics runs Everything when it opens")
    # Terminal: a shell as this user, touch keys, and station commands typed in at the prompt.
    if L.Vte is None:
        print("skipped: the terminal (gir1.2-vte-2.91 isn't installed)")
    else:
        def screen_text():
            try:
                return win.terminal.get_text_format(L.Vte.Format.TEXT) or ""
            except AttributeError:  # VTE before 0.76
                return win.terminal.get_text(None, None)[0] or ""

        win.open_terminal()
        pump(2)
        check(win.stack.get_visible_child_name() == "terminal" and win.term_pid, "Terminal: a shell started")
        check("Station terminal" not in screen_text() and "Terminal, as" in screen_text(),
              "Terminal: says whose shell it is (desktop mode here)")
        who = next(n for n, (_l, cmd) in enumerate(L.TERMINAL_COMMANDS) if cmd == "id")
        win.term_commands.set_active_id(str(who))
        pump(0.5)
        check(win.term_commands.get_active_id() is None and win.term_commands.label.get_text() == "Station commands…",
              "Terminal: the list goes back to its title once a command is typed in")
        win._terminal_send("\r")
        pump(1.5)
        check("uid=" in screen_text(), "Terminal: a station command runs with Enter")
        esc = L.Gdk.Event.new(L.Gdk.EventType.KEY_PRESS)
        esc.keyval, esc.state = L.Gdk.KEY_Escape, 0
        check(win._on_key(win, esc) is False and win.stack.get_visible_child_name() == "terminal",
              "Terminal: Esc is the terminal's, not Home")
        page = win.stack.get_child_by_name("terminal")
        need = page.get_preferred_width()[0]
        check(need <= 1024, f"Terminal: fits 1024 px (needs {need})")
        old_pid = win.term_pid
        win._terminal_restart()
        pump(1.5)
        check(win.term_pid and win.term_pid != old_pid, "Terminal: New starts another shell")
        os.kill(win.term_pid, 9)
        pump(1)
        check(win.term_pid is None and "The shell ended" in screen_text(), "Terminal: says when the shell ends")

    win.destroy()
    pump(0.2)
    tmp.cleanup()
    print("FAILURES:", failures or "none")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
