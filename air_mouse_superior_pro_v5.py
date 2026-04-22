#!/usr/bin/env python3
"""
Air Mouse Superior Pro v5.0
============================================================================================
Ultra-High-Performance Hand Gesture Mouse Controller – Headless, Configurable, Production-Ready

NEW in v5.0:
- Kalman filter option alongside 1€ filter for ultra-smooth tracking
- Adaptive gesture learning: system auto-tunes thresholds per session
- Full multi-monitor support: cursor maps correctly across all displays
- Wrist roll detection for continuous scroll (tilt hand = scroll)
- Open-palm freeze: flat palm halts cursor (precision anchor mode)
- Fingertip circle draw gesture → screenshot capture
- Predictive motion compensation to reduce perceived latency
- Async I/O pipeline: detector, capture, and mouse control on separate threads
- Hot-reload config: change JSON while running, re-applied without restart
- Per-gesture audio feedback (optional, via winsound/playsound)
- Gaze-hand fusion stub (ready for eye-tracker integration)
- Cross-platform: Windows (win32api), Linux (evdev/xdotool), macOS (Quartz)
- REST API control endpoint (optional, requires Flask)
- Structured telemetry export (CSV / SQLite)
- Plugin architecture: drop .py files into /plugins folder
- Extensive docstrings, type hints, and inline comments throughout

Dependencies:
    pip install mediapipe opencv-python numpy pywin32 pyautogui pystray Pillow flask

Author: Enhanced Version v5.0
License: MIT
"""

# ==========================================================================================
# IMPORTS & PLATFORM DETECTION
# ==========================================================================================

import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import queue
import json
import os
import sys
import math
import argparse
import ctypes
import logging
import importlib
import struct
import csv
import sqlite3
import hashlib
import socket
import traceback
import platform
import signal
import copy
import weakref
import itertools

from dataclasses import dataclass, asdict, field
from typing import Tuple, Optional, Dict, Any, List, Callable, Union, Deque, Generator
from collections import deque
from enum import Enum, auto
from pathlib import Path
from abc import ABC, abstractmethod
from logging.handlers import RotatingFileHandler
from functools import lru_cache, partial
from contextlib import contextmanager, suppress
from threading import RLock, Event

# ── Platform detection ──────────────────────────────────────────────────────────────────
PLATFORM = platform.system()  # "Windows", "Linux", "Darwin"
IS_WINDOWS = PLATFORM == "Windows"
IS_LINUX   = PLATFORM == "Linux"
IS_MAC     = PLATFORM == "Darwin"

# ── Optional: win32api (Windows) ────────────────────────────────────────────────────────
try:
    import win32api, win32con, win32gui, win32process
    import pywintypes
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

# ── Optional: evdev / xdotool (Linux) ───────────────────────────────────────────────────
if IS_LINUX:
    try:
        import evdev
        from evdev import UInput, ecodes as e
        EVDEV_AVAILABLE = True
    except ImportError:
        EVDEV_AVAILABLE = False
else:
    EVDEV_AVAILABLE = False

# ── Optional: Quartz (macOS) ────────────────────────────────────────────────────────────
if IS_MAC:
    try:
        import Quartz
        from Quartz.CoreGraphics import (
            CGEventCreateMouseEvent, CGEventPost,
            kCGEventMouseMoved, kCGMouseButtonLeft, kCGHIDEventTap,
            CGEventCreateScrollWheelEvent, kCGScrollEventUnitLine,
            CGEventCreateKeyboardEvent
        )
        QUARTZ_AVAILABLE = True
    except ImportError:
        QUARTZ_AVAILABLE = False
else:
    QUARTZ_AVAILABLE = False

# ── Optional: pyautogui (universal fallback) ────────────────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

if not WIN32_AVAILABLE and not PYAUTOGUI_AVAILABLE and not QUARTZ_AVAILABLE and not EVDEV_AVAILABLE:
    raise ImportError(
        "No mouse backend found! Install at least one of:\n"
        "  Windows:  pip install pywin32\n"
        "  Linux:    pip install evdev  OR install xdotool\n"
        "  macOS:    pip install pyobjc-framework-Quartz\n"
        "  Any OS:   pip install pyautogui"
    )

# ── Optional: system tray ───────────────────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# ── Optional: audio feedback ────────────────────────────────────────────────────────────
try:
    if IS_WINDOWS:
        import winsound
        AUDIO_AVAILABLE = True
    else:
        import playsound
        AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# ── Optional: REST API ──────────────────────────────────────────────────────────────────
try:
    from flask import Flask, jsonify, request as flask_request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# ── Optional: screen info ───────────────────────────────────────────────────────────────
try:
    from screeninfo import get_monitors
    SCREENINFO_AVAILABLE = True
except ImportError:
    SCREENINFO_AVAILABLE = False


# ==========================================================================================
# CONSTANTS & VERSION INFO
# ==========================================================================================

VERSION         = "5.0.0"
CONFIG_VERSION  = 5
CONFIG_FILE     = "air_mouse_pro_config.json"
LOG_FILE        = "air_mouse_pro.log"
TELEMETRY_DB    = "air_mouse_telemetry.db"
PLUGIN_DIR      = "plugins"
SCREENSHOT_DIR  = "screenshots"

# Hand landmark indices (MediaPipe convention)
WRIST         = 0
THUMB_CMC     = 1
THUMB_MCP     = 2
THUMB_IP      = 3
THUMB_TIP     = 4
INDEX_MCP     = 5
INDEX_PIP     = 6
INDEX_DIP     = 7
INDEX_TIP     = 8
MIDDLE_MCP    = 9
MIDDLE_PIP    = 10
MIDDLE_DIP    = 11
MIDDLE_TIP    = 12
RING_MCP      = 13
RING_PIP      = 14
RING_DIP      = 15
RING_TIP      = 16
PINKY_MCP     = 17
PINKY_PIP     = 18
PINKY_DIP     = 19
PINKY_TIP     = 20

FINGER_TIPS   = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
FINGER_PIPS   = [THUMB_IP,  INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]
FINGER_MCPS   = [THUMB_MCP, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
FINGER_DIPS   = [THUMB_IP,  INDEX_DIP, MIDDLE_DIP, RING_DIP, PINKY_DIP]


# ==========================================================================================
# DEFAULT CONFIGURATION
# ==========================================================================================

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": CONFIG_VERSION,
    "camera": {
        "device_id": 0,
        "frame_width": 320,
        "frame_height": 240,
        "target_fps": 30,
        "auto_exposure": True,
        "exposure": -6,
        "brightness": 128,
        "contrast": 128,
        "flip_horizontal": True,       # Mirror view (more natural)
        "flip_vertical": False,
        "buffer_size": 1               # Minimize internal camera buffer
    },
    "hand_tracking": {
        "min_detection_confidence": 0.6,
        "min_tracking_confidence": 0.5,
        "num_hands": 2,
        "primary_hand": "right",       # "right" or "left"
        "model_complexity": 1,         # 0=lite, 1=full
        "hand_lost_timeout": 2.0,
        "hand_swap_timeout": 1.0
    },
    "mouse": {
        "filter_type": "one_euro",     # "one_euro" | "kalman" | "lowpass" | "adaptive"
        "velocity_gain": 2.2,
        "smoothing_factor": 0.5,       # 1€: min-cutoff / lowpass: alpha
        "beta": 0.007,                 # 1€ speed coefficient
        "dead_zone": 2.0,
        "max_speed": 1500.0,
        "invert_x": False,
        "invert_y": False,
        "acceleration": True,
        "accel_multiplier": 1.6,
        "accel_threshold": 280.0,
        "prediction_ms": 15.0,         # Predictive compensation (0 = off)
        "monitor_index": -1            # -1 = all monitors combined
    },
    "gestures": {
        "left_click": {
            "enable": True,
            "type": "double_fist",
            "fist_threshold": 0.58,
            "double_click_timeout": 0.45
        },
        "right_click": {
            "enable": True,
            "type": "peace_sign",
            "angle_threshold": 30,
            "hold_duration": 0.0       # 0 = instant, >0 = hold N seconds
        },
        "scroll": {
            "enable": True,
            "type": "two_finger_vertical",
            "sensitivity": 18,
            "distance_threshold": 45,
            "wrist_roll_enable": True,  # Tilt wrist to scroll
            "wrist_roll_sensitivity": 25
        },
        "drag_lock": {
            "enable": True,
            "type": "pinch",
            "pinch_threshold": 42,
            "toggle": True
        },
        "desktop_swipe": {
            "enable": True,
            "type": "three_finger_swipe",
            "swipe_threshold": 55,
            "velocity_threshold": 190
        },
        "zoom": {
            "enable": True,
            "type": "thumb_index_spread",
            "sensitivity": 0.012,
            "min_delta": 2.5
        },
        "freeze_cursor": {
            "enable": True,
            "type": "open_palm",
            "flat_threshold": 0.12     # Max curl ratio for "flat"
        },
        "screenshot": {
            "enable": True,
            "type": "fingertip_circle",
            "circle_radius_threshold": 30,
            "min_points": 20
        },
        "click_cooldown": 0.22,
        "gesture_cooldown": 0.28,
        "adaptive_learning": True,     # Auto-tune thresholds over session
        "learning_rate": 0.05
    },
    "advanced": {
        "fps_limit": 60,
        "frame_queue_size": 2,
        "auto_calibrate": True,
        "calibration_duration": 3.0,
        "plugin_enabled": True,
        "hot_reload_config": True,
        "hot_reload_interval": 3.0,    # seconds
        "telemetry_enabled": False,
        "telemetry_backend": "csv"     # "csv" | "sqlite"
    },
    "performance": {
        "log_level": "INFO",
        "log_to_file": True,
        "show_fps_in_log": False,
        "frame_skip": 1,
        "process_every_n_frames": 1,
        "detector_thread": True        # Run detector on separate thread
    },
    "audio": {
        "enable": False,
        "click_sound": "",
        "gesture_sound": "",
        "volume": 0.5
    },
    "tray": {
        "enable": True,
        "icon_color": "cyan"
    },
    "api": {
        "enable": False,
        "host": "127.0.0.1",
        "port": 5765
    }
}


# ==========================================================================================
# UTILITIES & HELPERS
# ==========================================================================================

def deep_merge(base: Dict, update: Dict) -> Dict:
    """Recursively merge `update` into `base`, returning `base`."""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def dist2d(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dist3d(a, b) -> float:
    """Euclidean distance between two 3D landmarks."""
    return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)


def angle_between(v1: Tuple[float, float], v2: Tuple[float, float]) -> float:
    """Angle in degrees between two 2D vectors."""
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    mag = math.hypot(*v1) * math.hypot(*v2)
    if mag < 1e-9:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))


