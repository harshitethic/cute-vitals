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
