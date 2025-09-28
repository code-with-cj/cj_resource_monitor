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

# If LHM available, prepare Computer object
computer = None
if LHM_AVAILABLE:
    try:
        computer = Hardware.Computer()
        computer.IsCpuEnabled = True
        computer.IsMemoryEnabled = True
        computer.IsGpuEnabled = True
        computer.IsMotherboardEnabled = True
        computer.IsStorageEnabled = True
        computer.Open()
        print(" LibreHardwareMonitor Computer initialized successfully")
    except Exception as e:
        print(f" Error initializing LHM Computer: {e}")
        computer = None
        LHM_AVAILABLE = False


# CircularMeter widget with improved text rendering

class CircularMeter(QWidget):
    def __init__(self, label: str, diameter=160, parent=None):
        super().__init__(parent)
        self.label = label
        self.value = 0.0  # 0..100
        self.info = ""
        self.diameter = diameter
        self.is_dark_mode = True
        
        # Set fixed size with padding for info text
        self.setFixedSize(diameter + 20, diameter + 60)  
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # Fonts
        self._font_value = QFont("Segoe UI", 18, QFont.Bold)
        self._font_label = QFont("Segoe UI", 11, QFont.Bold)
        self._font_info = QFont("Segoe UI", 9)

    def set_dark_mode(self, is_dark):
        self.is_dark_mode = is_dark
        self.update()

    def set_value(self, percent: float, info: str = ""):
        self.value = max(0.0, min(100.0, float(percent)))
        self.info = info
        self.update()

    def get_color_for_value(self, percent):
        """Get color based on percentage value"""
        if percent <= 20:
            return QColor("#00ff88")  # Green
        elif percent <= 40:
            return QColor("#00d4ff")  # Cyan
        elif percent <= 60:
            return QColor("#ffd700")  # Yellow
        elif percent <= 80:
            return QColor("#ff8c00")  # Orange
        else:
            return QColor("#ff4757")  # Red

    def get_text_color(self):
        """Get appropriate text color based on theme"""
        return QColor("white") if self.is_dark_mode else QColor("#333333")

    def get_secondary_text_color(self):
        """Get secondary text color based on theme"""
        return QColor("#cccccc") if self.is_dark_mode else QColor("#666666")

    def get_track_color(self):
        """Get track color based on theme"""
        return QColor("#404040") if self.is_dark_mode else QColor("#e0e0e0")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate dimensions
        widget_rect = self.rect()
        center_x = widget_rect.width() // 2
        center_y = self.diameter // 2 + 10  
        radius = (self.diameter - 24) // 2 
        
        # Ensure valid dimensions
        if radius <= 0:
            return

        # Calculate drawing rectangle
        draw_x = int(center_x - radius)
        draw_y = int(center_y - radius)
        draw_size = int(radius * 2)
        
        # Background circle (track)
        pen = QPen(self.get_track_color(), 6, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(draw_x, draw_y, draw_size, draw_size)

        # Progress arc
        if self.value > 0:
            start_angle = 90 * 16  # Start from top
            span_angle = int(-(360 * self.value / 100) * 16)  
            
            arc_color = self.get_color_for_value(self.value)
            pen = QPen(arc_color, 6, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(draw_x, draw_y, draw_size, draw_size, start_angle, span_angle)

        # Center percentage text
        painter.setPen(self.get_text_color())
        painter.setFont(self._font_value)
        text_rect = QRect(draw_x, int(center_y - 12), draw_size, 24)
        painter.drawText(text_rect, Qt.AlignCenter, f"{int(self.value)}%")

        # Label below circle with proper spacing
        painter.setFont(self._font_label)
        painter.setPen(self.get_text_color())
        label_y = center_y + radius + 15  
        label_rect = QRect(0, int(label_y), widget_rect.width(), 20)
        painter.drawText(label_rect, Qt.AlignCenter, self.label)

        # Info text below label with more spacing
        if self.info:
            painter.setFont(self._font_info)
            painter.setPen(self.get_secondary_text_color())
            info_y = label_y + 25  
            info_rect = QRect(0, int(info_y), widget_rect.width(), 16)
            painter.drawText(info_rect, Qt.AlignCenter, self.info)

# Mini Status Widget (Text-based)

class MiniStatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setFixedSize(300, 36)  
        
        # Dark background with no border
        self.setStyleSheet("""
            background-color: #1a1c1e; 
            color: white; 
            border: none; 
            border-radius: 8px;
            padding: 8px;
        """)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4) 
        layout.setSpacing(0)
        
        # Status label with bold font
        self.status_label = QLabel("CPU 0% | RAM 0% | GPU 0%")
        self.status_label.setFont(QFont("Segoe UI", 9, QFont.Bold))  
        self.status_label.setStyleSheet("color: white; background: transparent;")
        
        # Restore button
        self.restore_btn = QPushButton("⬆")
        self.restore_btn.setFixedSize(30, 30)  # Smaller button
        self.restore_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))  
        self.restore_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)
        
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.restore_btn)

    def update_status(self, cpu_percent, ram_percent, gpu_percent):
        """Update the status text"""
        status_text = f"CPU {int(cpu_percent)}% | RAM {int(ram_percent)}% | GPU {int(gpu_percent)}%"
        self.status_label.setText(status_text)

    def position_at_top_right(self):
        """Position widget at top-right of screen"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.width() - self.width() - 20
        y = 20
        self.move(x, y)

# Main Window

class MonitorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(" CJ Resource Monitor Pro | CODE with CJ")
        
        # Window dimensions
        self.full_w = 980
        self.full_h = 580
        
        self.resize(self.full_w, self.full_h)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        
        # Theme state
        self.is_dark_mode = True
        
        # Setup UI
        self.setup_ui()
        self.apply_theme()
        
        # Setup mini widget
        self.mini_widget = MiniStatusWidget()
        self.mini_widget.restore_btn.clicked.connect(self.exit_mini_mode)
        
        # Timer for stats updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)
        
        # Network monitoring
        self.last_net = psutil.net_io_counters()
        self.last_time = time.time()
        
        # Center window
        self.center_window()

    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Left spacer (invisible placeholder to balance the right buttons)
        left_spacer = QWidget()
        left_spacer.setFixedSize(110, 45)  # Same total width as right buttons + spacing
        
        # Title (centered)
        self.title_label = QLabel("⚡ CJ RESOURCE MONITOR ⚡")
        self.title_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Theme toggle button
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setFixedSize(45, 45)
        self.theme_btn.setFont(QFont("Segoe UI", 18))
        self.theme_btn.setToolTip("Toggle Theme")
        self.theme_btn.clicked.connect(self.toggle_theme)
        
        # Mini mode button
        self.mini_btn = QPushButton("─")
        self.mini_btn.setFixedSize(45, 45)
        self.mini_btn.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self.mini_btn.setToolTip("Minimize to Status Bar")
        self.mini_btn.clicked.connect(self.enter_mini_mode)
        
        controls_layout.addWidget(self.theme_btn)
        controls_layout.addWidget(self.mini_btn)
        
        # Add widgets to header with equal spacing
        header_layout.addWidget(left_spacer)  # Left balance
        header_layout.addWidget(self.title_label, 1)  # Center with stretch
        header_layout.addLayout(controls_layout)  # Right buttons
        
        main_layout.addLayout(header_layout)

        # Meters section
        meters_layout = QHBoxLayout()
        meters_layout.setSpacing(30)  # More spacing between meters
        
        # Create meters
        self.cpu_meter = CircularMeter("CPU Usage", diameter=160)
        self.ram_meter = CircularMeter("RAM Usage", diameter=160)
        self.gpu_meter = CircularMeter("GPU Usage", diameter=160)
        self.net_meter = CircularMeter("Network", diameter=160)
        
        meters_layout.addWidget(self.cpu_meter, alignment=Qt.AlignCenter)
        meters_layout.addWidget(self.ram_meter, alignment=Qt.AlignCenter)
        meters_layout.addWidget(self.gpu_meter, alignment=Qt.AlignCenter)
        meters_layout.addWidget(self.net_meter, alignment=Qt.AlignCenter)
        
        main_layout.addLayout(meters_layout)

        # System info section
        self.system_info = QLabel(" System Information Loading...")
        self.system_info.setFont(QFont("Segoe UI", 10))
        self.system_info.setAlignment(Qt.AlignCenter)
        self.system_info.setWordWrap(True)
        main_layout.addWidget(self.system_info)

def apply_theme(self):
        """Apply theme to the entire application"""
        if self.is_dark_mode:
            # Dark theme
            self.setStyleSheet("""
                QWidget {
                    background-color: #1a1c1e;
                    color: white;
                }
                QPushButton {
                    background-color: #2d3142;
                    border: 2px solid #4f5b66;
                    border-radius: 12px;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #3d4152;
                    border-color: #6f7b86;
                }
                QPushButton:pressed {
                    background-color: #1d2132;
                }
                QLabel {
                    color: white;
                }
            """)
            
            self.title_label.setStyleSheet("color: #0066cc; font-weight: bold;")
            self.system_info.setStyleSheet("""
                color: #cccccc; 
                padding: 15px; 
                background-color: rgba(255,255,255,0.05); 
                border-radius: 10px;
                border: 1px solid #333333;
            """)
            
        else:
            # Light theme
            self.setStyleSheet("""
                QWidget {
                    background-color: #f8f9fa;
                    color: #333333;
                }
                QPushButton {
                    background-color: #e9ecef;
                    border: 2px solid #ced4da;
                    border-radius: 12px;
                    color: #333333;
                }
                QPushButton:hover {
                    background-color: #dee2e6;
                    border-color: #adb5bd;
                }
                QPushButton:pressed {
                    background-color: #ced4da;
                }
                QLabel {
                    color: #333333;
                }
            """)
            
            self.title_label.setStyleSheet("color: #0066cc; font-weight: bold;")
            self.system_info.setStyleSheet("""
                color: #495057; 
                padding: 15px; 
                background-color: rgba(0,0,0,0.05); 
                border-radius: 10px;
                border: 1px solid #dee2e6;
            """)
        
        # Update meters theme
        for meter in [self.cpu_meter, self.ram_meter, self.gpu_meter, self.net_meter]:
            meter.set_dark_mode(self.is_dark_mode)

def center_window(self):
        """Center the window on screen"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

