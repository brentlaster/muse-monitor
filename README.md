# NeuroFocus — Muse S EEG Focus Monitor

A real-time brain-computer interface that connects to the **Muse S (Athena)** EEG headband via Bluetooth Low Energy and provides live focus monitoring, ambient audio neurofeedback, a native macOS desktop overlay, timed focus goals, and session recording — all from a single HTML file in your browser with companion Python scripts.

## What It Does

NeuroFocus reads raw EEG data from your Muse S headband, processes it through a research-grade signal pipeline, and gives you a real-time **focus score (0–100)** based on your brain's electrical activity.

### Dashboard
- **Live focus gauge** with Deep Focus / Moderate / Distracted states
- **EEG waveform display** — all 4 channels (TP9, AF7, AF8, TP10)
- **Band power visualization** (Delta, Theta, Alpha, Beta, Gamma) with customizable target presets
- **Focus history timeline** with colored zone indicators
- **Zone time tracking** — time and percentage in each focus zone (deep/moderate/distracted)
- **Session history** — persisted across sessions, exportable to CSV

### Feedback & Alerts
- **Drift alerts** — visual flash, audio ding, and widget notification when focus drops
- **Ambient audio neurofeedback** — 5 generative styles (handpan, forest, zen, ambient, solfeggio) with density that responds to focus level
- **Desktop widget** — color-only orb (or text mode) that stays visible when the app is minimized
- **Native macOS window overlay** — glowing colored border around your active app window reflecting focus level in real-time

### Calibration & Accuracy
- **Voice-guided 2-minute baseline calibration** — spoken instructions with configurable voice
- **Individual Alpha Frequency (IAF) detection** — adapts band boundaries to your brain
- **Frontal channel weighting** — AF7/AF8 weighted 2.5× over TP9/TP10
- **Calibration persisted** across sessions via localStorage
- **Pause button** — suspend all tracking when you take the headband off

### Recording & Analysis
- **Session recording** to CSV with band powers, focus state, and active macOS app
- **Session history** — automatically saved, browsable, and exportable
- **Active app tracking** — correlate focus with which app you're using

## Requirements

- **Muse S (Athena)** headband — the newer model with Athena RevE/F hardware
- **Google Chrome** on macOS (Web Bluetooth API required)
- **Python 3** (included with macOS)
- **PyObjC** (optional, for desktop overlay): `pip3 install pyobjc-framework-Cocoa pyobjc-framework-Quartz`

> **Note:** Safari and Firefox do not support Web Bluetooth. The app must be served via `localhost`, not opened as a `file://` URL.

## Quick Start

```bash
# One-command startup (starts server, overlay, and opens Chrome):
./start.sh

# To stop everything:
./start.sh --stop
```

Or start components individually:

```bash
# Terminal 1: Server
python3 neurofocus-server.py

# Terminal 2: Desktop overlay (optional, requires PyObjC)
python3 neurofocus-overlay.py

# Open in Chrome:
open -a "Google Chrome" http://localhost:8000/muse-focus-monitor.html
```

Then: Turn on your Muse S → Click "Connect" → Select your Muse → Put on the headband → Wait ~10 seconds for signal.

## Files

| File | Purpose |
|------|---------|
| `muse-focus-monitor.html` | The complete app — single file, no dependencies |
| `neurofocus-server.py` | HTTP server with active app and window bounds detection |
| `neurofocus-overlay.py` | Native macOS overlay — glowing border around active window |
| `neurofocus-diag.py` | Diagnostic tool — 5-second delay window bounds check |
| `start.sh` | One-command launcher — starts/stops all components |
| `README.md` | This file |
| `INSTRUCTIONS.md` | Comprehensive usage guide (22 sections) |

## Signal Processing Pipeline

1. **14-bit LSB-first decoding** — Muse S Athena packet format (verified against OpenMuse)
2. **DC offset removal** — centers raw 0–1450µV signal around zero
3. **4th-order Butterworth IIR bandpass** — 1–50 Hz (flat within 0.75 dB across 2–30 Hz)
4. **60 Hz notch filter** — removes US power line interference
5. **Artifact rejection** — detects and removes eye blinks (>150µV p-p) and jaw clenches
6. **Welch's method PSD** — averaged overlapping 128-sample FFT segments for stable spectral estimates
7. **Individual Alpha Frequency detection** — adapts band boundaries to your personal alpha peak
8. **Frontal channel weighting** — AF7/AF8 weighted 2.5× over TP9/TP10 for attention relevance
9. **Composite focus metric** — weighted blend of 4 research-validated engagement indices
10. **Auto-calibrating percentile scoring** with EMA temporal smoothing (or manual baseline)

## Architecture

```
┌─────────────┐  BLE notify   ┌─────────────┐  POST /focus-score  ┌──────────────┐
│  Muse S     │ ────────────→ │   Chrome     │ ──────────────────→ │    Server    │
│  Headband   │               │  (HTML app)  │    every ~1sec      │  (port 8000) │
└─────────────┘               │              │                     │              │
                              │ GET /active-app                    │ osascript    │
                              │ ←──────────── │                    │ queries      │
                              └─────────────┘                     └──────┬───────┘
                                                                         │
                              ┌─────────────┐  GET /focus-score          │
                              │   Overlay    │ ←─────────────────────────┤
                              │  (PyObjC)   │  GET /active-window       │
                              │             │ ←─────────────────────────┘
                              └─────────────┘
                              Draws glow around active window
```

## Credits

- **Muse S BLE protocol**: Based on [amused-py](https://github.com/Amused-EEG/amused-py) by Adrian Tadeusz Belmans
- **Packet decoder**: Verified against [OpenMuse](https://github.com/DominiqueMakowski/OpenMuse) by Dominique Makowski
- **Focus metrics**: Based on Pope et al. (1995) engagement index and Monastra et al. (2005) attention index

## License

This project is for personal and educational use. The Muse S is a product of InteraXon Inc. This project is not affiliated with or endorsed by InteraXon.
