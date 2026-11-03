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

    def test_proc_stat_guest_ticks_and_malformed_rows(self):
        data = ("cpu 100 20 30 200 50 10 5 5 7 8\n"
                "cpu0 60 0 10 70 10 0 0 0 5 3\n"
                "cpu1 broken data\ncpu2 1 2\nintr 12345\n")
        with patch.object(cv, "read_text", return_value=data):
            self.assertEqual(cv.cpu_stats(), [("cpu", 420, 250), ("cpu0", 150, 80)])

    def test_cpu_percent_delta_bounded_and_counter_reset(self):
        self.assertAlmostEqual(cv.cpu_percent_delta(("cpu", 100, 30), ("cpu", 200, 70)), 60.0)
        self.assertIsNone(cv.cpu_percent_delta(("cpu", 200, 80), ("cpu", 100, 30)))
        self.assertIsNone(cv.cpu_percent_delta(("cpu", 100, 30), ("cpu1", 200, 70)))
        self.assertIsNone(cv.cpu_percent_delta(("cpu", 100, 30), ("cpu", 100, 30)))
        self.assertEqual(cv.cpu_percent_delta(("cpu", 100, 30), ("cpu", 200, 200)), 0.0)
