"""Check emcomm-files finds Winlink attachments in Pat's mailbox (without downloading
them), Downloads and SSTV pictures, and saves an attachment byte for byte.

Run: python3 tests/test_files.py
"""

import importlib.machinery
import importlib.util
import os
import shutil
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/launcher/files/emcomm-files")


def load():
    loader = importlib.machinery.SourceFileLoader("emcomm_files", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_files", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


files = load()
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) + b"\r\n\r\nend"  # CRLFs inside the data too
PDF = b"%PDF-1.4\n%\xe2\xe3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def b2f(mid, subject, attachments, body=b"See attached.\r\n"):
    head = [f"Mid: {mid}", "Body: %d" % len(body), "Date: 2026/10/26 14:05", "From: W1AW",
            "To: AC1SB", "Subject: " + subject, "Type: Private"]
    head += [f"File: {len(data)} {name}" for name, data in attachments]
    out = ("\r\n".join(head) + "\r\n\r\n").encode() + body
    if attachments:
        out += b"\r\n"
    for _name, data in attachments:
        out += data + b"\r\n"
    return out


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.inbox = os.path.join(self.tmp, "mailbox/AC1SB/in")
        os.makedirs(self.inbox)
        with open(os.path.join(self.inbox, "ABC123DEF456.b2f"), "wb") as f:
            f.write(b2f("ABC123DEF456", "Shelter roster", [("roster.pdf", PDF), ("=?utf-8?q?damage_=C3=A9.png?=", PNG)]))
        with open(os.path.join(self.inbox, "NOFILES00000.b2f"), "wb") as f:
            f.write(b2f("NOFILES00000", "Just text", []))
        os.makedirs(os.path.join(self.inbox, "../sent"))
        with open(os.path.join(self.inbox, "../sent/BROKEN000000.b2f"), "wb") as f:
            f.write(b"not a message")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_lists_attachments_from_the_mailbox(self):
        rows = files.winlink_files(os.path.join(self.tmp, "mailbox"))
        self.assertEqual([(r["name"], r["kind"], r["size"], r["box"]) for r in rows],
                         [("roster.pdf", "pdf", len(PDF), "Inbox"), ("damage é.png", "image", len(PNG), "Inbox")])
        self.assertEqual((rows[0]["subject"], rows[0]["from"], rows[0]["when"]),
                         ("Shelter roster", "W1AW", "2026-10-26 14:05Z"))

    def test_extracts_byte_for_byte(self):
        message = os.path.join(self.inbox, "ABC123DEF456.b2f")
        dest = os.path.join(self.tmp, "Winlink attachments")
        png = files.extract(message, 1, dest)
        self.assertEqual(png, os.path.join(dest, "ABC123DEF456", "damage é.png"))
        with open(png, "rb") as f:
            self.assertEqual(f.read(), PNG)
        with open(files.extract(message, 0, dest), "rb") as f:
            self.assertEqual(f.read(), PDF)
        with self.assertRaises(ValueError):
            files.extract(message, 5, dest)

    def test_folders_and_kinds(self):
        down = os.path.join(self.tmp, "Downloads")
        os.makedirs(down)
        for name in ("plan.docx", "notes.txt", "big.zip", "half.pdf.part", ".hidden"):
            open(os.path.join(down, name), "w").close()
        rows = {r["name"]: r["kind"] for r in files.folder_files(down, "downloads")}
        self.assertEqual(rows, {"plan.docx": "office", "notes.txt": "text", "big.zip": "other"})
        sstv = {r["name"] for r in files.folder_files(down, "sstv")}
        self.assertEqual(sstv, set())  # only pictures count as SSTV

    def test_no_libreoffice(self):
        doc = os.path.join(self.tmp, "a.docx")
        open(doc, "w").close()
        real = files.shutil.which
        files.shutil.which = lambda _name: None
        try:
            with self.assertRaises(FileNotFoundError):
                files.to_pdf(doc, os.path.join(self.tmp, "cache"))
        finally:
            files.shutil.which = real

    @unittest.skipUnless(shutil.which("soffice"), "LibreOffice isn't installed")
    def test_office_file_to_pdf(self):
        doc = os.path.join(self.tmp, "roster.csv.txt")
        with open(doc, "w") as f:
            f.write("Name,Shelter\nPat,High school\n")
        os.rename(doc, doc[:-4])  # roster.csv
        pdf = files.to_pdf(doc[:-4], os.path.join(self.tmp, "cache"))
        with open(pdf, "rb") as f:
            self.assertTrue(f.read(5) == b"%PDF-")
        self.assertEqual(files.to_pdf(doc[:-4], os.path.join(self.tmp, "cache")), pdf)  # kept, not redone

if __name__ == "__main__":
    unittest.main()
