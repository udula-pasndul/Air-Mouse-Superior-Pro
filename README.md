🖐️ Air Mouse Superior Pro
Professional Hand Gesture Mouse Control – Headless, High‑Performance, and Production‑Ready

https://img.shields.io/badge/Python-3.8%252B-blue
https://img.shields.io/badge/License-MIT-green
https://img.shields.io/badge/Platform-Windows%2520%257C%2520macOS%2520%257C%2520Linux-lightgrey

Transform your webcam into a precise, low‑latency air mouse. Control your cursor with natural hand movements using state‑of‑the‑art filtering, multi‑gesture recognition, and adaptive calibration. Designed for daily professional use—no windows, no bloat, just smooth, reliable hand tracking.

✨ Features
🎯 Palm‑Center Tracking – Dramatically reduces jitter compared to fingertip tracking

📈 Advanced Filters – 1€ filter, Kalman filter, and adaptive smoothing for buttery‑smooth cursor motion

⚡ Non‑Linear Velocity Mapping – Fine control for small movements, rapid flicks for large jumps

🤌 Rich Gesture Set

✊✊ Double fist → Left click

✌️ Peace sign → Right click

☝️☝️ Two‑finger spread → Scroll

🤙 Wrist roll → Continuous scroll

🤏 Pinch → Toggle drag lock

👋 Open palm → Freeze cursor (precision mode)

☝️✌️✌️ Three‑finger swipe → Switch virtual desktop

↔️ Thumb‑index spread → Zoom (Ctrl+wheel)

⭕ Draw a circle → Screenshot

🧠 Adaptive Learning – Thresholds auto‑tune to your hand over time

📷 Headless Operation – No distracting camera windows; runs quietly in the system tray

🔌 Cross‑Platform Backends – Windows (win32api), macOS (Quartz), Linux (evdev/pyautogui)

⚙️ Hot‑Reload Config – Edit JSON settings while the app is running

🔌 Plugin Architecture – Extend functionality with custom plugins

📊 Telemetry – Optional CSV/SQLite logging of all gesture events

🌐 REST API – Control the mouse remotely (optional)

🚀 Quick Start
bash
# Clone the repository
git clone https://github.com/yourusername/air-mouse-superior-pro.git
cd air-mouse-superior-pro

# Install dependencies
pip install -r requirements.txt

# Run the air mouse
python air_mouse_superior_pro_v5.py
On first run, the app auto‑calibrates and creates a air_mouse_pro_config.json file you can tweak to your liking.

📸 Screenshots
[Optional: Add a GIF or image showing hand gestures and cursor movement]

🛠️ Configuration
All behavior is controlled via a single JSON file. Adjust cursor speed, gesture thresholds, filter parameters, and more without touching the code.

📦 Requirements
Python 3.8+

Webcam (built‑in or USB)

Dependencies: mediapipe, opencv-python, numpy, pyautogui (and pywin32 on Windows)

See requirements.txt for the full list.

🤝 Contributing
Pull requests are welcome! If you've written a plugin or improved a gesture recognizer, feel free to open a PR.

📄 License
MIT – see LICENSE for details.
