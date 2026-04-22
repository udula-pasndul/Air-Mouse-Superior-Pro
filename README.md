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