def toggle_theme(self):
        """Toggle between dark and light themes"""
        self.is_dark_mode = not self.is_dark_mode
        self.theme_btn.setText("☀️" if self.is_dark_mode else "🌙")
        self.apply_theme()

def enter_mini_mode(self):
        """Switch to mini text-based mode"""
        self.hide()
        self.mini_widget.position_at_top_right()
        self.mini_widget.show()

def exit_mini_mode(self):
        """Switch back to full mode"""
        self.mini_widget.hide()
        self.center_window()
        self.show()
        self.raise_()
def get_gpu_usage(self):
        """Get GPU usage with improved LibreHardwareMonitor integration"""
        gpu_percent = 0.0
        gpu_name = "Integrated Graphics"
        
        if LHM_AVAILABLE and computer:
            try:
                for hw in computer.Hardware:
                    hw.Update()
                    
                    # Check for any GPU type
                    if hw.HardwareType in (Hardware.HardwareType.GpuNvidia,
                                         Hardware.HardwareType.GpuAmd,
                                         Hardware.HardwareType.GpuIntel):
                        
                        gpu_name = hw.Name
                        print(f"🎮 Found GPU: {gpu_name}")  # Debug info
                        
                        # Look through all sensors
                        for sensor in hw.Sensors:
                            sensor_name = sensor.Name or ""
                            sensor_value = sensor.Value
                            
                            print(f"   Sensor: {sensor_name} = {sensor_value} ({sensor.SensorType})")  # Debug
                            
                            # Look for GPU Core Load or similar
                            if (sensor.SensorType == Hardware.SensorType.Load and 
                                sensor_value is not None):
                                
                                if any(keyword in sensor_name.lower() for keyword in 
                                      ['gpu', 'core', 'load', '3d', 'graphics']):
                                    gpu_percent = max(gpu_percent, float(sensor_value))
                                    print(f"  Using sensor: {sensor_name} = {gpu_percent}%")
                        
                        # If we found a GPU but no load sensors, try alternative approach
                        if gpu_percent == 0.0:
                            for sensor in hw.Sensors:
                                if (sensor.SensorType == Hardware.SensorType.Load and 
                                    sensor.Value is not None):
                                    gpu_percent = float(sensor.Value)
                                    print(f"  Using first Load sensor: {sensor.Name} = {gpu_percent}%")
                                    break
                        
                        if gpu_percent > 0:
                            break  # Found working GPU
                            
            except Exception as e:
                print(f" GPU monitoring error: {e}")
                gpu_percent = 0.0
        
        # Fallback if no valid GPU data
        if gpu_percent == 0.0:
            # Use CPU-based approximation for systems without discrete GPU
            cpu_percent = psutil.cpu_percent()
            gpu_percent = min(cpu_percent * 0.3, 100.0)  # Conservative estimate
            
        return gpu_percent, gpu_name