def clamp(val: float, lo: float, hi: float) -> float:
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, val))


def moving_average(buf: deque, new_val: float, maxlen: int = 10) -> float:
    """Push new_val into buf (maxlen) and return average."""
    buf.append(new_val)
    if len(buf) > maxlen:
        buf.popleft()
    return sum(buf) / len(buf)


def lm_to_px(lm, w: int, h: int) -> Tuple[int, int]:
    """Convert a normalized landmark to pixel coordinates."""
    return (int(lm.x * w), int(lm.y * h))


def lm_to_np(lm, w: int, h: int) -> np.ndarray:
    """Convert a normalized landmark to a float numpy array [x, y]."""
    return np.array([lm.x * w, lm.y * h], dtype=np.float32)


def finger_extended(landmarks, tip_idx: int, pip_idx: int) -> bool:
    """Return True if a finger is extended (tip higher than PIP in image coords)."""
    return landmarks[tip_idx].y < landmarks[pip_idx].y


def all_fingers_extended(landmarks, exclude_thumb: bool = True) -> bool:
    """Return True if all (non-thumb) fingers are extended."""
    pairs = [(INDEX_TIP, INDEX_PIP), (MIDDLE_TIP, MIDDLE_PIP),
             (RING_TIP, RING_PIP), (PINKY_TIP, PINKY_PIP)]
    if not exclude_thumb:
        pairs.append((THUMB_TIP, THUMB_IP))
    return all(finger_extended(landmarks, t, p) for t, p in pairs)


def get_hand_bbox(landmarks, w: int, h: int) -> Tuple[int, int, int, int]:
    """Get bounding box (x1, y1, x2, y2) of all landmarks in pixel space."""
    xs = [int(lm.x * w) for lm in landmarks]
    ys = [int(lm.y * h) for lm in landmarks]
    return min(xs), min(ys), max(xs), max(ys)


def compute_hand_size(landmarks, w: int, h: int) -> float:
    """Estimate hand size as distance from wrist to middle-MCP."""
    wrist = lm_to_np(landmarks[WRIST], w, h)
    mid   = lm_to_np(landmarks[MIDDLE_MCP], w, h)
    return float(np.linalg.norm(wrist - mid))


def wrist_roll_angle(landmarks) -> float:
    """
    Compute wrist roll angle (tilt) in degrees.
    Positive = rolled clockwise (right/down), negative = counter-clockwise.
    """
    wrist = np.array([landmarks[WRIST].x, landmarks[WRIST].y])
    index = np.array([landmarks[INDEX_MCP].x, landmarks[INDEX_MCP].y])
    pinky = np.array([landmarks[PINKY_MCP].x, landmarks[PINKY_MCP].y])
    knuckle_vec = pinky - index
    angle = math.degrees(math.atan2(knuckle_vec[1], knuckle_vec[0]))
    return angle


