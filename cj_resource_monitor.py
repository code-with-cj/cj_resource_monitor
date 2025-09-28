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
