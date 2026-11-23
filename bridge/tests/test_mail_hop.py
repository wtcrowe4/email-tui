import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_loader = importlib.machinery.SourceFileLoader("herdr_mail_hop", str(ROOT / "bin" / "herdr-mail-hop"))
_spec = importlib.util.spec_from_loader("herdr_mail_hop", _loader)
hop = importlib.util.module_from_spec(_spec)
_loader.exec_module(hop)


def ws(wid, label, focused=False):
    return {"workspace_id": wid, "label": label, "focused": focused}


class PickTarget(unittest.TestCase):
    def test_from_elsewhere_goes_to_email(self):
        w = [ws("a", "Work", True), ws("e", "Email"), ws("m", "Messages")]
        self.assertEqual(hop.pick_target(w, "Email", "Messages"), "e")

    def test_from_email_goes_to_messages(self):
        w = [ws("e", "Email", True), ws("m", "Messages")]
        self.assertEqual(hop.pick_target(w, "Email", "Messages"), "m")

    def test_from_messages_goes_to_email(self):
        w = [ws("e", "Email"), ws("m", "Messages", True)]
        self.assertEqual(hop.pick_target(w, "Email", "Messages"), "e")

    def test_only_messages_exists(self):
        self.assertEqual(hop.pick_target([ws("m", "Messages")], "Email", "Messages"), "m")

    def test_email_focused_without_messages_stays(self):
        self.assertEqual(hop.pick_target([ws("e", "Email", True)], "Email", "Messages"), "e")

    def test_neither(self):
        self.assertIsNone(hop.pick_target([ws("a", "Work")], "Email", "Messages"))


class PickWindow(unittest.TestCase):
    clients = [
        {"address": "0x1", "title": "host: Work", "pid": 10},
        {"address": "0x2", "title": "host: Email", "pid": 20},
    ]

    def test_title_match_wins(self):
        self.assertEqual(hop.pick_window(self.clients, "Email", []), "0x2")

    def test_falls_back_to_ancestor_pid(self):
        orig = hop.ancestors
        hop.ancestors = lambda pid: [pid, 10]
        try:
            self.assertEqual(hop.pick_window(self.clients, "Messages", [99]), "0x1")
        finally:
            hop.ancestors = orig

    def test_none(self):
        self.assertIsNone(hop.pick_window(self.clients, "Messages", []))


if __name__ == "__main__":
    unittest.main()