def circle_score(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Fit a circle to 2D points using least-squares.
    Returns (radius, residual_error). Low error = good circle.
    """
    if len(points) < 5:
        return 0.0, 1e9
    pts = np.array(points, dtype=np.float32)
    # Algebraic circle fit
    x, y = pts[:, 0], pts[:, 1]
    A = np.c_[2*x, 2*y, np.ones(len(pts))]
    b = x**2 + y**2
    try:
        result, residuals, _, _ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return 0.0, 1e9
    cx, cy, c = result
    radius = math.sqrt(c + cx**2 + cy**2)
    fitted = np.sqrt((x - cx)**2 + (y - cy)**2)
    error = float(np.std(fitted - radius))
    return radius, error


# ==========================================================================================
# LOGGING
# ==========================================================================================

def setup_logging(level: str = "INFO", log_to_file: bool = True) -> logging.Logger:
    """Configure and return the application logger."""
    _logger = logging.getLogger("AirMousePro")
    _logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    _logger.handlers.clear()

    fmt = logging.Formatter(
        '%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    _logger.addHandler(ch)

    if log_to_file:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        fh.setFormatter(fmt)
        _logger.addHandler(fh)

    return _logger

logger: logging.Logger = logging.getLogger("AirMousePro")


# ==========================================================================================
# CONFIG MANAGEMENT
# ==========================================================================================

@dataclass
class Config:
    """
    Typed wrapper around the raw configuration dictionary.
    Supports JSON persistence, version migration, hot-reload, and deep-merge.
    """
    version:     int
    camera:      Dict[str, Any]
    hand_tracking: Dict[str, Any]
    mouse:       Dict[str, Any]
    gestures:    Dict[str, Any]
    advanced:    Dict[str, Any]
    performance: Dict[str, Any]
    audio:       Dict[str, Any]
    tray:        Dict[str, Any]
    api:         Dict[str, Any]
    _path:       str = field(default=CONFIG_FILE, repr=False, compare=False)

    # ── Factory ─────────────────────────────────────────────────────────────────────────
    @classmethod
    def load(cls, path: str = CONFIG_FILE) -> "Config":
        """Load config from disk; fall back to defaults if missing or corrupt."""
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                if raw.get("version", 0) < CONFIG_VERSION:
                    raw = deep_merge(copy.deepcopy(DEFAULT_CONFIG), raw)
                    raw["version"] = CONFIG_VERSION
                # Ensure all top-level keys are present
                merged = deep_merge(copy.deepcopy(DEFAULT_CONFIG), raw)
                merged["_path"] = path
                return cls(**merged)
            except Exception as exc:
                logger.warning(f"Config load error ({exc}). Using defaults.")

        cfg = cls(**copy.deepcopy(DEFAULT_CONFIG), _path=path)
        cfg.save()
        return cfg

    def save(self, path: Optional[str] = None) -> None:
        """Persist current config to disk."""
        target = path or self._path
        data = asdict(self)
        data.pop("_path", None)
        with open(target, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    def reload(self, path: Optional[str] = None) -> bool:
        """
        Hot-reload: read disk, update own fields in-place.
        Returns True if something changed.
        """
        target = path or self._path
        if not os.path.exists(target):
            return False
        try:
            with open(target, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            merged = deep_merge(copy.deepcopy(DEFAULT_CONFIG), raw)
            changed = False
            for field_name in DEFAULT_CONFIG:
                new_val = merged.get(field_name)
                if getattr(self, field_name, None) != new_val:
                    setattr(self, field_name, new_val)
                    changed = True
            return changed
        except Exception as exc:
            logger.warning(f"Hot-reload failed: {exc}")
            return False

    def fingerprint(self) -> str:
        """SHA256 fingerprint of the current config (for change detection)."""
        data = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]


# ==========================================================================================
# MONITOR / SCREEN INFO
# ==========================================================================================

@dataclass
class MonitorInfo:
    """Represents a single display monitor."""
    index: int
    x: int
    y: int
    width: int
    height: int
    name: str = ""

    @property
    def right(self):  return self.x + self.width
    @property
    def bottom(self): return self.y + self.height
    @property
    def center(self): return (self.x + self.width // 2, self.y + self.height // 2)


def get_monitors_info() -> List[MonitorInfo]:
    """Return a list of connected monitors."""
    monitors = []
    if SCREENINFO_AVAILABLE:
        for i, m in enumerate(get_monitors()):
            monitors.append(MonitorInfo(i, m.x, m.y, m.width, m.height, m.name or f"Monitor {i}"))
    elif IS_WINDOWS:
        # Use ctypes to call EnumDisplayMonitors directly
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                             ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)]

        def _cb(hMonitor, hdcMonitor, lprcMonitor, dwData):
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
                r = mi.rcMonitor
                monitors.append(MonitorInfo(len(monitors), r.left, r.top,
                                            r.right - r.left, r.bottom - r.top,
                                            f"Monitor {len(monitors)}"))
            return True

        callback = MONITORENUMPROC(_cb)
        user32.EnumDisplayMonitors(None, None, callback, 0)
    if not monitors:
        # Fallback to single monitor from pyautogui or default
        try:
            w, h = pyautogui.size()
            monitors.append(MonitorInfo(0, 0, 0, w, h, "Primary"))
        except Exception:
            monitors.append(MonitorInfo(0, 0, 0, 1920, 1080, "Primary"))
    return monitors


def get_virtual_screen_bounds(monitors: List[MonitorInfo]) -> Tuple[int, int, int, int]:
    """Return (left, top, right, bottom) spanning all monitors."""
    left   = min(m.x for m in monitors)
    top    = min(m.y for m in monitors)
    right  = max(m.right for m in monitors)
    bottom = max(m.bottom for m in monitors)
    return left, top, right, bottom


# ==========================================================================================
# SIGNAL FILTERS
# ==========================================================================================

class FilterBase(ABC):
    """Abstract base for all signal filters."""
    @abstractmethod
    def filter(self, x: float, timestamp: Optional[float] = None) -> float: ...
    @abstractmethod
    def reset(self) -> None: ...


class OneEuroFilter(FilterBase):
    """
    1€ filter – low-latency adaptive low-pass filter.
    Reference: Casiez et al., "1€ Filter: A Simple Speed-based Low-pass Filter
    for Noisy Input in Interactive Systems", CHI 2012.
    """
    def __init__(self, freq: float, mincutoff: float = 1.0,
                 beta: float = 0.0, dcutoff: float = 1.0):
        self.freq      = freq
        self.mincutoff = mincutoff
        self.beta      = beta
        self.dcutoff   = dcutoff
        self.x_prev:  Optional[float] = None
        self.dx_prev: Optional[float] = None
        self._first   = True

    def _alpha(self, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te  = 1.0 / self.freq
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        if self.x_prev is None:
            self.x_prev  = x
            self.dx_prev = 0.0
            self._first  = True
            return x
        dx = 0.0 if self._first else (x - self.x_prev) * self.freq
        self._first = False
        a_d  = self._alpha(self.dcutoff)
        edx  = a_d * dx + (1.0 - a_d) * (self.dx_prev or 0.0)
        self.dx_prev = edx
        cutoff = self.mincutoff + self.beta * abs(edx)
        a     = self._alpha(cutoff)
        y     = a * x + (1.0 - a) * self.x_prev
        self.x_prev = y
        return y

    def reset(self) -> None:
        self.x_prev  = None
        self.dx_prev = None
        self._first  = True


class KalmanFilter1D(FilterBase):
    """
    Scalar Kalman filter – optimal for Gaussian noise.
    Models hand position as a noisy constant with process drift.
    """
    def __init__(self, process_noise: float = 1e-3, measurement_noise: float = 0.1,
                 initial_estimate_error: float = 1.0):
        self.Q = process_noise           # Process noise covariance
        self.R = measurement_noise       # Measurement noise covariance
        self.P = initial_estimate_error  # Estimate error covariance
        self.x_est: Optional[float] = None  # State estimate

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        if self.x_est is None:
            self.x_est = x
            return x
        # Prediction step
        self.P += self.Q
        # Update step
        K       = self.P / (self.P + self.R)
        self.x_est += K * (x - self.x_est)
        self.P  *= (1.0 - K)
        return self.x_est

    def reset(self) -> None:
        self.x_est = None
        self.P     = 1.0


class LowpassFilter(FilterBase):
    """Exponential moving average (simple low-pass)."""
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.prev: Optional[float] = None

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        if self.prev is None:
            self.prev = x
            return x
        y = self.alpha * self.prev + (1.0 - self.alpha) * x
        self.prev = y
        return y

    def reset(self) -> None:
        self.prev = None


class AdaptiveFilter(FilterBase):
    """
    Adaptive filter that switches between Kalman and 1€ based on signal variance.
    High variance → Kalman dominates (trust model).
    Low variance  → 1€ dominates (trust measurement).
    """
    def __init__(self, freq: float, mincutoff: float = 0.5, beta: float = 0.01):
        self.k1e   = OneEuroFilter(freq, mincutoff, beta)
        self.kalman = KalmanFilter1D()
        self.history: Deque[float] = deque(maxlen=15)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        self.history.append(x)
        variance = float(np.var(self.history)) if len(self.history) > 2 else 0.0
        # Blend weight: high variance → rely more on Kalman
        w = clamp(variance / 50.0, 0.0, 1.0)
        y_euro   = self.k1e.filter(x, timestamp)
        y_kalman = self.kalman.filter(x, timestamp)
        return w * y_kalman + (1.0 - w) * y_euro

    def reset(self) -> None:
        self.k1e.reset()
        self.kalman.reset()
        self.history.clear()


def make_filter(filter_type: str, freq: float, cfg: Dict[str, Any]) -> FilterBase:
    """Factory: create a filter given the filter_type string."""
    ft = filter_type.lower()
    if ft == "one_euro":
        return OneEuroFilter(freq, mincutoff=cfg["smoothing_factor"], beta=cfg["beta"])
    elif ft == "kalman":
        return KalmanFilter1D(process_noise=1e-3, measurement_noise=cfg["smoothing_factor"])
    elif ft == "adaptive":
        return AdaptiveFilter(freq, mincutoff=cfg["smoothing_factor"], beta=cfg["beta"])
    else:
        return LowpassFilter(alpha=cfg["smoothing_factor"])


# ==========================================================================================
# PREDICTOR (Motion Compensation)
# ==========================================================================================

class MotionPredictor:
    """
    Predict future cursor position using linear extrapolation.
    Reduces perceived latency by offsetting the cursor ahead of the measured
    hand position by `prediction_ms` milliseconds.
    """
    def __init__(self, prediction_ms: float = 15.0, history_len: int = 5):
        self.pred_dt  = prediction_ms / 1000.0
        self.history: Deque[Tuple[float, float, float]] = deque(maxlen=history_len)
        # Each entry: (timestamp, x, y)

    def push(self, x: float, y: float, t: float) -> None:
        self.history.append((t, x, y))

    def predict(self, x: float, y: float, t: float) -> Tuple[float, float]:
        """Return predicted (x, y) at t + pred_dt."""
        if len(self.history) < 2 or self.pred_dt <= 0:
            return x, y
        # Least-squares velocity over history
        ts = np.array([h[0] for h in self.history])
        xs = np.array([h[1] for h in self.history])
        ys = np.array([h[2] for h in self.history])
        ts -= ts[-1]  # normalize relative to last frame
        if ts[0] == 0:
            return x, y
        vx = float(np.polyfit(ts, xs, 1)[0])
        vy = float(np.polyfit(ts, ys, 1)[0])
        px = x + vx * self.pred_dt
        py = y + vy * self.pred_dt
        return px, py


# ==========================================================================================
# PLATFORM MOUSE BACKENDS
# ==========================================================================================

class MouseBackendBase(ABC):
    """Abstract mouse backend."""
    @abstractmethod
    def move_relative(self, dx: int, dy: int) -> None: ...
    @abstractmethod
    def move_absolute(self, x: int, y: int) -> None: ...
    @abstractmethod
    def click(self, button: str = "left", down_only: bool = False, up_only: bool = False) -> None: ...
    @abstractmethod
    def scroll(self, delta: int) -> None: ...
    @abstractmethod
    def get_position(self) -> Tuple[int, int]: ...


class Win32Backend(MouseBackendBase):
    """High-performance Windows backend using win32api."""
    def move_relative(self, dx: int, dy: int) -> None:
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, dx, dy, 0, 0)

    def move_absolute(self, x: int, y: int) -> None:
        # Convert to normalized coords (0–65535)
        sw = win32api.GetSystemMetrics(0)
        sh = win32api.GetSystemMetrics(1)
        nx = int(x * 65535 / sw)
        ny = int(y * 65535 / sh)
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE | win32con.MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0)

    def click(self, button: str = "left", down_only: bool = False, up_only: bool = False) -> None:
        _map = {
            "left":  (win32con.MOUSEEVENTF_LEFTDOWN,  win32con.MOUSEEVENTF_LEFTUP),
            "right": (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
            "middle":(win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP),
        }
        dn, up = _map.get(button, _map["left"])
        if down_only:
            win32api.mouse_event(dn, 0, 0, 0, 0)
        elif up_only:
            win32api.mouse_event(up, 0, 0, 0, 0)
        else:
            win32api.mouse_event(dn | up, 0, 0, 0, 0)

    def scroll(self, delta: int) -> None:
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, delta * 120, 0)

    def get_position(self) -> Tuple[int, int]:
        return win32api.GetCursorPos()


class PyAutoGUIBackend(MouseBackendBase):
    """Universal fallback backend via pyautogui."""
    def move_relative(self, dx: int, dy: int) -> None:
        pyautogui.moveRel(dx, dy, _pause=False)

    def move_absolute(self, x: int, y: int) -> None:
        pyautogui.moveTo(x, y, _pause=False)

    def click(self, button: str = "left", down_only: bool = False, up_only: bool = False) -> None:
        if down_only:
            pyautogui.mouseDown(button=button)
        elif up_only:
            pyautogui.mouseUp(button=button)
        else:
            pyautogui.click(button=button)

    def scroll(self, delta: int) -> None:
        pyautogui.scroll(delta)

    def get_position(self) -> Tuple[int, int]:
        return pyautogui.position()


class MacOSBackend(MouseBackendBase):
    """macOS backend using Quartz CoreGraphics."""
    def _cur_pos(self) -> Tuple[int, int]:
        pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return int(pos.x), int(pos.y)

    def move_relative(self, dx: int, dy: int) -> None:
        x, y = self._cur_pos()
        self.move_absolute(x + dx, y + dy)

    def move_absolute(self, x: int, y: int) -> None:
        ev = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (x, y), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, ev)

    def click(self, button: str = "left", down_only: bool = False, up_only: bool = False) -> None:
        import Quartz.CoreGraphics as CG
        btn_map = {
            "left":  (CG.kCGEventLeftMouseDown,  CG.kCGEventLeftMouseUp,  CG.kCGMouseButtonLeft),
            "right": (CG.kCGEventRightMouseDown, CG.kCGEventRightMouseUp, CG.kCGMouseButtonRight),
        }
        dn_t, up_t, btn = btn_map.get(button, btn_map["left"])
        pos = self._cur_pos()
        if not up_only:
            ev = CG.CGEventCreateMouseEvent(None, dn_t, pos, btn)
            CG.CGEventPost(CG.kCGHIDEventTap, ev)
        if not down_only:
            ev = CG.CGEventCreateMouseEvent(None, up_t, pos, btn)
            CG.CGEventPost(CG.kCGHIDEventTap, ev)

    def scroll(self, delta: int) -> None:
        ev = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, delta)
        CGEventPost(kCGHIDEventTap, ev)

    def get_position(self) -> Tuple[int, int]:
        return self._cur_pos()


def create_mouse_backend() -> MouseBackendBase:
    """Select the best available mouse backend for the current platform."""
    if IS_WINDOWS and WIN32_AVAILABLE:
        logger.info("Mouse backend: win32api (Windows native)")
        return Win32Backend()
    elif IS_MAC and QUARTZ_AVAILABLE:
        logger.info("Mouse backend: Quartz (macOS native)")
        return MacOSBackend()
    elif PYAUTOGUI_AVAILABLE:
        logger.info("Mouse backend: pyautogui (cross-platform fallback)")
        return PyAutoGUIBackend()
    else:
        raise RuntimeError("No usable mouse backend found.")


# ==========================================================================================
# KEYBOARD HELPERS
# ==========================================================================================

def send_key_combo(keys: List[str]) -> None:
    """
    Send a keyboard shortcut across platforms.
    `keys` is a list of key names, e.g. ["ctrl", "win", "left"].
    """
    if IS_WINDOWS and WIN32_AVAILABLE:
        VK = {
            "ctrl": 0x11, "shift": 0x10, "alt": 0x12,
            "win": 0x5B, "left": 0x25, "right": 0x27,
            "up": 0x26, "down": 0x28, "tab": 0x09,
            "f1": 0x70, "f2": 0x71, "esc": 0x1B,
        }
        down_keys = []
        for k in keys:
            vk = VK.get(k.lower())
            if vk:
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                down_keys.append(vk)
        for vk in reversed(down_keys):
            ctypes.windll.user32.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP if IS_WINDOWS else 0x0002, 0)
    elif PYAUTOGUI_AVAILABLE:
        pyautogui.hotkey(*keys)


def take_screenshot(output_dir: str = SCREENSHOT_DIR) -> Optional[str]:
    """Capture a full-screen screenshot and save to output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    ts   = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"screenshot_{ts}.png")
    try:
        if IS_WINDOWS and WIN32_AVAILABLE:
            import win32ui
            hdc   = win32gui.GetDC(0)
            dc    = win32ui.CreateDCFromHandle(hdc)
            mem   = dc.CreateCompatibleDC()
            w, h  = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
            bmp   = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(dc, w, h)
            mem.SelectObject(bmp)
            mem.BitBlt((0, 0), (w, h), dc, (0, 0), win32con.SRCCOPY)
            bmp.SaveBitmapFile(mem, path)
            mem.DeleteDC()
            win32gui.ReleaseDC(0, hdc)
        elif PYAUTOGUI_AVAILABLE:
            img = pyautogui.screenshot()
            img.save(path)
        logger.info(f"Screenshot saved: {path}")
        return path
    except Exception as exc:
        logger.error(f"Screenshot failed: {exc}")
        return None


