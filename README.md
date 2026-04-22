# 🖐️ Air Mouse Superior Pro

**Professional Hand Gesture Mouse Control – Headless, High‑Performance, Production‑Ready**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

Turn any webcam into a precise, low‑latency air mouse. Control your cursor with natural hand movements and perform gestures for clicks, scrolling, zooming, and more. Runs silently in the system tray with zero camera windows.

---

## ✨ What Makes It Different

- **Palm‑center tracking** (not jittery fingertip) for stable cursor control.
- **1€ / Kalman / Adaptive filters** – smooth motion without lag.
- **Non‑linear velocity mapping** (linear, power, exponential) – intuitive speed response.
- **11+ gesture recognizers** with debouncing and adaptive thresholds.
- **Automatic hand‑size calibration** – adjusts to your hand on first run.
- **Hot‑reload configuration** – edit the JSON file while the app runs.
- **Headless operation** – optional system tray icon for quick control.
- **Cross‑platform mouse backends** – Windows (win32api), macOS (Quartz), Linux (pyautogui/evdev).
- **Optional REST API, telemetry (CSV/SQLite), and plugin system.**

---

## 📦 Installation

### 1. Clone the repository
git clone https://github.com/yourusername/air-mouse-superior-pro.git
cd air-mouse-superior-pro

### 2. Install dependencies
pip install -r requirements.txt

### 3.just run
python air_mouse_superior_pro_v5.py

Command‑line arguments
Argument	Description
--config PATH	Use a custom config file (default: air_mouse_pro_config.json)
--calibrate	Force calibration on startup
--list-monitors	Print all connected displays and exit
--reset-config	Overwrite config with factory defaults and exit
--log-level {DEBUG,INFO,WARNING,ERROR}	Override log level
--no-tray	Disable system tray icon
--api	Enable REST API server
--version	Show version and exit

First‑run calibration
On first run, the app automatically runs a 3‑second calibration. Hold your hand open and steady in front of the camera. The system measures your hand size and scales gesture thresholds accordingly.

🔧 Troubleshooting
Cursor is jittery or too sensitive
Increase dead_zone and smoothing_factor in the config.

Ensure the room is well‑lit and your hand contrasts with the background.

Try "filter_type": "kalman" for heavier smoothing.

Gestures not triggering consistently
Run with --log-level DEBUG to see detection values in the console.

Re‑calibrate (tray icon → Calibrate, or --calibrate).

Lower the relevant threshold in the config (e.g., fist_threshold).

High CPU usage
Reduce target_fps or frame_width/frame_height.

Increase frame_skip (process every Nth frame).

Camera not found
Check device_id in the config (0 = default webcam).

Ensure no other app is using the camera.

Windows: ImportError: No module named win32api
bash
pip install pywin32
```bash

bash
pip install -r requirements.txt