def get_system_info(self):
        """Get comprehensive system information"""
        try:
            # CPU info
            cpu_count = psutil.cpu_count(logical=False)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            freq_text = f"{cpu_freq.current:.0f}MHz" if cpu_freq else "Unknown"
            
            # Memory info
            mem = psutil.virtual_memory()
            mem_total = mem.total / (1024**3)
            mem_available = mem.available / (1024**3)
            
            # Boot time
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            uptime_hours = int(uptime // 3600)
            uptime_minutes = int((uptime % 3600) // 60)
            
            return (f"🔥 CPU: {cpu_count}C/{cpu_count_logical}T @ {freq_text} | "
                   f"💾 RAM: {mem_available:.1f}GB/{mem_total:.1f}GB Available | "
                   f"⏱️ Uptime: {uptime_hours}h {uptime_minutes}m |")
                   
        except Exception as e:
            return f"⚠️ System info error: {str(e)}"

def update_stats(self):
        """Update all system statistics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            
            # RAM usage  
            mem = psutil.virtual_memory()
            ram_percent = mem.percent
            
            # GPU usage with improved detection
            gpu_percent, gpu_info = self.get_gpu_usage()
            
            # Network usage calculation
            current_time = time.time()
            net_current = psutil.net_io_counters()
            time_diff = current_time - self.last_time
            
            total_bytes_per_sec = 0
            if time_diff > 0:
                bytes_sent_per_sec = (net_current.bytes_sent - self.last_net.bytes_sent) / time_diff
                bytes_recv_per_sec = (net_current.bytes_recv - self.last_net.bytes_recv) / time_diff
                total_bytes_per_sec = bytes_sent_per_sec + bytes_recv_per_sec
                
                # Convert to percentage (10MB/s = 100%)
                net_percent = min((total_bytes_per_sec / (10 * 1024 * 1024)) * 100, 100)
            else:
                net_percent = 0
                
            self.last_net = net_current
            self.last_time = current_time

            # Update main meters
            cpu_freq = psutil.cpu_freq()
            cpu_freq_text = f"{cpu_freq.current/1000:.2f} GHz" if cpu_freq else "N/A"
            
            self.cpu_meter.set_value(cpu_percent, cpu_freq_text)
            self.ram_meter.set_value(ram_percent, f"{mem.total/(1024**3):.1f} GB Total")
            self.gpu_meter.set_value(gpu_percent, gpu_info[:30] + "..." if len(gpu_info) > 30 else gpu_info)
            self.net_meter.set_value(net_percent, f"{total_bytes_per_sec/(1024*1024):.1f} MB/s")

            # Update mini widget
            if self.mini_widget.isVisible():
                self.mini_widget.update_status(cpu_percent, ram_percent, gpu_percent)

            # Update system info
            self.system_info.setText(self.get_system_info())

        except Exception as e:
            print(f" Error updating stats: {e}")

def closeEvent(self, event):
        """Handle application close"""
        self.mini_widget.close()
        if LHM_AVAILABLE and computer:
            try:
                computer.Close()
            except:
                pass
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("CJ Resource Monitor Pro")
    app.setApplicationVersion("2.1")
    
    try:
        window = MonitorWindow()
        window.show()
        
        print(" CJ Resource Monitor Pro started successfully!")
        print(f" LibreHardwareMonitor: {' Active' if LHM_AVAILABLE else ' Using Fallbacks'}")
        print("=" * 50)
        
        sys.exit(app.exec_())
        
    except Exception as e:
        print(f" Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()