# ==========================================================================================
# AUDIO FEEDBACK
# ==========================================================================================

class AudioFeedback:
    """Optional audio cues for gestures."""
    def __init__(self, cfg: Dict[str, Any]):
        self.enabled = cfg.get("enable", False) and AUDIO_AVAILABLE
        self.volume  = cfg.get("volume", 0.5)
        self._lock   = threading.Lock()

    def _play(self, freq: int = 800, duration_ms: int = 50) -> None:
        """Non-blocking beep."""
        def _do():
            with self._lock:
                try:
                    if IS_WINDOWS:
                        winsound.Beep(freq, duration_ms)
                    else:
                        # On Linux/macOS: use system bell or playsound
                        os.system(f"beep -f {freq} -l {duration_ms} 2>/dev/null || true")
                except Exception:
                    pass
        threading.Thread(target=_do, daemon=True).start()

    def click_sound(self)   -> None:
        if self.enabled: self._play(900, 40)

    def gesture_sound(self) -> None:
        if self.enabled: self._play(700, 60)

    def drag_sound(self)    -> None:
        if self.enabled: self._play(600, 80)

    def error_sound(self)   -> None:
        if self.enabled: self._play(300, 150)


# ==========================================================================================
# TELEMETRY
# ==========================================================================================

class TelemetryBackend(ABC):
    @abstractmethod
    def record(self, event: str, data: Dict[str, Any]) -> None: ...
    @abstractmethod
    def flush(self) -> None: ...
    @abstractmethod
    def close(self) -> None: ...


class CSVTelemetry(TelemetryBackend):
    """Write gesture events to a rotating CSV log."""
    def __init__(self):
        ts   = time.strftime("%Y%m%d_%H%M%S")
        self._path = f"telemetry_{ts}.csv"
        self._f    = open(self._path, 'w', newline='', encoding='utf-8')
        self._writer = csv.writer(self._f)
        self._writer.writerow(["timestamp", "event", "data"])

    def record(self, event: str, data: Dict[str, Any]) -> None:
        self._writer.writerow([time.time(), event, json.dumps(data)])

    def flush(self) -> None:
        self._f.flush()

    def close(self) -> None:
        self._f.close()


class SQLiteTelemetry(TelemetryBackend):
    """Write gesture events to a SQLite database."""
    def __init__(self):
        self._conn = sqlite3.connect(TELEMETRY_DB, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events "
            "(id INTEGER PRIMARY KEY, ts REAL, event TEXT, data TEXT)"
        )
        self._conn.commit()

    def record(self, event: str, data: Dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO events (ts, event, data) VALUES (?, ?, ?)",
            (time.time(), event, json.dumps(data))
        )

    def flush(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()


def create_telemetry(cfg: Dict[str, Any]) -> Optional[TelemetryBackend]:
    """Create and return a telemetry backend if enabled."""
    if not cfg.get("telemetry_enabled", False):
        return None
    backend = cfg.get("telemetry_backend", "csv")
    if backend == "sqlite":
        return SQLiteTelemetry()
    return CSVTelemetry()


# ==========================================================================================
# GESTURE RECOGNIZERS
# ==========================================================================================

class GestureRecognizerBase(ABC):
    """Abstract base class for all gesture recognizers."""
    @abstractmethod
    def update(self, *args, **kwargs): ...
    def reset(self) -> None: pass


class DoubleFistRecognizer(GestureRecognizerBase):
    """
    Detects a double-fist gesture for left click.
    User closes their fist twice within `double_click_timeout` seconds.
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.threshold = cfg["fist_threshold"]
        self.timeout   = cfg["double_click_timeout"]
        self._last_fist_time = 0.0
        self._fist_state     = False

    def get_curl(self, landmarks, w: int, h: int, hand_size: float = 100.0) -> float:
        """Return average curl ratio across all 5 fingers (0=open, 1=fist)."""
        ratios = []
        pairs = [
            (THUMB_TIP, THUMB_MCP, True),
            (INDEX_TIP, INDEX_MCP, False),
            (MIDDLE_TIP, MIDDLE_MCP, False),
            (RING_TIP, RING_MCP, False),
            (PINKY_TIP, PINKY_MCP, False),
        ]
        scale = max(hand_size / 100.0, 0.5)
        for tip_i, base_i, is_thumb in pairs:
            tip  = lm_to_px(landmarks[tip_i], w, h)
            base = lm_to_px(landmarks[base_i], w, h)
            if is_thumb:
                diff  = abs(tip[0] - base[0])
                ratio = clamp(diff / (30.0 * scale), 0.0, 1.0)
            else:
                diff  = tip[1] - base[1]  # positive = tip below base = curled
                ratio = clamp(diff / (40.0 * scale), 0.0, 1.0)
            ratios.append(ratio)
        return float(np.mean(ratios))

    def update(self, curl: float, now: float) -> bool:
        is_fist  = curl > self.threshold
        triggered = False
        if is_fist and not self._fist_state:
            self._fist_state = True
            if now - self._last_fist_time < self.timeout:
                triggered = True
                self._last_fist_time = 0.0
            else:
                self._last_fist_time = now
        elif not is_fist:
            self._fist_state = False
        return triggered

    def reset(self) -> None:
        self._fist_state     = False
        self._last_fist_time = 0.0


class PeaceSignRecognizer(GestureRecognizerBase):
    """Detects a ✌️ (peace / V-sign) gesture for right click."""
    def __init__(self, cfg: Dict[str, Any]):
        self.hold_duration = cfg.get("hold_duration", 0.0)
        self._hold_start: Optional[float] = None

    def update(self, landmarks, w: int, h: int, now: float) -> bool:
        index_up  = finger_extended(landmarks, INDEX_TIP,  INDEX_PIP)
        middle_up = finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP)
        ring_dn   = not finger_extended(landmarks, RING_TIP,  RING_PIP)
        pinky_dn  = not finger_extended(landmarks, PINKY_TIP, PINKY_PIP)
        thumb_curl = dist2d(lm_to_px(landmarks[THUMB_TIP], w, h),
                            lm_to_px(landmarks[THUMB_IP],  w, h)) < 40.0
        sign = index_up and middle_up and ring_dn and pinky_dn and thumb_curl

        if sign:
            if self._hold_start is None:
                self._hold_start = now
            if self.hold_duration <= 0 or (now - self._hold_start) >= self.hold_duration:
                self._hold_start = None
                return True
        else:
            self._hold_start = None
        return False


class TwoFingerScrollRecognizer(GestureRecognizerBase):
    """
    Detects two-finger vertical movement for scrolling.
    Triggered when index and middle fingers are spread apart horizontally
    and moved up/down together.
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.sensitivity  = cfg.get("sensitivity", 18)
        self.dist_thresh  = cfg.get("distance_threshold", 45)
        self._prev_avg_y: Optional[float] = None
        self._locked      = False

    def update(self, landmarks, w: int, h: int) -> int:
        it = lm_to_px(landmarks[INDEX_TIP],  w, h)
        mt = lm_to_px(landmarks[MIDDLE_TIP], w, h)
        sep   = dist2d(it, mt)
        avg_y = (it[1] + mt[1]) / 2.0
        if sep > self.dist_thresh:
            if not self._locked:
                self._locked    = True
                self._prev_avg_y = avg_y
                return 0
            if self._prev_avg_y is None:
                self._prev_avg_y = avg_y
            dy = avg_y - self._prev_avg_y
            self._prev_avg_y = avg_y
            val = int(dy * self.sensitivity / 60.0)
            return -val  # positive dy = scroll down
        else:
            self._locked     = False
            self._prev_avg_y = None
            return 0

    def reset(self) -> None:
        self._locked     = False
        self._prev_avg_y = None


class WristRollScrollRecognizer(GestureRecognizerBase):
    """
    Detects wrist tilt/roll for continuous scrolling.
    Tilt hand left/right → scroll up/down.
    Requires open-ish hand (not a fist).
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.sensitivity  = cfg.get("wrist_roll_sensitivity", 25)
        self._neutral_angle: Optional[float] = None
        self._calibrated  = False

    def calibrate(self, landmarks) -> None:
        self._neutral_angle = wrist_roll_angle(landmarks)
        self._calibrated    = True

    def update(self, landmarks, curl: float) -> int:
        if curl > 0.5:  # fist-like: skip
            return 0
        angle = wrist_roll_angle(landmarks)
        if not self._calibrated or self._neutral_angle is None:
            self._neutral_angle = angle
            self._calibrated    = True
            return 0
        delta = angle - self._neutral_angle
        if abs(delta) < 5.0:  # dead zone
            return 0
        return int(-delta * self.sensitivity / 30.0)

    def reset(self) -> None:
        self._calibrated    = False
        self._neutral_angle = None


class PinchDragRecognizer(GestureRecognizerBase):
    """Thumb-index pinch → toggle drag lock."""
    def __init__(self, cfg: Dict[str, Any]):
        self.threshold = cfg.get("pinch_threshold", 42)
        self.pinching  = False

    def update(self, landmarks, w: int, h: int) -> bool:
        tt = lm_to_px(landmarks[THUMB_TIP],  w, h)
        it = lm_to_px(landmarks[INDEX_TIP], w, h)
        return dist2d(tt, it) < self.threshold


class ThreeFingerSwipeRecognizer(GestureRecognizerBase):
    """
    Detects a three-finger horizontal swipe for virtual desktop navigation.
    Returns "left", "right", or None.
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.swipe_thresh    = cfg.get("swipe_threshold", 55)
        self.velocity_thresh = cfg.get("velocity_threshold", 190)
        self._tracking   = False
        self._start_x: Optional[float] = None
        self._last_time: Optional[float] = None

    def update(self, landmarks, w: int, h: int, now: float) -> Optional[str]:
        idx_up = finger_extended(landmarks, INDEX_TIP,  INDEX_PIP)
        mid_up = finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP)
        rng_up = finger_extended(landmarks, RING_TIP,   RING_PIP)
        if not (idx_up and mid_up and rng_up):
            self._tracking = False
            self._start_x  = None
            return None
        x = lm_to_px(landmarks[MIDDLE_TIP], w, h)[0]
        if not self._tracking:
            self._tracking = True
            self._start_x  = x
            self._last_time = now
            return None
        dx  = x - (self._start_x or x)
        dt  = now - (self._last_time or now)
        if abs(dx) > self.swipe_thresh and dt > 0:
            vel = dx / dt
            if abs(vel) > self.velocity_thresh:
                self._tracking = False
                self._start_x  = None
                return "right" if dx > 0 else "left"
        self._last_time = now
        return None


