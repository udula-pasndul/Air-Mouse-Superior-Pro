# 🖐️ Air Mouse Superior Pro

**Professional Hand Gesture Mouse Control – Headless, High‑Performance, Production‑Ready**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

Transform any standard webcam into a precise, low‑latency air mouse. Control your cursor with natural hand movements, perform gestures for clicks, scrolling, zooming, and more – all without ever touching a physical mouse. Built for reliability and daily professional use.

![Air Mouse Demo](docs/demo.gif) <!-- Replace with actual demo link -->

## ✨ Key Features

- **🎯 Palm‑Center Tracking** – Cursor is driven by the stable center of your palm, eliminating the jitter common with fingertip tracking.
- **📈 Advanced Signal Filtering** – Choose between 1€ filter, Kalman filter, or adaptive smoothing for buttery‑smooth motion without lag.
- **⚡ Intuitive Velocity Mapping** – Non‑linear curves (linear, power, exponential) give you fine control for small movements and quick flicks for large jumps.
- **🤌 Rich Gesture Set**
  | Gesture | Action |
  |---|---|
  | ✊✊ Double fist | Left click |
  | ✌️ Peace sign | Right click |
  | ☝️☝️ Two‑finger spread | Vertical scroll |
  | 🤙 Wrist roll | Continuous scroll |
  | 🤏 Thumb‑index pinch | Toggle drag lock |
  | 👋 Open flat palm | Freeze cursor (precision anchor) |
  | ☝️✌️✌️ Three‑finger swipe | Switch virtual desktop |
  | ↔️ Thumb‑index spread | Zoom (Ctrl+wheel) |
  | ⭕ Draw a circle in the air | Take a screenshot |
- **🧠 Adaptive Learning** – Thresholds automatically adjust to your hand size and gesture style over time.
- **👻 Headless & Tray‑Based** – Runs silently in the system tray; no distracting camera windows.
- **🔌 Cross‑Platform Mouse Backends** – Windows (win32api low‑latency), macOS (Quartz), Linux (evdev/pyautogui).
- **⚙️ Hot‑Reload Configuration** – Edit the JSON config file while the app is running; changes apply instantly.
- **🔌 Plugin System** – Extend functionality by dropping Python plugins into the `plugins/` folder.
- **📊 Telemetry** – Optional logging of gesture events to CSV or SQLite for analysis.
- **🌐 REST API** – Optional HTTP server for remote control and monitoring.

## 📦 Installation

### Prerequisites

- Python 3.8 or newer
- A webcam (built‑in or USB)
- **Windows users:** [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) (required for MediaPipe)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/air-mouse-superior-pro.git
cd air-mouse-superior-pro
2. Install Dependencies
bash
pip install -r requirements.txt
Optional extras:

System tray icon: pip install pystray Pillow

REST API: pip install flask

Multi‑monitor info: pip install screeninfo

Linux native mouse: pip install evdev

3. Download the Hand Landmark Model
The first run will automatically download the MediaPipe hand landmark model (~10 MB). Ensure you have an internet connection.

🚀 Usage
Run the main script:

bash
python air_mouse_superior_pro_v5.py
Command‑Line Options
Argument	Description
--config PATH	Use a custom config file (default: air_mouse_pro_config.json)
--calibrate	Force calibration on startup
--list-monitors	Print all connected displays and exit
--reset-config	Overwrite config with factory defaults and exit
--log-level {DEBUG,INFO,WARNING,ERROR}	Override log level from config
--no-tray	Disable system tray icon
--api	Enable REST API server
--version	Show version and exit
First‑Run Calibration
The application automatically runs a 3‑second calibration when first started. Hold your hand open and steady in front of the camera. The system measures your hand size and adjusts gesture thresholds accordingly.

⚙️ Configuration
All settings are stored in air_mouse_pro_config.json. The file is created on first run with sensible defaults. You can edit it at any time – the app will hot‑reload changes automatically (if enabled).

Key sections you may want to tweak:

json
{
  "cursor": {
    "velocity_gain": 2.3,          // Overall cursor speed
    "smoothing_factor": 0.45,      // Higher = smoother but more lag
    "dead_zone": 2.0,              // Ignore tiny movements
    "velocity_mapping": "power"    // "linear", "power", "exponential"
  },
  "gestures": {
    "left_click": { "fist_threshold": 0.58 },
    "drag_lock": { "pinch_threshold": 42 }
  }
}
See the Configuration Guide for a full breakdown. <!-- optional -->

🤌 Gesture Reference
Gesture	How to Perform	Default Action
Double Fist	Close your hand into a fist twice quickly	Left click
Peace Sign	Extend index and middle fingers, curl others	Right click
Two‑Finger Scroll	Spread index and middle fingers, move hand vertically	Scroll
Wrist Roll Scroll	Tilt your hand left/right with fingers extended	Continuous scroll
Pinch	Bring thumb and index fingertip together	Toggle drag lock
Open Palm	Fully extend all fingers, palm facing camera	Freeze cursor
Three‑Finger Swipe	Extend index, middle, ring fingers and swipe horizontally	Switch desktop
Thumb‑Index Spread	Move thumb and index finger apart/together	Zoom in/out
Circle Gesture	Draw a circle in the air with your index finger	Screenshot
🐛 Troubleshooting
Cursor jumps or is jittery
Ensure the room is well‑lit and your hand contrasts with the background.

Try switching tracking_point to "palm_center" (default) if you're using "index_tip".

Increase dead_zone or smoothing_factor in the config.

Gestures not triggering
Run with --log-level DEBUG to see gesture detection values.

Re‑calibrate by clicking "Calibrate" in the tray menu or running with --calibrate.

Adjust threshold values in the config (lower values make gestures easier to trigger).

Camera not found
Verify device_id in the config (0 is usually the built‑in webcam).

Ensure no other application is using the camera.

High CPU usage
Reduce target_fps or frame_width/frame_height in the camera section.

Increase frame_skip (e.g., 2 to process every 2nd frame).

Windows: ImportError: No module named win32api
Install the missing dependency:

bash
pip install pywin32
🔌 Plugins
You can extend Air Mouse Superior Pro by placing Python files in the plugins/ directory. A plugin must subclass PluginBase and implement the desired hooks.

Example plugin that prints gestures:

python
from air_mouse_superior_pro_v5 import PluginBase

class PrintPlugin(PluginBase):
    name = "Gesture Printer"
    version = "1.0"

    def on_gesture(self, gesture, data):
        print(f"Gesture detected: {gesture} -> {data}")
🌐 REST API
Enable the API by setting "enable": true in the api section of the config. The server runs on http://127.0.0.1:5765.

Endpoint	Method	Description
/status	GET	Return current status (running, paused, fps, drag state)
/pause	POST	Toggle pause/resume
/calibrate	POST	Start calibration
/screenshot	GET	Take a screenshot
Example:

bash
curl -X POST http://127.0.0.1:5765/pause
🤝 Contributing
Contributions are welcome! Feel free to open issues for bugs or feature requests, and submit pull requests with improvements.

Please ensure your code adheres to the existing style and includes appropriate docstrings.

📄 License
This project is licensed under the MIT License – see the LICENSE file for details.

Air Mouse Superior Pro – Control your computer like a maestro, with just a wave of your hand.

text

You can save this as `README.md` in your repository root. Adjust the GitHub username and demo GIF link as needed.
