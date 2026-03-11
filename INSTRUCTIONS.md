# NeuroFocus — Detailed Instructions

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Installation & Setup](#2-installation--setup)
3. [Connecting Your Muse S](#3-connecting-your-muse-s)
4. [Understanding the Dashboard](#4-understanding-the-dashboard)
5. [Signal Quality & Headband Fit](#5-signal-quality--headband-fit)
6. [Baseline Calibration](#6-baseline-calibration)
7. [Focus Scoring — How It Works](#7-focus-scoring--how-it-works)
8. [Band Power & Targets](#8-band-power--targets)
9. [Focus History Chart](#9-focus-history-chart)
10. [Drift Alerts](#10-drift-alerts)
11. [Audio Feedback](#11-audio-feedback)
12. [Focus Goals](#12-focus-goals)
13. [Desktop Widget](#13-desktop-widget)
14. [Mini Mode](#14-mini-mode)
15. [Recording Sessions](#15-recording-sessions)
16. [Active App Tracking](#16-active-app-tracking)
17. [Pause](#17-pause)
18. [Focus Glow Overlay](#18-focus-glow-overlay-desktop)
19. [Settings Reference](#19-settings-reference)
20. [Demo Mode](#20-demo-mode)
21. [Startup Script](#21-startup-script)
22. [Diagnostics](#22-diagnostics)
23. [Connection Log & Troubleshooting](#23-connection-log--troubleshooting)
24. [Technical Details](#24-technical-details)
25. [Known Limitations](#25-known-limitations)

---

## 1. System Requirements

**Hardware:**
- Muse S (Athena) headband — model with Athena RevE/F hardware, firmware 3.x
- Mac computer with Bluetooth (tested on macOS)
- The older Muse 2 uses a different BLE protocol and is **not currently supported**

**Software:**
- Google Chrome browser (required for Web Bluetooth API)
- Python 3 (pre-installed on macOS)
- No additional packages, libraries, or installations needed

**Browser restrictions:**
- Safari and Firefox do **not** support Web Bluetooth
- The page **must** be served via `http://localhost` — opening the HTML file directly (`file://`) will cause Web Bluetooth to silently fail
- Chrome may need popup permissions enabled for the widget feature

---

## 2. Installation & Setup

### Quick Start (recommended)

```bash
# Make start script executable (one time only)
chmod +x start.sh

# Start everything — kills old instances, starts server + overlay, opens Chrome
./start.sh

# To stop everything
./start.sh --stop
```

### Manual Setup (without start.sh)

1. Download both files into the same folder:
   - `muse-focus-monitor.html`
   - `neurofocus-server.py`

2. Open Terminal (Applications → Utilities → Terminal)

3. Navigate to the folder containing the files:
   ```bash
   cd ~/Downloads
   ```
   (Replace with your actual folder path)

4. Start the server:
   ```bash
   python3 neurofocus-server.py
   ```

5. You should see:
   ```
   ╔══════════════════════════════════════════════════╗
   ║           NeuroFocus Server v1.0                 ║
   ║                                                  ║
   ║  Open in Chrome:                                 ║
   ║  http://localhost:8000/muse-focus-monitor.html   ║
   ║                                                  ║
   ║  Active app detection: enabled                   ║
   ║  Press Ctrl+C to stop                            ║
   ╚══════════════════════════════════════════════════╝
   ```

6. Open Chrome and navigate to: `http://localhost:8000/muse-focus-monitor.html`

### Alternative Setup (without app tracking)

If you don't need active app tracking, you can use Python's built-in server:

```bash
cd ~/Downloads
python3 -m http.server 8000
```

Then open `http://localhost:8000/muse-focus-monitor.html` in Chrome. Everything works except the "Track app" feature.

### Stopping the Server

Press `Ctrl+C` in the Terminal window to stop the server.

---

## 3. Connecting Your Muse S

1. **Turn on your Muse S** — press the button until the lights pulse

2. **Click "Connect"** in the top-right corner of the app

3. **Chrome will show a Bluetooth picker** — select your device (e.g., "MuseS-F760")

4. **Wait for the connection sequence** — the Connection Log (click to expand) will show:
   - GATT connection
   - Service discovery
   - Characteristic subscription
   - Preset selection (`p1035`)
   - Stream start (`dc001` sent twice — required for Muse S)

5. **Put on the headband** and wait approximately 10 seconds for signals to settle

6. **The signal quality indicator** below the focus gauge will show:
   - `4/4 channels OK` — all sensors making good contact
   - `2/4 channels — tp9: noisy...` — some sensors need adjustment
   - `0/4 channels — noisy (no contact?)` — headband not on or poor fit

### Connection Protocol Details

The Muse S Athena uses a different protocol than documented for older Muse models:

- **Preset:** `p1035` (full sensor mode — EEG + PPG + IMU)
- **Start command:** `dc001` (must be sent **twice** — this is critical and undocumented)
- **Packet format:** Large multiplexed packets (200+ bytes) with 14-byte headers
- **EEG encoding:** 14-bit LSB-first packed values, 4 channels × 4 samples per EEG subpacket
- **Scale factor:** `1450.0 / 16383.0 ≈ 0.0885 µV/LSB`

---

## 4. Understanding the Dashboard

### Focus Gauge (top)
The large semicircular gauge shows your current focus score:
- **70–100 (green): Deep Focus** — sustained concentration, high beta activity
- **40–69 (yellow): Moderate** — partially engaged, mixed brain states
- **0–39 (red): Distracted** — low engagement, high alpha/theta

Below the gauge: signal quality indicator and current state badge.

### EEG Waveform
Raw filtered EEG from all 4 channels displayed as scrolling waveforms:
- **Cyan (TP9):** Left ear
- **Purple (AF7):** Left forehead
- **Pink (AF8):** Right forehead
- **Green (TP10):** Right ear

### Band Power
Horizontal bars showing relative power in each frequency band:
- **Delta (1–4 Hz):** Deep sleep, unconscious processing
- **Theta (4–8 Hz):** Drowsiness, daydreaming, creative thinking
- **Alpha (8–13 Hz):** Relaxed wakefulness, eyes closed
- **Beta (13–30 Hz):** Active thinking, focus, concentration
- **Gamma (30–50 Hz):** Higher cognitive processing

Diamond markers (◆) show your target values for each band.

> **Note:** When Individual Alpha Frequency (IAF) is detected, band boundaries automatically adjust to your personal alpha peak. For example, if your IAF is 9.5 Hz, alpha becomes 7.5–11.5 Hz instead of the standard 8–13 Hz.

### Session Stats
- **Avg Focus:** Running average for the session
- **Peak Focus:** Highest score achieved
- **Session Time:** Duration since connection
- **Drift Alerts:** Number of times focus dropped below threshold

### Zone Time Breakdown

Below the session stats, a colored bar and time breakdown show how much time you've spent in each focus zone:

- **Deep Focus (green):** Score ≥70 — time and percentage
- **Moderate (yellow):** Score 40–69 — time and percentage
- **Distracted (red):** Score <40 — time and percentage

The colored bar provides a visual ratio at a glance. Percentages are based on active signal time only — no-signal periods are excluded from the calculation.

### Active App (when enabled)
Shows which macOS application is currently in the foreground. Requires `neurofocus-server.py`.

### Session History (persisted)

Click **"Session History"** to expand a table of all past sessions. Each row shows:

| Column | Description |
|--------|-------------|
| Date | When the session started |
| Dur | Session duration |
| Avg | Average focus score |
| Peak | Highest focus score |
| Deep % | Percentage of time in Deep Focus |
| Mod % | Percentage of time in Moderate |
| Dist % | Percentage of time Distracted |
| Drifts | Number of drift alerts |

Sessions are **automatically saved** when you disconnect, close the page, or refresh the browser. Up to 100 sessions are retained. Demo sessions are shown dimmed with a "(demo)" label.

**Export CSV:** Downloads all session history as a CSV file for analysis in a spreadsheet.

**Clear History:** Permanently deletes all saved session data.

### Persisted Calibration

When you complete a baseline calibration, the results (baseline, range, and IAF) are **automatically saved** to your browser's local storage. The next time you connect — even after closing and reopening the page — your calibration is restored automatically. You'll see:

```
Restored calibration (3/10/2026) baseline=0.45 range=1.37
```

This means you don't need to recalibrate every session unless you want to. The "Recalibrate" button is always available if you want fresh calibration data.

---

## 5. Signal Quality & Headband Fit

### What good signal looks like

The Connection Log shows per-channel diagnostics:

```
tp9:  rms=68.5µV ok (std=68.5µV, mean=735µV)
af7:  rms=29.3µV ok (std=29.3µV, mean=732µV)
af8:  rms=41.7µV ok (std=41.7µV, mean=730µV)
tp10: rms=65.0µV ok (std=65.0µV, mean=736µV)
```

- **std (standard deviation):** Should be 5–150 µV. This represents the AC fluctuation of your EEG.
- **mean:** Should be 400–1000 µV (midrange of the 0–1450 µV ADC range). This is the DC offset.

### What bad signal looks like

| Problem | Symptoms | Fix |
|---------|----------|-----|
| No contact | `std=500+µV, noisy` | Adjust headband position |
| Railed sensor | `mean<100µV` or `mean>1350µV` | Clean sensor, re-seat |
| Flat signal | `std<1µV` | Sensor may be damaged |
| Too many artifacts | `>50% artifacts` | Stop moving, relax jaw |

### Headband fit tips

1. **Forehead sensors (AF7/AF8):** Must sit flat against skin with no hair between sensor and forehead. These are the most important sensors for focus detection.
2. **Ear sensors (TP9/TP10):** Rest snugly behind the ears. They're naturally noisier than forehead sensors.
3. **Give it 10–30 seconds** after putting on for signals to settle — dry electrodes need time to establish good contact.
4. **Minimize movement** — head movement, jaw clenching, and eye blinks create artifacts. The app rejects the worst of these, but excessive movement degrades accuracy.

---

## 6. Baseline Calibration

### Why calibrate?

Without calibration, the app uses auto-calibration (adapts to your percentile range over time). This works, but doesn't know what "relaxed" vs "focused" specifically looks like for your brain. A guided baseline gives it ground truth.

### Choosing a calibration voice

The calibration is fully voice-guided so you can close your eyes during the relaxation phase. A **Voice** dropdown and **Test** button appear in the calibration panel.

Chrome provides system voices via the Web Speech API. The quality varies dramatically:

| Tier | Example | Sound quality |
|------|---------|--------------|
| ★★★ Premium | Ava (Premium), Zoe (Premium) | Near-human, natural inflection |
| ★★ Enhanced | Samantha (Enhanced), Karen (Enhanced) | Good quality, slight synth |
| ★ Google | Google US English Female | Decent, a bit flat |
| (none) | Samantha, Alex | Basic, robotic |

**To get the best voices (free, one-time download on macOS):**

1. Open **System Settings** → **Accessibility** → **Spoken Content**
2. Click **System Voice** → **Manage Voices**
3. Download **Ava (Premium)** or **Zoe (Premium)** under English
4. Close System Settings and **reload the NeuroFocus page**
5. The new voice will appear in the dropdown with ★★★

The premium voices are ~300–500 MB downloads but sound dramatically better — warm, natural, and genuinely calming. The app auto-selects the highest-quality available voice, but you can choose any voice from the dropdown.

Use the **Test** button to preview: *"Take a slow, deep breath in. And gently breathe out. Allow yourself to relax completely."*

### How to calibrate

1. Connect your Muse S and verify signal quality (2+ channels OK)
2. Find the **Baseline Calibration** section on the dashboard
3. Click **"Calibrate (2 min)"**
4. **The app will speak all instructions** — you can close your eyes immediately

**Phase 1 — Relaxation (60 seconds):**
   - Voice: *"Close your eyes. Breathe slowly and deeply. Try to relax completely."*
   - At 15s: *"Keep your eyes closed. Relax your jaw. Let go of any tension."*
   - At 30s: *"Halfway through the relaxation phase. 30 seconds remaining."*
   - At 50s: *"10 seconds left. Get ready to focus."*
   - At 57s: *"3. 2. 1."*

**Phase 2 — Focus (60 seconds):**
   - Voice: *"Open your eyes. Count backwards from 300 by sevens. 300. 293. 286. 279. Keep going."*
   - At 75s: *"Keep counting. Stay focused."*
   - At 90s: *"Halfway through the focus phase. 30 seconds remaining."*
   - At 110s: *"Almost done. 10 seconds left."*
   - At 117s: *"3. 2. 1."*

**Completion:**
   - Voice: *"Calibration complete. Your personal baseline has been set."*
   - If IAF was detected: *"Your individual alpha frequency is [X] hertz."*

### Calibration results

After calibration, the status line shows something like:
```
Calibrated! Relaxed=0.45 Focused=1.82 (range=1.37)
```

This means your personal engagement ratio ranges from 0.45 (relaxed) to 1.82 (focused), and the scoring system now maps that range to 0–100.

### When to recalibrate

Your calibration is automatically saved and restored across sessions. You only need to recalibrate if:

- After taking a long break
- If you feel the readings don't match your subjective state
- After moving/adjusting the headband
- At the start of each session for best accuracy (optional but recommended)

### If calibration fails

- **"Range too narrow"** — your relaxed and focused states produced similar readings. This can happen if you weren't truly relaxed during phase 1, or weren't mentally engaged during phase 2. Try again.
- **"Insufficient data"** — signal quality was poor during calibration. Fix headband fit first.

---

## 7. Focus Scoring — How It Works

### The composite metric

Focus is not measured by a single number — the app combines four research-validated indices:

| Metric | Weight | What it measures | Reference |
|--------|--------|------------------|-----------|
| Beta / (Alpha + Theta) | 40% | Cognitive engagement | Pope et al., 1995 |
| Beta / Theta | 25% | Sustained attention | Monastra et al., 2005 |
| Relative Beta Power | 20% | Proportion of active thinking | Standard neurofeedback |
| Alpha / Theta | 15% | Alertness vs. drowsiness | Standard neurofeedback |

### Scoring pipeline

1. The composite metric produces a raw engagement value
2. **Auto-calibration** (or manual baseline) maps this to a 0–100 percentile score relative to your personal range
3. **EMA smoothing** (α=0.2) prevents jittery jumps — the score responds to real trends over ~5 readings rather than reacting to every single sample
4. The smoothed score maps to focus states: 0–39 Distracted, 40–69 Moderate, 70–100 Deep Focus

### Frontal channel weighting

The forehead sensors (AF7, AF8) are weighted **2.5×** more heavily than the ear sensors (TP9, TP10) because the prefrontal cortex is where executive attention and focus control happens. The temporal regions picked up by ear sensors are more associated with auditory processing.

### Individual Alpha Frequency (IAF)

Everyone's dominant alpha rhythm has a slightly different peak frequency (typically 8.5–11.5 Hz). The app automatically detects your personal IAF by finding the spectral peak in the 7–13 Hz range from the frontal channels.

Once detected with sufficient confidence, the standard band boundaries shift:
- **Standard:** Delta 1–4, Theta 4–8, Alpha 8–13, Beta 13–30 Hz
- **IAF-adjusted (example, IAF=9.5Hz):** Delta 1–3.5, Theta 3.5–7.5, Alpha 7.5–11.5, Beta 11.5–30 Hz

This prevents power from adjacent bands bleeding into each other and gives more accurate engagement ratios.

The IAF detection runs continuously and displays below the calibration section: `Your alpha frequency: 10.2 Hz (confidence 85%)`

---

## 8. Band Power & Targets

### Band target presets

The dropdown in the Band Targets section provides research-informed starting points:

| Preset | Delta | Theta | Alpha | Beta | Gamma | Use case |
|--------|-------|-------|-------|------|-------|----------|
| Deep Focus | 15% | 20% | 25% | 55% | 15% | Sustained concentration, coding, writing |
| Creative Flow | 15% | 40% | 35% | 30% | 10% | Brainstorming, art, open-ended thinking |
| Relaxed Alert | 20% | 25% | 50% | 20% | 10% | Calm attention, reading, listening |
| Meditation | 25% | 45% | 40% | 15% | 8% | Deep meditative states |
| Active Learning | 15% | 30% | 30% | 45% | 20% | Studying, encoding new information |
| Custom | — | — | — | — | — | Set your own values |

The diamond markers (◆) on each band bar show your target. Adjust the numeric inputs to fine-tune.

---

## 9. Focus History Chart

The scrolling 2-minute chart shows your focus score over time with:

- **Green zone (above 70%):** Deep Focus region
- **Yellow zone (40–70%):** Moderate region
- **Red zone (below 40%):** Distracted region
- **Dashed red line:** Your alert threshold setting
- **Red tick marks:** Periods with no valid signal

The line breaks when signal is lost and resumes when it returns.

---

## 10. Drift Alerts

When your focus drops below a threshold for a sustained period, the app alerts you:

- **Visual:** Red banner at top of screen + red overlay flash
- **Audio:** Alert tone (can be muted via the Sound toggle in Settings)
- **Widget:** "⚠ refocus" message with red background tint

### Settings

- **Alert below:** Focus score threshold (default: 30%)
- **for:** Seconds of sustained low focus before alerting (default: 5 seconds)
- **Alerts:** Master on/off toggle
- **Sound:** Mute/unmute the alert pong independently

Alerts clear automatically when focus returns above the threshold.

---

## 11. Audio Feedback

### How it works

The audio system plays **discrete musical notes** (not continuous tones) at intervals that vary with your focus level. Higher focus produces richer, denser soundscapes; lower focus produces sparse, isolated tones.

| Focus Level | Notes per event | Interval | Character |
|-------------|----------------|----------|-----------|
| Deep Focus (70+) | 3–5 simultaneous | 2–3.5 sec | Rich, layered, with ghost notes |
| Moderate (40–69) | 1–2 | 3–5 sec | Occasional harmony |
| Distracted (0–39) | 1 single note | 4–7 sec | Isolated, lower register |

### Styles

**Handpan (D minor):** Percussive steel tongue drum tones with harmonics and long ring. Focused = cascading strikes with ghost echoes. Distracted = single deep resonant strikes.

**Forest birds:** Short chirps with pitch bends mimicking birdsong. Focused = busy canopy with call-and-response patterns. Distracted = lone dove calls.

**Ambient pads:** Slow-swelling detuned sine pairs creating a shimmering wash. Long 5-second sustains that overlap. Focused = layered chords. Distracted = isolated low drone.

**Zen bells:** Sharp attack with inharmonic bell partials (like a temple bell). Clean ring fading over 4 seconds. Focused = overlapping bells. Distracted = single distant bell.

**Solfeggio frequencies:** The 9 solfeggio tones (174–963 Hz). Focused biases toward higher frequencies (741 Hz awakening, 852 Hz spiritual order, 963 Hz divine consciousness). Distracted stays in grounding range (174 Hz, 285 Hz, 396 Hz). Status display shows which frequency is playing.

### Controls

- **Ambient tone toggle:** On/off (Chrome requires a user gesture to start audio)
- **Style selector:** Choose your preferred soundscape
- **Volume slider:** 0–100%
- **Status indicator:** Shows current state (Focused ▲ / Moderate ● / Low ▼) or the active solfeggio frequency

Audio fades out automatically on disconnect.

---

## 12. Focus Goals

### Setting a goal

1. **Target:** Choose Deep Focus (70+), Moderate (40+), or Custom
2. **Duration:** Set in minutes (1–240)
3. Click **"Start Goal"**

### During a goal

The goal panel shows:
- **Progress bar** — fills over the duration, colored by performance (green/yellow/red)
- **Time remaining** — countdown timer
- **Average focus** — running mean during the goal period
- **Time in zone** — percentage of time you've been at or above the target

### Goal completion report

When the timer ends (or you stop early), a report overlay appears with:
- **Letter grade:** A+ (≥90% in zone) through F (<40% in zone)
- **Duration, average focus, peak focus**
- **Time in zone percentage**
- **Total samples collected**

A completion chime plays if sound is enabled.

Goals only count samples with valid signal — no-signal periods are excluded.

---

## 13. Desktop Widget

### Opening the widget

Click **"Widget"** in the header bar. A small popup window (~180×220 pixels) opens.

### Color-only mode (default)

By default, the widget shows **only a colored orb with no text** — a minimal ambient indicator. The orb uses a smooth color gradient with ~20 distinguishable colors:

| Score Range | Orb Color |
|-------------|-----------|
| 0–15 | Deep red |
| 20–35 | Red-orange |
| 40–50 | Orange-amber |
| 55–65 | Yellow |
| 70–80 | Yellow-green to lime |
| 85–100 | Green to teal |
| No signal | Grey |
| Paused | Amber |

The orb brightness and glow radius also scale with focus — brighter and wider at higher scores, faint at low scores.

### Text mode

Click the small **"T" button** in the widget's top-right corner (nearly invisible until hovered) to toggle text on/off. When text is enabled, the widget shows:

- **Focus score** — large number in the center of the orb
- **State label** — DEEP FOCUS / MODERATE / DISTRACTED
- **Session time and average**
- **Goal status** (if a goal is active)

Click "T" again to return to color-only mode.

### Drift alerts in the widget

When a drift alert fires, the widget receives:

- **Ding sound** — a two-tone chime (A4→C#5) plays in the widget's own audio context, even if the main tab is in the background
- **Red flash** — full-window red overlay flashes and fades
- **Orb pulse** — the orb gently scales up/down while the alert is active
- **"⚠ refocus"** text — always visible regardless of text mode

### Key behavior

- The widget **stays visible** even when the main Chrome tab is minimized or you switch to other applications
- It updates via direct window reference (no server needed)
- A background `setInterval` timer ensures updates continue when Chrome throttles the main tab
- Close the widget window to dismiss it; click "Widget" again to reopen

### Popup blocked?

Chrome may block the popup. Look for a blocked-popup icon in the address bar, click it, and allow popups for `localhost:8000`.

---

## 14. Mini Mode

Click **"Mini"** in the header to enter Mini Mode:

- The entire dashboard is hidden
- A single large colored orb fills the screen with your focus score and state
- Session time is shown in the corner
- Click anywhere to return to the full dashboard

Mini Mode is useful when you want a maximally unobtrusive indicator while working.

---

## 15. Recording Sessions

### Starting a recording

Click the **"Record"** button in the header. It turns red and a pulsing dot appears.

### What's recorded

At each recording interval (configurable in Settings), a data point is captured:

| Column | Description |
|--------|-------------|
| `time` | ISO 8601 timestamp |
| `focus` | Focus score (0–100) |
| `delta` | Delta band power |
| `theta` | Theta band power |
| `alpha` | Alpha band power |
| `beta` | Beta band power |
| `gamma` | Gamma band power |
| `state` | `focused`, `moderate`, or `distracted` |
| `app` | Active macOS application (if tracking enabled) |

### Recording settings

- **Rec interval:** How often to sample (default: 5 seconds). Lower values = more data but larger files.
- **Track app:** Toggle macOS app tracking on/off (requires `neurofocus-server.py`)

### Saving recordings

Click **"Record"** again to stop. The app automatically downloads a CSV file named:
```
neurofocus_2026-03-09T15-30-00.csv
```

Only valid signal samples are recorded — no-signal periods are skipped.

### Example CSV output

```csv
time,focus,delta,theta,alpha,beta,gamma,state,app
2026-03-09T15:30:00.000Z,72,0.0012,0.0034,0.0089,0.0156,0.0023,focused,"Google Chrome"
2026-03-09T15:30:05.000Z,68,0.0015,0.0041,0.0095,0.0142,0.0019,moderate,"Visual Studio Code"
2026-03-09T15:30:10.000Z,45,0.0022,0.0055,0.0120,0.0098,0.0015,moderate,"Slack"
```

---

## 16. Active App Tracking

### What it does

Records which macOS application is in the foreground at each recording interval. This lets you analyze which apps correlate with higher or lower focus.

### Requirements

You **must** use `neurofocus-server.py` instead of `python3 -m http.server`. The server exposes a `/active-app` endpoint that uses macOS `osascript` to query the frontmost application.

### First-time setup

macOS will prompt you to grant Terminal (or your terminal emulator) permission to control **System Events** via Accessibility. You must allow this for app detection to work:

1. System Settings → Privacy & Security → Accessibility
2. Enable your terminal application (Terminal, iTerm2, etc.)

### How it appears

When enabled (Settings → "Track app" toggle), the Session panel shows:
```
App: Visual Studio Code
```

This updates every 3 seconds. In recordings, each data point includes the active app name in the `app` CSV column.

### Without the server

If you use `python3 -m http.server` instead, the app tracking gracefully falls back and displays `(use neurofocus-server.py)`. All other features work normally.

---

## 17. Pause

A **⏸ Pause** button appears in the header bar whenever you're connected or in demo mode. This is for when you need to temporarily take off the headband.

### What pauses

When you click Pause, **everything stops**:

- EEG data collection — BLE packets are silently discarded
- Signal processing — no FFT, no band power computation
- Focus scoring — score freezes at last value
- Zone time accumulation — the clock stops, no time is attributed to any zone
- Recording — no CSV samples captured
- Drift alerts — any active alert is cleared, no new alerts fire
- Audio feedback — no new notes play
- Waveform display — clears and shows "PAUSED"
- Focus goals — timer pauses (paused time is excluded from goal duration)

### Visual indicators

- **Amber banner** at the top: "⏸ PAUSED — headband off" with an inline Resume button
- **Header button** changes to "▶ Resume" with amber highlight
- **Focus gauge** shows "PAUSED" badge
- **Widget** orb turns amber with "PAUSED" text

### Resuming

Click **▶ Resume** (header button or banner button). All EEG buffers are cleared on resume so the first post-resume analysis uses only fresh data — no stale pre-pause samples contaminate the readings.

### Auto-cleanup

Pause resets automatically on disconnect, new connection, or demo start.

---

## 18. Focus Glow Overlay (Desktop)

The overlay draws a **glowing colored border around your active macOS window** that changes color in real-time to reflect your focus level. It uses the same smooth color gradient as the widget orb.

### Setup

The overlay requires PyObjC (Python bindings for macOS native APIs):

```bash
pip3 install pyobjc-framework-Cocoa pyobjc-framework-Quartz
```

### Running

You need three terminal windows:

```bash
# Terminal 1: Start the server
python3 neurofocus-server.py

# Terminal 2: Start the overlay
python3 neurofocus-overlay.py

# Terminal 3 (optional): Open Chrome
open -a "Google Chrome" http://localhost:8000/muse-focus-monitor.html
```

The overlay will print a confirmation when it connects to the server:
```
✓  Connected to NeuroFocus server
✓  Overlay active — glow will appear when headband is streaming
```

### How it works

The system has three components communicating:

1. **Browser** → computes focus score → POSTs to server every ~1 second
2. **Server** → stores latest score, also queries active window bounds via osascript
3. **Overlay** → polls server every 0.5 seconds → draws a transparent, click-through window on top of the active app

### Color mapping

The overlay uses the same gradient as the widget:

| Score | Color | Appearance |
|-------|-------|------------|
| 0–15 | Deep red | Faint dim glow |
| 20–35 | Red-orange | |
| 40–50 | Orange-amber | |
| 55–65 | Yellow | Moderate glow |
| 70–80 | Yellow-green to lime | |
| 85–100 | Green to teal | Bright vivid glow |
| Paused | Amber | Pulsing |
| No signal | Grey | Very faint |

The glow brightness also scales with focus — brighter and wider at higher scores, faint at low scores.

### Behavior

- The overlay is **fully click-through** — you can interact with windows normally
- It **hides automatically** when there's no signal, when you disconnect, or when the NeuroFocus app itself is focused
- It follows whichever window is in the foreground, updating position every 0.5 seconds
- It works across all macOS Spaces and fullscreen apps
- Press `Ctrl+C` in the overlay terminal to stop it

### macOS permissions

The overlay may trigger a macOS permission request for:
- **Accessibility** — needed to read window positions (System Settings → Privacy & Security → Accessibility)

---

## 19. Settings Reference

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| Alert below | 30% | 0–100 | Focus threshold for drift alerts |
| Alert duration | 5 sec | 1–60 | Sustained time below threshold before alert |
| Alerts | On | On/Off | Master toggle for drift alerts |
| Sound | On | On/Off | Alert tone and calibration chimes |
| Refresh | 1 sec | 1–30 | How often the display updates (data streams continuously) |
| Rec interval | 5 sec | 1–60 | How often recording samples a data point |
| Track app | On | On/Off | macOS active app detection |
| Ambient tone | Off | On/Off | Generative audio feedback |
| Audio style | Handpan | 5 options | Soundscape type |
| Volume | 30% | 0–100 | Audio feedback volume |

**Window Overlay settings** (requires `neurofocus-overlay.py`):

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| Brightness | 100% | 10–200 | Overlay opacity multiplier. 200% = very vivid, 30% = subtle hint |
| Border | 4 px | 1–12 | Solid inner border thickness |
| Glow | 12 px | 0–30 | Soft outer glow width. 0 = sharp border only, 30 = wide aura |

Overlay settings update in real-time as you drag the sliders.

---

## 20. Demo Mode

Click **"Demo"** to run with simulated EEG data. This is useful for:

- Testing the interface before connecting a Muse
- Learning the controls and features
- Verifying audio feedback styles
- Demonstrating the app to others

Demo mode simulates a focus pattern that oscillates between focused and distracted states. All features work in demo mode (goals, recording, widget, audio) except that the data is synthetic.

Click **"Stop"** to exit demo mode.

---

## 21. Startup Script

The `start.sh` script provides one-command control of all NeuroFocus components.

### Usage

```bash
./start.sh            # Start everything (kills old instances first)
./start.sh --stop     # Stop all NeuroFocus processes
./start.sh --restart  # Stop then start
./start.sh --help     # Show help
```

### What it does

1. **Kills any existing instances** — finds and kills processes on port 8000, plus any running overlay or server scripts
2. **Checks dependencies** — verifies Python 3 is available, warns if PyObjC is missing
3. **Starts the server** — `neurofocus-server.py` in the background, logs to `logs/server.log`
4. **Starts the overlay** — `neurofocus-overlay.py` in the background (if PyObjC is installed), logs to `logs/overlay.log`
5. **Opens Chrome** — navigates to `http://localhost:8000/muse-focus-monitor.html`
6. **Tails logs** — shows live output from both server and overlay
7. **Handles Ctrl+C** — cleanly stops all components when you press Ctrl+C

### First-time setup

```bash
# Make the script executable (one time only)
chmod +x start.sh
```

### Log files

Logs are stored in a `logs/` subdirectory:
- `logs/server.log` — server output
- `logs/overlay.log` — overlay output and debug info

---

## 22. Diagnostics

The `neurofocus-diag.py` script helps troubleshoot window detection issues with the overlay.

```bash
python3 neurofocus-diag.py
```

It gives you a 5-second countdown to switch to the target app, then queries the server's `/active-window` endpoint and reports what the server sees: app name, position, and window dimensions. This is useful for diagnosing overlay positioning issues with specific apps.

---

## 23. Connection Log & Troubleshooting

### Viewing the log

The **Connection Log** is collapsed by default. Click the header to expand it. It shows timestamped diagnostic messages:

- **Green:** Success messages
- **Cyan:** Informational (commands, responses, IAF detection)
- **Yellow:** Warnings (non-fatal issues)
- **Red:** Errors

### Common issues

**"No Muse device found"**
- Make sure the Muse S is powered on (pulsing lights)
- Make sure Bluetooth is enabled on your Mac
- Close the Muse app on your phone if it's connected to the headband
- A Muse can only connect to one device at a time

**Connected but no data (0 packets)**
- Try disconnecting and reconnecting
- Turn the Muse off and back on
- Remove the Muse from macOS Bluetooth preferences and re-pair
- Check `chrome://flags/#enable-web-bluetooth` is not disabled

**"NO SIGNAL" with headband on**
- Adjust fit — forehead sensors (AF7/AF8) need direct skin contact
- Wait 10–30 seconds for dry electrodes to settle
- Clean sensors with a slightly damp cloth
- Check the Connection Log for specific channel issues

**Signal quality is poor (high std values)**
- Minimize head movement
- Relax your jaw (jaw clenching produces EMG artifacts)
- Avoid blinking excessively (the app rejects blink artifacts, but excessive blinking degrades accuracy)
- Make sure there's no hair between the forehead sensors and your skin

**Scores seem inaccurate**
- Run the baseline calibration for personalized scoring
- Wait for the auto-calibration to warm up (~30 readings)
- Check if IAF has been detected (shown below calibration section)

**Widget not updating when tab is minimized**
- This should work automatically via a background `setInterval` timer
- If it stops, the browser may be aggressively throttling — try keeping the Chrome window visible but behind other windows instead of fully minimized

**Web Bluetooth not available**
- Must use Google Chrome (not Safari, Firefox, or Brave)
- Must serve via `localhost` (not `file://`)
- Check `chrome://flags/#enable-web-bluetooth`

---

## 24. Technical Details

### Muse S BLE Protocol

The Muse S Athena uses Bluetooth Low Energy with service UUID `0xFE8D`. The connection sequence is:

1. Connect GATT server
2. Get primary service (`0xFE8D`)
3. Get control characteristic (`273e0001-...`)
4. Subscribe to all notifiable characteristics
5. Send commands (length-prefixed: first byte = length of remaining bytes):
   - `h\n` — halt
   - `p1035\n` — set preset (full sensor mode)
   - `dc001\n` — start streaming (must be sent **twice**)

### Packet Structure

Each BLE notification contains one or more inner packets:

```
Byte 0:      Packet length
Byte 1:      Packet index (sequence counter)
Bytes 2-5:   Timestamp (32-bit, 256kHz clock)
Bytes 6-8:   Unknown
Byte 9:      Sensor type ID (0x11=EEG4ch, 0x12=EEG8ch, 0x47=ACCGYRO, etc.)
Bytes 10-13: Unknown/metadata
Bytes 14+:   Sensor data
```

EEG data is 28 bytes per subpacket: 4 channels × 4 samples × 14 bits = 224 bits, packed LSB-first.

### Signal Processing Pipeline

```
Raw EEG (0-1450µV, 14-bit)
    │
    ├── Signal quality check (std, mean, saturation)
    │
    ├── DC offset removal (subtract mean)
    │
    ├── 4th-order Butterworth highpass at 1 Hz
    ├── 4th-order Butterworth lowpass at 50 Hz
    ├── 2nd-order 60 Hz notch filter
    │
    ├── Artifact rejection (150µV p-p threshold, 200ms windows)
    │
    ├── Welch's PSD (128-sample segments, 50% overlap, Hanning window)
    │
    ├── IAF-adjusted band power extraction
    │
    ├── Frontal channel weighting (AF7/AF8 × 2.5)
    │
    ├── Composite focus metric (4 weighted indices)
    │
    ├── Auto-calibration (percentile scaling) or manual baseline
    │
    └── EMA smoothing (α=0.2) → Final focus score (0-100)
```

### IIR Filter Coefficients

All filters are pre-computed for fs=256 Hz:

**Highpass 1 Hz (2nd-order Butterworth):**
```
b = [0.9827947083, -1.9655894166, 0.9827947083]
a = [1, -1.9652933726, 0.9658854606]
```

**Lowpass 50 Hz (2nd-order Butterworth):**
```
b = [0.1990398655, 0.3980797310, 0.1990398655]
a = [1, -0.4044849047, 0.2006443667]
```

**60 Hz Notch (2nd-order):**
```
b = [0.9704989008, -0.1902510539, 0.9704989008]
a = [1, -0.1901532522, 0.9409000000]
```

Each HP and LP section is applied twice (cascaded) for 4th-order response.

---

## 25. Known Limitations

1. **4 dry electrodes** cannot match the spatial resolution of research-grade 64-channel wet EEG systems. The focus score is a useful approximation, not a clinical measurement.

2. **EEG is a correlate of attention**, not a direct measure. The beta/(alpha+theta) engagement ratio and related metrics are well-validated in neurofeedback research, but individual responses vary.

3. **Movement artifacts** — head movement, jaw clenching, and excessive blinking produce artifacts. The app rejects the worst cases, but can't fully compensate for continuous movement.

4. **Muse S Athena only** — the BLE protocol is specific to the Athena hardware revision. Older Muse 2 models use different characteristic UUIDs and a different packet format.

5. **Auto-calibration is relative** — your score of 50 means "middle of YOUR range in THIS session." Scores are not comparable across sessions or between people unless you use the manual baseline calibration.

6. **Channel assignment is assumed** — we decode the 4×4 sample matrix as [TP9, AF7, AF8, TP10] based on OpenMuse's ordering, but haven't cross-validated the channel mapping against known stimuli (e.g., asymmetric alpha with eyes closed).

7. **Consumer hardware noise floor** — the Muse S has a higher noise floor than research-grade amplifiers. Readings in very quiet environments with minimal movement will be most accurate.

8. **Web Bluetooth requires Chrome** — no other browser currently supports the Web Bluetooth API on macOS.