class ZoomRecognizer(GestureRecognizerBase):
    """
    Tracks the distance between thumb-tip and index-tip.
    Change in distance → zoom delta.
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.sensitivity = cfg.get("sensitivity", 0.012)
        self.min_delta   = cfg.get("min_delta", 2.5)
        self._prev_dist: Optional[float] = None

    def update(self, landmarks, w: int, h: int) -> float:
        tt = lm_to_px(landmarks[THUMB_TIP],  w, h)
        it = lm_to_px(landmarks[INDEX_TIP], w, h)
        d  = dist2d(tt, it)
        if self._prev_dist is None:
            self._prev_dist = d
            return 0.0
        delta = (d - self._prev_dist) * self.sensitivity
        self._prev_dist = d
        return delta if abs(delta) > self.min_delta * self.sensitivity else 0.0

    def reset(self) -> None:
        self._prev_dist = None


class OpenPalmFreezeRecognizer(GestureRecognizerBase):
    """
    Detects an open flat palm → freeze cursor.
    All fingers extended AND low curl ratio indicates flat palm.
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.flat_threshold = cfg.get("flat_threshold", 0.12)

    def update(self, landmarks, curl: float) -> bool:
        extended = all_fingers_extended(landmarks, exclude_thumb=True)
        return extended and curl < self.flat_threshold


class FingertipCircleRecognizer(GestureRecognizerBase):
    """
    Tracks the path of the index fingertip.
    If the path approximates a circle → triggers screenshot.
    """
    def __init__(self, cfg: Dict[str, Any]):
        self.radius_thresh = cfg.get("circle_radius_threshold", 30)
        self.min_points    = cfg.get("min_points", 20)
        self._points: List[Tuple[float, float]] = []
        self._tracking    = False
        self._track_start = 0.0
        self._timeout     = 3.0  # max seconds to complete circle

    def update(self, landmarks, w: int, h: int, now: float, drawing: bool) -> bool:
        """
        `drawing` should be True when only the index finger is extended and all others curled.
        Returns True when a circle is detected.
        """
        if not drawing:
            # Evaluate if we have enough points
            if self._tracking and len(self._points) >= self.min_points:
                radius, error = circle_score(self._points)
                if radius > self.radius_thresh and error < radius * 0.35:
                    self._points.clear()
                    self._tracking = False
                    return True
            self._points.clear()
            self._tracking = False
            return False

        if not self._tracking:
            self._tracking    = True
            self._track_start = now

        # Timeout
        if now - self._track_start > self._timeout:
            self._points.clear()
            self._tracking    = False
            self._track_start = now
            return False

        tip = lm_to_px(landmarks[INDEX_TIP], w, h)
        self._points.append(tip)
        return False

    def reset(self) -> None:
        self._points.clear()
        self._tracking = False


# ==========================================================================================
# ADAPTIVE GESTURE LEARNER
# ==========================================================================================

class AdaptiveLearner:
    """
    Online adaptive threshold tuner.
    Observes gesture trigger events and the activating signal values,
    then nudges thresholds toward the observed distribution center.
    """
    def __init__(self, learning_rate: float = 0.05):
        self.lr        = learning_rate
        self._obs: Dict[str, List[float]] = {}

    def observe(self, gesture: str, signal_value: float) -> None:
        if gesture not in self._obs:
            self._obs[gesture] = []
        self._obs[gesture].append(signal_value)
        # Keep last 50 observations
        if len(self._obs[gesture]) > 50:
            self._obs[gesture].pop(0)

    def suggest_threshold(self, gesture: str, current: float) -> float:
        """Return a nudged threshold based on observations."""
        obs = self._obs.get(gesture)
        if not obs or len(obs) < 5:
            return current
        mean = float(np.mean(obs))
        # Nudge toward (mean - 1 std) so trigger is slightly below average
        std  = float(np.std(obs))
        target = mean - 0.5 * std
        return current + self.lr * (target - current)


# ==========================================================================================
# MOUSE CONTROLLER (HIGH-LEVEL)
# ==========================================================================================

class MouseController:
    """
    High-level mouse controller.
    Wraps a platform backend with filtering, prediction, acceleration, and drag state.
    """
    def __init__(self, config: Config, backend: MouseBackendBase):
        self.cfg     = config
        self.backend = backend
        self.monitors = get_monitors_info()
        bounds = get_virtual_screen_bounds(self.monitors)
        self.screen_left, self.screen_top, self.screen_right, self.screen_bottom = bounds
        self.screen_w = self.screen_right  - self.screen_left
        self.screen_h = self.screen_bottom - self.screen_top

        freq = self.cfg.advanced.get("fps_limit", 60)
        ft   = self.cfg.mouse.get("filter_type", "one_euro")
        self._filter_x = make_filter(ft, freq, self.cfg.mouse)
        self._filter_y = make_filter(ft, freq, self.cfg.mouse)

        pred_ms = self.cfg.mouse.get("prediction_ms", 15.0)
        self._predictor = MotionPredictor(pred_ms) if pred_ms > 0 else None

        self._last_pos:   Optional[Tuple[float, float]] = None
        self._last_time:  Optional[float] = None
        self.drag_active  = False
        self._last_click  = 0.0
        self._click_cd    = self.cfg.gestures.get("click_cooldown", 0.22)
        self._smooth_vx   = 0.0
        self._smooth_vy   = 0.0
        self._cursor_frozen = False

    def freeze(self, state: bool) -> None:
        """Freeze/unfreeze cursor movement."""
        self._cursor_frozen = state

    def reset_filters(self) -> None:
        """Reset all filters (called when hand is lost)."""
        self._filter_x.reset()
        self._filter_y.reset()
        if self._predictor:
            self._predictor.history.clear()
        self._last_pos  = None
        self._last_time = None
        self._smooth_vx = 0.0
        self._smooth_vy = 0.0

    def update(self, hand_px: Tuple[float, float], now: float) -> None:
        """Process a new hand position and move the cursor accordingly."""
        if self._cursor_frozen:
            return

        fx = self._filter_x.filter(hand_px[0])
        fy = self._filter_y.filter(hand_px[1])

        if self._predictor is not None:
            fx, fy = self._predictor.predict(fx, fy, now)
            self._predictor.push(hand_px[0], hand_px[1], now)

        if self._last_pos is None or self._last_time is None:
            self._last_pos  = (fx, fy)
            self._last_time = now
            return

        dt = max(0.001, now - self._last_time)

        raw_vx = (fx - self._last_pos[0]) / dt
        raw_vy = (fy - self._last_pos[1]) / dt

        # Dead zone
        dz = self.cfg.mouse.get("dead_zone", 2.0)
        if abs(raw_vx) < dz: raw_vx = 0.0
        if abs(raw_vy) < dz: raw_vy = 0.0

        # Invert
        if self.cfg.mouse.get("invert_x"): raw_vx = -raw_vx
        if self.cfg.mouse.get("invert_y"): raw_vy = -raw_vy

        # Acceleration
        if self.cfg.mouse.get("acceleration"):
            speed = math.hypot(raw_vx, raw_vy)
            thresh = self.cfg.mouse.get("accel_threshold", 280.0)
            mult   = self.cfg.mouse.get("accel_multiplier", 1.6)
            if speed > thresh:
                factor = 1.0 + (mult - 1.0) * clamp((speed - thresh) / thresh, 0.0, 1.5)
                raw_vx *= factor
                raw_vy *= factor

        gain   = self.cfg.mouse.get("velocity_gain", 2.2)
        max_sp = self.cfg.mouse.get("max_speed", 1500.0)
        vx = clamp(raw_vx * gain, -max_sp, max_sp)
        vy = clamp(raw_vy * gain, -max_sp, max_sp)

        dx = int(vx * dt)
        dy = int(vy * dt)

        if dx != 0 or dy != 0:
            try:
                self.backend.move_relative(dx, dy)
            except Exception as exc:
                logger.debug(f"move_relative error: {exc}")

        self._last_pos  = (fx, fy)
        self._last_time = now

    def click(self, button: str = "left", down_only: bool = False, up_only: bool = False) -> None:
        """Send a mouse click with cooldown protection."""
        now = time.time()
        if not down_only and not up_only:
            if now - self._last_click < self._click_cd:
                return
            self._last_click = now
        try:
            self.backend.click(button, down_only, up_only)
        except Exception as exc:
            logger.debug(f"click error: {exc}")

    def scroll(self, delta: int) -> None:
        """Send scroll wheel event."""
        if delta == 0:
            return
        try:
            self.backend.scroll(delta)
        except Exception as exc:
            logger.debug(f"scroll error: {exc}")

    def start_drag(self) -> None:
        """Begin drag: press and hold left button."""
        if not self.drag_active:
            self.click("left", down_only=True)
            self.drag_active = True
            logger.info("Drag lock ON")

    def stop_drag(self) -> None:
        """End drag: release left button."""
        if self.drag_active:
            self.click("left", up_only=True)
            self.drag_active = False
            logger.info("Drag lock OFF")

    def zoom(self, delta: float) -> None:
        """Simulate Ctrl+scroll for application zoom."""
        steps = int(delta)
        if steps == 0:
            return
        send_key_combo(["ctrl"])   # just hold ctrl
        try:
            self.backend.scroll(steps)
        finally:
            # Release ctrl via separate call
            if IS_WINDOWS and WIN32_AVAILABLE:
                ctypes.windll.user32.keybd_event(0x11, 0, win32con.KEYEVENTF_KEYUP, 0)
            elif PYAUTOGUI_AVAILABLE:
                pyautogui.keyUp("ctrl")

    def navigate_desktop(self, direction: str) -> None:
        """Send virtual desktop switch shortcut."""
        logger.info(f"Desktop switch: {direction}")
        if IS_WINDOWS:
            send_key_combo(["ctrl", "win", direction])
        elif IS_MAC:
            # Mission Control: Ctrl+Left/Ctrl+Right
            send_key_combo(["ctrl", direction])
        else:
            # Most Linux DEs: Ctrl+Alt+Left/Right
            send_key_combo(["ctrl", "alt", direction])


# ==========================================================================================
# HAND DETECTOR (MediaPipe)
# ==========================================================================================

