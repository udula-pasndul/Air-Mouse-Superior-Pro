# 🖐️ Air Mouse Superior Pro

**Professional Hand Gesture Mouse Control — Headless, High‑Performance, Production‑Ready.**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey?style=for-the-badge)]()

Turn any webcam into a precise, low‑latency air mouse. Control your cursor with natural movements and a suite of intuitive gestures for clicks, scrolling, and zooming. Designed to run silently in the background with zero-window "headless" operation.

---

## ✨ Why Superior Pro?

* **Palm‑Center Tracking:** Uses the hand's center of mass for tracking rather than jittery fingertips, ensuring rock-solid cursor stability.
* **Advanced Filtering:** Integrated **1€**, **Kalman**, and **Adaptive filters** eliminate micro-jitters without introducing processing lag.
* **Non‑Linear Mapping:** Professional-grade velocity curves (Linear, Power, Exponential) for a natural, intuitive mouse feel.
* **Zero-UI "Headless" Mode:** Runs entirely in the system tray. No distracting camera feed windows cluttering your workspace.
* **Auto-Calibration:** Dynamically measures hand-to-camera distance to scale gesture sensitivity to your specific environment.
* **Hot-Reloading:** Modify `air_mouse_pro_config.json` and see changes applied instantly without restarting the application.

---

## 🛠️ Technical Architecture

| Component | Technology |
| :--- | :--- |
| **Vision Engine** | MediaPipe Hand Landmarker |
| **Processing** | OpenCV & NumPy |
| **Smoothing** | One-Euro Filter / Kalman Filter |
| **I/O Control** | Win32API (Win), Quartz (macOS), Evdev (Linux) |
| **Extensibility** | REST API & Python Plugin System |

---

## 📦 Installation

### 1. Clone & Enter
```bash
git clone [https://github.com/yourusername/air-mouse-superior-pro.git](https://github.com/yourusername/air-mouse-superior-pro.git)
cd air-mouse-superior-pro

2. Install Core Dependencies
pip install -r requirements.txt

3. Launch
python air_mouse_superior_pro_v5.py
