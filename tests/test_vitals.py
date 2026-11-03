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

    def test_nvidia_quoted_comma_model(self):
        output = SimpleNamespace(returncode=0, stdout='"Mock, RTX", 41, 22, 1024, 8192, 80\n')
        with patch.object(cv.subprocess, "run", return_value=output):
            gpu, error = cv.gpu_reading()
        self.assertIsNone(error)
        self.assertEqual(gpu["name"], "Mock, RTX")
        self.assertEqual(gpu["mem_used"], 1024)

    def test_nvidia_na_metrics_remain_partial_reading(self):
        output = SimpleNamespace(returncode=0, stdout="RTX, N/A, N/A, 1024, 8192, N/A\n")
        with patch.object(cv.subprocess, "run", return_value=output):
            gpu, error = cv.gpu_reading()
        self.assertIsNone(error)
        self.assertEqual(gpu["name"], "RTX")
        for field in ("temp", "load", "power"):
            self.assertIsNone(gpu[field])
        self.assertEqual(gpu["mem_used"], 1024)

    def test_amd_power_from_hwmon(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            device = base / "class/drm/card0/device"
            hwmon = device / "hwmon/hwmon0"
            hwmon.mkdir(parents=True)
            (device / "vendor").write_text("0x1002")
            (device / "product_name").write_text("AMD Test")
            (device / "mem_info_vram_used").write_text("1048576")
            (device / "mem_info_vram_total").write_text("8388608")
            (hwmon / "power1_average").write_text("45000000")
            with patch.object(cv, "BASE", base), patch.object(
                cv.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="")
            ):
                gpu, error = cv.gpu_reading()
            self.assertIsNone(error)
            self.assertEqual(gpu["name"], "AMD Test")
            self.assertEqual(gpu["power"], 45.0)

    def test_amd_nonfinite_or_invalid_values(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            device = base / "class/drm/card0/device"
            sensor = device / "hwmon/hwmon0/temp1_input"
            sensor.parent.mkdir(parents=True)
            (device / "vendor").write_text("0x1002")
            (device / "product_name").write_text("AMD Partial")
            (device / "gpu_busy_percent").write_text("not-a-number")
            (device / "mem_info_vram_used").write_text("NaN")
            (device / "mem_info_vram_total").write_text("8388608")
            (device / "power1_average").write_text("N/A")
            sensor.write_text("NaN")
            with patch.object(cv, "BASE", base), patch.object(
                cv.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="")
            ):
                gpu, _ = cv.gpu_reading()
            self.assertEqual(gpu["name"], "AMD Partial")
            self.assertIsNone(gpu["load"])
            self.assertIsNone(gpu["mem_used"])
            self.assertIsNone(gpu["temp"])
            self.assertIsNone(gpu["power"])
            self.assertEqual(gpu["mem_total"], 8.0)