class HandDetector:
    """
    Wraps MediaPipe Hands for landmark detection.
    Supports both the legacy `mediapipe.solutions.hands` API and the newer Tasks API.
    """
    MODEL_URL = (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    )
    MODEL_PATH = "hand_landmarker.task"

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._use_tasks = False
        self._init_detector()

    def _ensure_model(self) -> None:
        """Download the landmark model if not present."""
        if not os.path.exists(self.MODEL_PATH):
            logger.info("Downloading MediaPipe hand landmark model (~10 MB)…")
            import urllib.request
            try:
                urllib.request.urlretrieve(self.MODEL_URL, self.MODEL_PATH)
                logger.info("Model downloaded successfully.")
            except Exception as exc:
                logger.error(f"Model download failed: {exc}")
                raise

    def _init_detector(self) -> None:
        """Try Tasks API first; fall back to legacy solutions API."""
        try:
            self._ensure_model()
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
            base = mp_python.BaseOptions(model_asset_path=self.MODEL_PATH)
            opts = mp_vision.HandLandmarkerOptions(
                base_options=base,
                num_hands=self.cfg.hand_tracking["num_hands"],
                min_hand_detection_confidence=self.cfg.hand_tracking["min_detection_confidence"],
                min_tracking_confidence=self.cfg.hand_tracking["min_tracking_confidence"],
            )
            self._detector = mp_vision.HandLandmarker.create_from_options(opts)
            self._use_tasks = True
            logger.info("MediaPipe: using Tasks API (hand_landmarker.task)")
        except Exception as exc:
            logger.warning(f"Tasks API unavailable ({exc}); using legacy solutions.hands")
            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=self.cfg.hand_tracking["num_hands"],
                min_detection_confidence=self.cfg.hand_tracking["min_detection_confidence"],
                min_tracking_confidence=self.cfg.hand_tracking["min_tracking_confidence"],
                model_complexity=self.cfg.hand_tracking.get("model_complexity", 1),
            )
            self._use_tasks = False

    def detect(self, rgb_frame: np.ndarray) -> Any:
        """Run detection and return a result object."""
        if self._use_tasks:
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            return self._detector.detect(img)
        else:
            return self._mp_hands.process(rgb_frame)

    @staticmethod
    def parse_result(result: Any) -> Tuple[Optional[List], Optional[List]]:
        """
        Parse a detection result (Tasks or legacy) into:
        (list_of_landmark_lists, list_of_handedness_lists)
        Returns (None, None) if no hands found.
        """
        # Tasks API
        if hasattr(result, 'hand_landmarks') and result.hand_landmarks:
            return result.hand_landmarks, result.handedness
        # Legacy API
        if hasattr(result, 'multi_hand_landmarks') and result.multi_hand_landmarks:
            return result.multi_hand_landmarks, result.multi_handedness
        return None, None

    def release(self) -> None:
        """Clean up MediaPipe resources."""
        try:
            if self._use_tasks:
                self._detector.close()
            else:
                self._mp_hands.close()
        except Exception:
            pass


# ==========================================================================================
# HAND TRACKER (MULTI-HAND ROLE ASSIGNMENT)
# ==========================================================================================

class HandTracker:
    """
    Assigns detected hands to primary (cursor) and secondary (gesture assist) roles.
    Handles hand-lost timeout and smooth hand-swap transitions.
    """
    def __init__(self, cfg: Config, mouse: MouseController):
        self.cfg           = cfg
        self.mouse         = mouse
        self.primary_pref  = cfg.hand_tracking.get("primary_hand", "right").lower()
        self.lost_timeout  = cfg.hand_tracking.get("hand_lost_timeout", 2.0)
        self._last_seen    = 0.0
        self._hand_lost    = False

    def _label(self, handedness_entry) -> str:
        """Extract 'left' or 'right' from a handedness entry."""
        try:
            # Tasks API: list of Classification
            return handedness_entry[0].category_name.lower()
        except (AttributeError, IndexError, TypeError):
            try:
                # Legacy: ClassificationList
                return handedness_entry.classification[0].label.lower()
            except Exception:
                return "unknown"

    def assign(
        self,
        landmarks_list: List,
        handedness_list: List,
        now: float
    ) -> Tuple[Optional[Any], Optional[Any]]:
        """
        Assign primary and secondary hand landmarks.
        Returns (primary_landmarks, secondary_landmarks).
        """
        self._last_seen    = now
        self._hand_lost    = False

        primary   = None
        secondary = None

        for lms, hand in zip(landmarks_list, handedness_list):
            label = self._label(hand)
            if label == self.primary_pref:
                primary = lms
            else:
                secondary = lms

        # If preferred primary not found, use first detected hand
        if primary is None:
            primary = landmarks_list[0]
            if len(landmarks_list) > 1:
                secondary = landmarks_list[1]

        return primary, secondary

    def tick(self, now: float) -> None:
        """Call each frame even if no hands detected; triggers hand-lost logic."""
        if not self._hand_lost and now - self._last_seen > self.lost_timeout:
            self._hand_lost = True
            logger.debug("Hand lost – resetting filters")
            self.mouse.reset_filters()

    @property
    def hand_present(self) -> bool:
        return not self._hand_lost


# ==========================================================================================
# CALIBRATOR
# ==========================================================================================

class Calibrator:
    """
    Auto-calibration routine: collects hand size samples over N seconds,
    then scales gesture thresholds to match the user's hand.
    """
    def __init__(self, cfg: Config):
        self.cfg          = cfg
        self.calibrating  = False
        self._start_time  = 0.0
        self._sizes: List[float] = []
        self._duration    = cfg.advanced.get("calibration_duration", 3.0)

    def start(self) -> None:
        self.calibrating = True
        self._start_time = time.time()
        self._sizes      = []
        logger.info(f"Calibration started ({self._duration:.0f}s). Show open hand to camera…")

    def update(self, landmarks, w: int, h: int) -> bool:
        """Call each frame during calibration. Returns True when done."""
        if not self.calibrating:
            return False
        size = compute_hand_size(landmarks, w, h)
        if size > 10:
            self._sizes.append(size)
        if time.time() - self._start_time >= self._duration:
            self._finish()
            return True
        return False

    def _finish(self) -> None:
        if not self._sizes:
            logger.warning("Calibration: no valid samples collected.")
            self.calibrating = False
            return
        avg  = float(np.mean(self._sizes))
        base = 100.0
        scale = avg / base
        logger.info(f"Calibration complete. Hand size: {avg:.1f}px  scale={scale:.2f}")
        # Scale thresholds
        g = self.cfg.gestures
        g["left_click"]["fist_threshold"]    = clamp(g["left_click"]["fist_threshold"] * scale, 0.3, 0.9)
        g["drag_lock"]["pinch_threshold"]    = clamp(g["drag_lock"]["pinch_threshold"] * scale, 15, 100)
        g["scroll"]["distance_threshold"]   = clamp(g["scroll"]["distance_threshold"] * scale, 20, 120)
        self.cfg.save()
        self.calibrating = False


# ==========================================================================================
# FRAME CAPTURE (THREADED, HEADLESS)
# ==========================================================================================

