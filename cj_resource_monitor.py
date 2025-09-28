import sys
import os
import math
import time
import threading
from pathlib import Path

import psutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt5.QtGui import QPainter, QColor, QFont, QIcon, QPixmap, QPen, QConicalGradient, QBrush
from PyQt5.QtCore import Qt, QTimer, QEasingCurve, QPropertyAnimation, QRect, QRectF

# Load LibreHardwareMonitor DLL (pythonnet / clr)

dll_candidates = [
    Path("libs/LibreHardwareMonitorLib.dll"),
    Path(__file__).parent / "libs" / "LibreHardwareMonitorLib.dll",
    Path("LibreHardwareMonitorLib.dll"),
]

LIBRE_DLL = None
for p in dll_candidates:
    if p.exists():
        LIBRE_DLL = str(p.resolve())
        break

LHM_AVAILABLE = False
if LIBRE_DLL:
    try:
        import clr
        clr.AddReference(LIBRE_DLL)
        from LibreHardwareMonitor import Hardware
        LHM_AVAILABLE = True
        print(f" LibreHardwareMonitor loaded from: {LIBRE_DLL}")
    except Exception as e:
        print(f" Failed to load LibreHardwareMonitor DLL: {e}")
        LHM_AVAILABLE = False
else:
    print(" LibreHardwareMonitorLib.dll not found in ./libs/ — GPU sensors will use fallbacks.")
