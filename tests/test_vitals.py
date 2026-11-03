"""Regressions for hardware probes and UI fallback behavior.

Uses synthetic /proc, sysfs and subprocess responses only; no real devices needed.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cute_vitals as cv

class VitalsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = cv.QApplication.instance() or cv.QApplication([])

def test_import_has_no_gui_side_effect(self):
    result = subprocess.run(
        [sys.executable, "-c", "import cute_vitals; print('import complete')"],
        cwd=Path(cv.__file__).parent, text=True, capture_output=True, timeout=8,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(result.stdout.strip(), "import complete")

def test_malformed_and_overreported_meminfo(self):
    with patch.object(cv, "read_text", return_value="MemTotal: 8192 kB\nMemFree: bad kB\nMemAvailable: 2048 kB"):
        self.assertEqual(cv.ram_reading(), (6.0, 8.0))
    with patch.object(cv, "read_text", return_value="MemTotal: 8192 kB\nMemAvailable: 99999 kB"):
        self.assertEqual(cv.ram_reading(), (0.0, 8.0))
    with patch.object(cv, "read_text", return_value="MemTotal: 0 kB\nMemAvailable: 0 kB"):
        self.assertIsNone(cv.ram_reading())