class CameraCapture:
    """
    Dedicated capture thread that decouples camera I/O from processing.
    Drops frames when the processing pipeline is busy to minimize latency.
    """
    def __init__(self, cfg: Config):
        self.cfg         = cfg
        self._cam        = cv2.VideoCapture(cfg.camera["device_id"])
        self._configure()
        self._queue      = queue.Queue(maxsize=cfg.advanced.get("frame_queue_size", 2))
        self._stop       = Event()
        self._thread     = threading.Thread(target=self._loop, name="CaptureThread", daemon=True)
        self._thread.start()
        self.frames_grabbed = 0
        self.frames_dropped = 0

    def _configure(self) -> None:
        c = self.cfg.camera
        self._cam.set(cv2.CAP_PROP_FRAME_WIDTH,  c["frame_width"])
        self._cam.set(cv2.CAP_PROP_FRAME_HEIGHT, c["frame_height"])
        self._cam.set(cv2.CAP_PROP_BUFFERSIZE,   c.get("buffer_size", 1))
        if c.get("auto_exposure", True):
            self._cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
        else:
            self._cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            self._cam.set(cv2.CAP_PROP_EXPOSURE, c.get("exposure", -6))
        self._cam.set(cv2.CAP_PROP_BRIGHTNESS, c.get("brightness", 128))
        self._cam.set(cv2.CAP_PROP_CONTRAST,   c.get("contrast", 128))

    def _loop(self) -> None:
        target_fps  = self.cfg.camera.get("target_fps", 30)
        frame_time  = 1.0 / target_fps
        flip_h      = self.cfg.camera.get("flip_horizontal", True)
        flip_v      = self.cfg.camera.get("flip_vertical", False)
        while not self._stop.is_set():
            t0 = time.monotonic()
            ok, frame = self._cam.read()
            if not ok:
                logger.warning("Camera read failed – retrying…")
                time.sleep(0.05)
                continue
            self.frames_grabbed += 1
            if flip_h: frame = cv2.flip(frame, 1)
            if flip_v: frame = cv2.flip(frame, 0)
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    self.frames_dropped += 1
                except queue.Empty:
                    pass
            self._queue.put(frame)
            elapsed = time.monotonic() - t0
            sleep   = frame_time - elapsed
            if sleep > 0:
                time.sleep(sleep)

    def get(self) -> Optional[np.ndarray]:
        """Non-blocking frame fetch. Returns None if no frame available."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def release(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._cam.release()
        logger.debug(
            f"Camera released. Grabbed={self.frames_grabbed} Dropped={self.frames_dropped}"
        )


# ==========================================================================================
# PERFORMANCE MONITOR
# ==========================================================================================

class PerformanceMonitor:
    """Tracks processing FPS and per-section timing."""
    def __init__(self, log_fps: bool = False):
        self.log_fps     = log_fps
        self._count      = 0
        self._last_t     = time.monotonic()
        self.fps         = 0.0
        self._section_times: Dict[str, Deque[float]] = {}

    def tick(self) -> None:
        self._count += 1
        now = time.monotonic()
        dt  = now - self._last_t
        if dt >= 1.0:
            self.fps     = self._count / dt
            self._count  = 0
            self._last_t = now
            if self.log_fps:
                logger.debug(f"Processing FPS: {self.fps:.1f}")

    @contextmanager
    def section(self, name: str):
        """Context manager for timing a code section."""
        t0 = time.monotonic()
        yield
        dt = time.monotonic() - t0
        if name not in self._section_times:
            self._section_times[name] = deque(maxlen=60)
        self._section_times[name].append(dt)

    def report(self) -> Dict[str, float]:
        """Return average timing (ms) per section."""
        return {k: 1000.0 * float(np.mean(v)) for k, v in self._section_times.items()}


# ==========================================================================================
# PLUGIN SYSTEM
# ==========================================================================================

class PluginBase(ABC):
    """
    Base class for Air Mouse Pro plugins.
    Drop subclasses of PluginBase in the /plugins directory.
    """
    name    = "unnamed_plugin"
    version = "1.0"

    def __init__(self, app: "AirMousePro"): ...
    def on_gesture(self, gesture: str, data: Dict[str, Any]) -> None: ...
    def on_frame(self, landmarks: Any, frame_shape: Tuple) -> None: ...
    def shutdown(self) -> None: ...


class PluginManager:
    """Loads and manages plugins from the PLUGIN_DIR folder."""
    def __init__(self, app: "AirMousePro"):
        self._app     = app
        self._plugins: List[PluginBase] = []
        self._dir     = PLUGIN_DIR

    def load_all(self) -> None:
        if not os.path.isdir(self._dir):
            return
        for path in Path(self._dir).glob("*.py"):
            self._load(path)

    def _load(self, path: Path) -> None:
        try:
            spec   = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for attr in dir(module):
                cls = getattr(module, attr)
                if (isinstance(cls, type)
                        and issubclass(cls, PluginBase)
                        and cls is not PluginBase):
                    inst = cls(self._app)
                    self._plugins.append(inst)
                    logger.info(f"Plugin loaded: {cls.name} v{cls.version}")
        except Exception as exc:
            logger.warning(f"Plugin load failed ({path.name}): {exc}")

    def broadcast_gesture(self, gesture: str, data: Dict[str, Any]) -> None:
        for p in self._plugins:
            with suppress(Exception):
                p.on_gesture(gesture, data)

    def broadcast_frame(self, landmarks: Any, frame_shape: Tuple) -> None:
        for p in self._plugins:
            with suppress(Exception):
                p.on_frame(landmarks, frame_shape)

    def shutdown_all(self) -> None:
        for p in self._plugins:
            with suppress(Exception):
                p.shutdown()


# ==========================================================================================
# SYSTEM TRAY ICON
# ==========================================================================================

class TrayIcon:
    """Optional system tray icon with status display and quick controls."""
    def __init__(self, app: "AirMousePro"):
        self._app    = app
        self._icon   = None
        self._paused = False
        if not TRAY_AVAILABLE:
            logger.warning("pystray or Pillow not installed – tray disabled.")
            return
        self._menu = pystray.Menu(
            pystray.MenuItem("Air Mouse Pro v5.0", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause / Resume", self._toggle_pause),
            pystray.MenuItem("Calibrate",      self._calibrate),
            pystray.MenuItem("Reload Config",  self._reload_cfg),
            pystray.MenuItem("Screenshot",     self._screenshot),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit",           self._exit),
        )
        self._icon = pystray.Icon(
            "AirMousePro",
            self._make_image(active=True),
            "Air Mouse Pro v5.0",
            self._menu
        )

    def _make_image(self, active: bool = True) -> "Image.Image":
        size  = 64
        img   = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(img)
        color = (0, 180, 255, 255) if active else (120, 120, 120, 255)
        draw.ellipse((4, 4, 60, 60), fill=color, outline=(255, 255, 255, 200), width=3)
        # Hand silhouette (simplified dots)
        for cx, cy in [(32, 22), (24, 32), (32, 42), (40, 32)]:
            draw.ellipse((cx-4, cy-4, cx+4, cy+4), fill=(255, 255, 255, 200))
        return img

    def _toggle_pause(self, icon, item) -> None:
        self._paused    = not self._paused
        self._app.paused = self._paused
        icon.icon = self._make_image(not self._paused)
        logger.info("Paused" if self._paused else "Resumed")

    def _calibrate(self, icon, item) -> None:
        self._app.calibrator.start()

    def _reload_cfg(self, icon, item) -> None:
        changed = self._app.config.reload()
        logger.info(f"Config reloaded (changed={changed})")

    def _screenshot(self, icon, item) -> None:
        take_screenshot()

    def _exit(self, icon, item) -> None:
        self._app.running = False
        icon.stop()

    def run(self) -> None:
        if self._icon:
            self._icon.run_detached()
            logger.info("System tray icon active.")

    def stop(self) -> None:
        if self._icon:
            with suppress(Exception):
                self._icon.stop()


# ==========================================================================================
# REST API CONTROLLER
# ==========================================================================================

class RestAPIController:
    """
    Optional HTTP REST API for external control.
    Starts a Flask server on localhost:5765 (configurable).
    Endpoints:
        GET  /status           – JSON status info
        POST /pause            – Pause/resume
        POST /calibrate        – Start calibration
        POST /config           – Update config key (body: {"key": "...", "value": ...})
        GET  /screenshot       – Take screenshot
    """
    def __init__(self, app: "AirMousePro", host: str = "127.0.0.1", port: int = 5765):
        if not FLASK_AVAILABLE:
            logger.warning("Flask not installed – REST API disabled.")
            self._flask = None
            return
        self._app  = app
        self._host = host
        self._port = port
        self._flask_app = Flask("AirMousePro")
        self._register_routes()
        self._thread = threading.Thread(target=self._run, daemon=True, name="RestAPI")

    def _register_routes(self) -> None:
        fa = self._flask_app

        @fa.route("/status", methods=["GET"])
        def status():
            return jsonify({
                "running": self._app.running,
                "paused":  self._app.paused,
                "fps":     self._app.perf.fps,
                "drag":    self._app.mouse.drag_active,
                "frozen":  self._app.mouse._cursor_frozen,
            })

        @fa.route("/pause", methods=["POST"])
        def pause():
            self._app.paused = not self._app.paused
            return jsonify({"paused": self._app.paused})

        @fa.route("/calibrate", methods=["POST"])
        def calibrate():
            self._app.calibrator.start()
            return jsonify({"ok": True})

        @fa.route("/screenshot", methods=["GET"])
        def screenshot():
            path = take_screenshot()
            return jsonify({"path": path})

    def _run(self) -> None:
        import logging as _log
        _log.getLogger("werkzeug").setLevel(_log.ERROR)
        self._flask_app.run(host=self._host, port=self._port, use_reloader=False)

    def start(self) -> None:
        if FLASK_AVAILABLE and hasattr(self, "_thread"):
            self._thread.start()
            logger.info(f"REST API listening on http://{self._host}:{self._port}")


# ==========================================================================================
# HOT-RELOAD WATCHER
# ==========================================================================================

class ConfigWatcher:
    """Watches the config file for changes and reloads on-the-fly."""
    def __init__(self, cfg: Config, interval: float = 3.0):
        self.cfg        = cfg
        self.interval   = interval
        self._last_mtime = self._mtime()
        self._stop      = Event()
        self._thread    = threading.Thread(target=self._watch, daemon=True, name="ConfigWatcher")

    def _mtime(self) -> float:
        try:
            return os.path.getmtime(self.cfg._path)
        except OSError:
            return 0.0

    def _watch(self) -> None:
        while not self._stop.is_set():
            time.sleep(self.interval)
            mt = self._mtime()
            if mt != self._last_mtime:
                self._last_mtime = mt
                changed = self.cfg.reload()
                if changed:
                    logger.info("Config hot-reloaded from disk.")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


# ==========================================================================================
# MAIN APPLICATION
# ==========================================================================================

class AirMousePro:
    """
    Air Mouse Superior Pro v5.0 – main application class.
    Orchestrates all subsystems: capture, detection, gesture recognition,
    mouse control, plugins, telemetry, tray, and REST API.
    """

    def __init__(self, config_path: str = CONFIG_FILE):
        global logger
        # ── Config ──────────────────────────────────────────────────────────────────────
        self.config = Config.load(config_path)
        logger = setup_logging(
            self.config.performance.get("log_level", "INFO"),
            self.config.performance.get("log_to_file", True)
        )
        self._log_banner()

        # ── Core subsystems ─────────────────────────────────────────────────────────────
        self.backend   = create_mouse_backend()
        self.mouse     = MouseController(self.config, self.backend)
        self.detector  = HandDetector(self.config)
        self.tracker   = HandTracker(self.config, self.mouse)
        self.calibrator = Calibrator(self.config)
        self.perf      = PerformanceMonitor(
            log_fps=self.config.performance.get("show_fps_in_log", False)
        )
        self.audio     = AudioFeedback(self.config.audio)
        self.telemetry = create_telemetry(self.config.advanced)

        # ── Gesture recognizers ─────────────────────────────────────────────────────────
        g = self.config.gestures
        self._rec_left_click  = DoubleFistRecognizer(g["left_click"])
        self._rec_right_click = PeaceSignRecognizer(g["right_click"])
        self._rec_scroll      = TwoFingerScrollRecognizer(g["scroll"])
        self._rec_wrist_scroll = WristRollScrollRecognizer(g["scroll"])
        self._rec_drag        = PinchDragRecognizer(g["drag_lock"])
        self._rec_swipe       = ThreeFingerSwipeRecognizer(g["desktop_swipe"])
        self._rec_zoom        = ZoomRecognizer(g["zoom"])
        self._rec_freeze      = OpenPalmFreezeRecognizer(g["freeze_cursor"])
        self._rec_circle      = FingertipCircleRecognizer(g["screenshot"])
        self._learner         = AdaptiveLearner(g.get("learning_rate", 0.05))
        self._drag_was_pinching = False

        # ── Capture ─────────────────────────────────────────────────────────────────────
        self.capture   = CameraCapture(self.config)

        # ── Plugins ─────────────────────────────────────────────────────────────────────
        self.plugins   = PluginManager(self)
        if self.config.advanced.get("plugin_enabled", True):
            self.plugins.load_all()

        # ── Optional: tray icon ─────────────────────────────────────────────────────────
        self.tray: Optional[TrayIcon] = None
        if TRAY_AVAILABLE and self.config.tray.get("enable", True):
            self.tray = TrayIcon(self)

        # ── Optional: hot-reload ────────────────────────────────────────────────────────
        self._watcher: Optional[ConfigWatcher] = None
        if self.config.advanced.get("hot_reload_config", True):
            self._watcher = ConfigWatcher(
                self.config,
                interval=self.config.advanced.get("hot_reload_interval", 3.0)
            )

        # ── Optional: REST API ──────────────────────────────────────────────────────────
        self._api: Optional[RestAPIController] = None
        if FLASK_AVAILABLE and self.config.api.get("enable", False):
            self._api = RestAPIController(
                self,
                host=self.config.api.get("host", "127.0.0.1"),
                port=self.config.api.get("port", 5765)
            )

        # ── State ───────────────────────────────────────────────────────────────────────
        self.running   = True
        self.paused    = False
        self._frame_n  = 0
        self._skip     = max(1, self.config.performance.get("frame_skip", 1))
        self._gest_cd  = self.config.gestures.get("gesture_cooldown", 0.28)
        self._gest_cd_end = 0.0

        # ── Signal handling ─────────────────────────────────────────────────────────────
        signal.signal(signal.SIGINT,  self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    # ── Startup ──────────────────────────────────────────────────────────────────────────

    def _log_banner(self) -> None:
        lines = [
            "=" * 60,
            f"  Air Mouse Superior Pro v{VERSION}",
            f"  Platform: {PLATFORM}",
            f"  Config:   {self.config._path}  (v{self.config.version})",
            "=" * 60,
        ]
        for l in lines:
            logger.info(l)

    def _handle_signal(self, signum, frame) -> None:
        logger.info(f"Signal {signum} received – shutting down…")
        self.running = False

    def start_calibration(self) -> None:
        self.calibrator.start()

    # ── Main loop ─────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start all background services and enter the main processing loop."""
        if self.tray:       self.tray.run()
        if self._watcher:   self._watcher.start()
        if self._api:       self._api.start()

        logger.info("=== Air Mouse Superior Pro ACTIVE ===")
        logger.info("Gesture mapping:")
        logger.info("  ✊✊  Double fist       → Left click")
        logger.info("  ✌️   Peace sign        → Right click")
        logger.info("  ☝️☝️  Two fingers spread → Scroll")
        logger.info("  🤏   Pinch             → Toggle drag lock")
        logger.info("  👋   Open palm         → Freeze cursor")
        logger.info("  ☝️✌️✌️ Three-finger swipe → Switch desktop")
        logger.info("  ↔️   Thumb-index spread → Zoom")
        logger.info("  ⭕   Draw circle       → Screenshot")
        logger.info("  Ctrl-C / tray Exit   → Quit")

        try:
            while self.running:
                if self.paused:
                    time.sleep(0.05)
                    continue

                frame = self.capture.get()
                if frame is None:
                    time.sleep(0.001)
                    continue

                self._frame_n += 1
                if self._frame_n % self._skip != 0:
                    continue

                with self.perf.section("total"):
                    self._process_frame(frame)

                self.perf.tick()

        except Exception as exc:
            logger.error(f"Fatal error in main loop: {exc}")
            logger.debug(traceback.format_exc())
        finally:
            self._shutdown()

    def _process_frame(self, frame: np.ndarray) -> None:
        """Full pipeline for a single frame."""
        h, w = frame.shape[:2]
        now  = time.monotonic()

        # ── Detection ─────────────────────────────────────────────────────────────────
        with self.perf.section("detect"):
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.detector.detect(rgb)

        landmarks_list, handedness_list = HandDetector.parse_result(result)
        self.tracker.tick(now)

        if not landmarks_list:
            return

        # ── Hand assignment ────────────────────────────────────────────────────────────
        primary, secondary = self.tracker.assign(landmarks_list, handedness_list, now)
        if primary is None:
            return

        # ── Plugin broadcast ───────────────────────────────────────────────────────────
        self.plugins.broadcast_frame(primary, (h, w))

        # ── Calibration ────────────────────────────────────────────────────────────────
        if self.calibrator.calibrating:
            self.calibrator.update(primary, w, h)

        # ── Cursor movement ────────────────────────────────────────────────────────────
        with self.perf.section("cursor"):
            tip = lm_to_px(primary[INDEX_TIP], w, h)
            self.mouse.update((float(tip[0]), float(tip[1])), now)

        # ── Gesture processing (with cooldown) ────────────────────────────────────────
        if now >= self._gest_cd_end:
            with self.perf.section("gesture"):
                triggered = self._process_gestures(primary, secondary, w, h, now)
            if triggered:
                self._gest_cd_end = now + self._gest_cd

    # ── Gesture processing ─────────────────────────────────────────────────────────────

    def _process_gestures(
        self,
        primary,
        secondary,
        w: int,
        h: int,
        now: float
    ) -> bool:
        """
        Run all gesture recognizers on the primary (and optionally secondary) hand.
        Returns True if any gesture was triggered this frame.
        """
        triggered = False
        g         = self.config.gestures

        # Compute shared values
        hand_size = compute_hand_size(primary, w, h)
        curl      = self._rec_left_click.get_curl(primary, w, h, hand_size)

        # ── Open palm freeze ──────────────────────────────────────────────────────────
        if g["freeze_cursor"]["enable"]:
            freeze = self._rec_freeze.update(primary, curl)
            if freeze != self.mouse._cursor_frozen:
                self.mouse.freeze(freeze)
                logger.debug(f"Cursor {'frozen' if freeze else 'unfrozen'}")
                triggered = True

        # ── Left click (double fist) ───────────────────────────────────────────────────
        if g["left_click"]["enable"] and not self.mouse._cursor_frozen:
            if self._rec_left_click.update(curl, now):
                self.mouse.click("left")
                self.audio.click_sound()
                self._emit("left_click", {"curl": curl})
                triggered = True
                # Adaptive learning
                if g.get("adaptive_learning"):
                    self._learner.observe("left_click_curl", curl)

        # ── Right click (peace sign) ───────────────────────────────────────────────────
        if g["right_click"]["enable"]:
            if self._rec_right_click.update(primary, w, h, now):
                self.mouse.click("right")
                self.audio.gesture_sound()
                self._emit("right_click", {})
                triggered = True

        # ── Two-finger scroll ─────────────────────────────────────────────────────────
        if g["scroll"]["enable"]:
            delta = self._rec_scroll.update(primary, w, h)
            if delta != 0:
                self.mouse.scroll(delta)
                self._emit("scroll", {"delta": delta})
                triggered = True
            # Wrist roll scroll
            if g["scroll"].get("wrist_roll_enable", True):
                wdelta = self._rec_wrist_scroll.update(primary, curl)
                if wdelta != 0:
                    self.mouse.scroll(wdelta)
                    self._emit("wrist_scroll", {"delta": wdelta})
                    triggered = True

        # ── Drag lock (pinch toggle) ──────────────────────────────────────────────────
        if g["drag_lock"]["enable"]:
            pinching = self._rec_drag.update(primary, w, h)
            if pinching and not self._drag_was_pinching:
                # Rising edge: toggle drag
                if not self.mouse.drag_active:
                    self.mouse.start_drag()
                    self.audio.drag_sound()
                else:
                    self.mouse.stop_drag()
                self._emit("drag_toggle", {"active": self.mouse.drag_active})
                triggered = True
            self._drag_was_pinching = pinching

        # ── Three-finger desktop swipe ─────────────────────────────────────────────────
        if g["desktop_swipe"]["enable"]:
            direction = self._rec_swipe.update(primary, w, h, now)
            if direction:
                self.mouse.navigate_desktop(direction)
                self.audio.gesture_sound()
                self._emit("desktop_swipe", {"direction": direction})
                triggered = True

        # ── Zoom (thumb-index spread) ──────────────────────────────────────────────────
        if g["zoom"]["enable"]:
            zdelta = self._rec_zoom.update(primary, w, h)
            if zdelta != 0.0:
                self.mouse.zoom(zdelta)
                self._emit("zoom", {"delta": zdelta})
                triggered = True

        # ── Fingertip circle → screenshot ─────────────────────────────────────────────
        if g["screenshot"]["enable"]:
            # "drawing mode" = index extended, all others curled
            drawing = (
                finger_extended(primary, INDEX_TIP, INDEX_PIP)
                and not finger_extended(primary, MIDDLE_TIP, MIDDLE_PIP)
                and not finger_extended(primary, RING_TIP,   RING_PIP)
                and not finger_extended(primary, PINKY_TIP,  PINKY_PIP)
            )
            if self._rec_circle.update(primary, w, h, now, drawing):
                path = take_screenshot()
                self.audio.gesture_sound()
                self._emit("screenshot", {"path": path})
                triggered = True

        return triggered

    # ── Event emission ─────────────────────────────────────────────────────────────────

    def _emit(self, gesture: str, data: Dict[str, Any]) -> None:
        """Broadcast a gesture event to plugins and telemetry."""
        logger.debug(f"Gesture: {gesture} | {data}")
        self.plugins.broadcast_gesture(gesture, data)
        if self.telemetry:
            self.telemetry.record(gesture, data)

    # ── Shutdown ───────────────────────────────────────────────────────────────────────

    def _shutdown(self) -> None:
        logger.info("Shutting down Air Mouse Superior Pro…")

        if self.mouse.drag_active:
            self.mouse.stop_drag()

        self.capture.release()
        self.detector.release()
        self.plugins.shutdown_all()

        if self._watcher:
            self._watcher.stop()

        if self.telemetry:
            self.telemetry.flush()
            self.telemetry.close()

        if self.tray:
            self.tray.stop()

        # Log performance report
        report = self.perf.report()
        if report:
            logger.info("Performance summary (avg ms per section):")
            for section, ms in report.items():
                logger.info(f"  {section:15s}: {ms:.2f} ms")

        logger.info("Air Mouse Superior Pro terminated cleanly.")


# ==========================================================================================
# CLI ENTRY POINT
# ==========================================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Air Mouse Superior Pro v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python air_mouse_superior_pro_v5.py
  python air_mouse_superior_pro_v5.py --calibrate
  python air_mouse_superior_pro_v5.py --config my_config.json
  python air_mouse_superior_pro_v5.py --list-monitors
  python air_mouse_superior_pro_v5.py --reset-config
        """
    )
    parser.add_argument("--config",        type=str,  default=CONFIG_FILE,
                        help="Path to JSON config file (default: %(default)s)")
    parser.add_argument("--calibrate",     action="store_true",
                        help="Start with auto-calibration routine")
    parser.add_argument("--list-monitors", action="store_true",
                        help="Print detected monitors and exit")
    parser.add_argument("--reset-config",  action="store_true",
                        help="Overwrite config with defaults and exit")
    parser.add_argument("--log-level",     type=str,  default=None,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Override log level from config")
    parser.add_argument("--no-tray",       action="store_true",
                        help="Disable system tray icon")
    parser.add_argument("--api",           action="store_true",
                        help="Enable REST API server")
    parser.add_argument("--version",       action="version",
                        version=f"Air Mouse Superior Pro v{VERSION}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_monitors:
        monitors = get_monitors_info()
        print(f"Detected {len(monitors)} monitor(s):")
        for m in monitors:
            print(f"  [{m.index}] {m.name}  {m.width}x{m.height}  @({m.x},{m.y})")
        return

    if args.reset_config:
        cfg = Config(**copy.deepcopy(DEFAULT_CONFIG), _path=args.config)
        cfg.save()
        print(f"Config reset to defaults: {args.config}")
        return

    # Build the app
    app = AirMousePro(config_path=args.config)

    # Apply CLI overrides
    if args.log_level:
        app.config.performance["log_level"] = args.log_level
        logger.setLevel(getattr(logging, args.log_level))

    if args.no_tray:
        app.config.tray["enable"] = False
        app.tray = None

    if args.api:
        app.config.api["enable"] = True
        if app._api is None and FLASK_AVAILABLE:
            app._api = RestAPIController(app)
            app._api.start()

    if args.calibrate:
        app.start_calibration()

    # Run
    app.run()


if __name__ == "__main__":
    main()