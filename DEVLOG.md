# NeuroFocus — Complete Technical Reference & Development Log

> Last updated: March 2026
> This document captures all architecture, protocol, design decisions, bug fixes, and implementation details accumulated during development. It is intended to serve as a complete reference for resuming work on this project.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [File Inventory](#2-file-inventory)
3. [Muse S BLE Protocol](#3-muse-s-ble-protocol)
4. [Signal Processing Pipeline](#4-signal-processing-pipeline)
5. [Focus Scoring System](#5-focus-scoring-system)
6. [Preset-Aware Scoring](#6-preset-aware-scoring)
7. [Auto-Calibration](#7-auto-calibration)
8. [Individual Alpha Frequency (IAF)](#8-individual-alpha-frequency-iaf)
9. [Audio Engine Architecture](#9-audio-engine-architecture)
10. [Custom Audio Processing Chain](#10-custom-audio-processing-chain)
11. [Bird Chirp Synthesis](#11-bird-chirp-synthesis)
12. [Continuous Sound Generators](#12-continuous-sound-generators)
13. [Desktop Overlay System](#13-desktop-overlay-system)
14. [Window Detection](#14-window-detection)
15. [Subliminal Message System](#15-subliminal-message-system)
16. [Server Architecture](#16-server-architecture)
17. [Settings Persistence](#17-settings-persistence)
18. [Startup Script](#18-startup-script)
19. [Bug Fixes & Lessons Learned](#19-bug-fixes--lessons-learned)
20. [Known Limitations](#20-known-limitations)
21. [Development Conversation History](#21-development-conversation-history)

---

## 1. Project Overview

NeuroFocus is a real-time brain-computer interface that connects to a **Muse S (Athena)** EEG headband via Web Bluetooth in Chrome, processes raw EEG through a research-grade signal pipeline, and provides a live focus score (0-100) with ambient audio neurofeedback, a native macOS desktop overlay, subliminal affirmations, and comprehensive session tracking.

**Key principle:** Everything runs from a single HTML file served by a simple Python HTTP server. No build tools, no npm, no frameworks. The HTML file contains all CSS, JavaScript, signal processing, audio synthesis, and UI. The Python companions handle macOS-specific features (window detection, overlay drawing).

---

## 2. File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `muse-focus-monitor.html` | ~3120 | Complete app — BLE, DSP, UI, audio engine, all in one file |
| `neurofocus-server.py` | ~378 | Threaded HTTP server with window detection, audio upload, subliminal messages |
| `neurofocus-overlay.py` | ~465 | Native macOS PyObjC overlay — glow border, subliminal text |
| `neurofocus-diag.py` | ~33 | 5-second delay diagnostic for window bounds testing |
| `start.sh` | ~202 | One-command launcher — kills old instances, starts all components |
| `subliminal-messages.txt` | ~25 | Editable affirmation messages, one per line |
| `README.md` | ~121 | Project overview with architecture diagram |
| `INSTRUCTIONS.md` | ~1005 | 25-section comprehensive user guide |
| `.gitignore` | — | Excludes logs/, audio/, .DS_Store, __pycache__ |
| `DEVLOG.md` | — | This file |

---

## 3. Muse S BLE Protocol

**VERIFIED against amused-py and OpenMuse.**

- **Device:** MuseS-F760, firmware 3.1.19, protocol v7 (Athena RevE/F)
- **Service UUID:** `0xFE8D`
- **Control characteristic:** `273e0001-4c4d-454d-96be-f03bac821358`

### Connection sequence

```
h\n          → halt (stop any existing stream)
p1035\n      → set preset 1035 (enables EEG4 + EEG8)
dc001\n      → start data stream (MUST send twice for reliable start)
dc001\n      → second send
```

### Packet format

- 14-byte header
- Byte 9 = sensor type: `0x11` = EEG4 (4-channel), `0x12` = EEG8 (8-channel)
- EEG samples: 14-bit, LSB-first, unsigned
- Scale: `1450.0 / 16383.0 ≈ 0.0885 µV/LSB` (range 0–1450 µV)
- Sample rate: 256 Hz

### Channel mapping

| Channel | Position | Weight in scoring |
|---------|----------|-------------------|
| TP9 | Left temporal | 1.0× |
| AF7 | Left frontal | 2.5× |
| AF8 | Right frontal | 2.5× |
| TP10 | Right temporal | 1.0× |

Frontal channels (AF7/AF8) are weighted 2.5× because prefrontal cortex activity is more relevant to attention and executive function.

---

## 4. Signal Processing Pipeline

All processing happens in JavaScript in the browser at 256 Hz sample rate.

### Step 1: DC Offset Removal
Subtract the mean from each channel's buffer. The raw Muse signal is unsigned 0–1450 µV; centering it around zero is required for filtering.

### Step 2: 4th-Order Butterworth IIR Bandpass (1–50 Hz)
Pre-computed coefficients for fs=256 Hz:

```
Highpass 1Hz: b=[0.9827947083, -1.9655894166, 0.9827947083]
              a=[-1.9652933726, 0.9658854606]

Lowpass 50Hz: b=[0.1990398655, 0.3980797310, 0.1990398655]
              a=[-0.4044849047, 0.2006443667]
```

**Why IIR not FIR:** An earlier FIR implementation had -14dB attenuation in the delta band. The IIR Butterworth is flat within 0.75dB across 2–30 Hz.

### Step 3: 60 Hz Notch Filter
US power line interference removal:
```
Notch 60Hz: b=[0.9704989008, -0.1902510539, 0.9704989008]
            a=[-0.1901532522, 0.9409000000]
```
Verified: -240dB at exactly 60 Hz.

### Step 4: Artifact Rejection
Eye blinks and jaw clenches detected by >150 µV peak-to-peak amplitude in 200ms sliding windows. Affected windows are excluded from PSD computation.

### Step 5: Welch's Method PSD
128-sample segments, 50% overlap, Hanning window. Produces stable spectral power estimates averaged across overlapping segments.

### Step 6: IAF-Adjusted Band Powers
See section 8. Standard bands adjusted ±1 Hz based on detected Individual Alpha Frequency.

### Step 7: Frontal Channel Weighting
AF7/AF8 × 2.5, TP9/TP10 × 1.0. Weighted average across all good channels.

### Step 8: Composite Focus Metric
See section 5.

### Step 9: Auto-Calibrating Percentile Scoring
See section 7.

### Step 10: EMA Temporal Smoothing
α = 0.2, giving ~5-sample memory. Prevents score from jumping frame-to-frame.

---

## 5. Focus Scoring System

The composite metric is a weighted blend of research-validated EEG indices. **The formula changes based on the selected preset** (see section 6).

For Deep Focus (default):
```
engagement = beta / (alpha + theta)          — Pope et al. 1995
attention  = beta / theta                    — Monastra et al. 2005
relBeta    = beta / totalPower
alertness  = alpha / theta

composite  = engagement×0.40 + attention×0.25 + relBeta×5.0×0.20 + alertness×0.15
```

The raw composite (typically 0–8+) is mapped to 0–100 via auto-calibrating percentile scoring.

### Zone thresholds (fixed for all presets)

| Score | Zone | Color | Meaning |
|-------|------|-------|---------|
| 70–100 | Deep | Green | Achieving target brain state well |
| 40–69 | Moderate | Yellow/Amber | Partially achieving target |
| 0–39 | Low | Red | Not producing target brain state |

### Zone labels adapt to preset

| Preset | Green | Yellow | Red |
|--------|-------|--------|-----|
| Deep Focus | DEEP FOCUS | MODERATE | DISTRACTED |
| Creative Flow | CREATIVE FLOW | DRIFTING | UNFOCUSED |
| Relaxed Alert | DEEPLY RELAXED | SOMEWHAT RELAXED | TENSE |
| Meditation | DEEP MEDITATION | SETTLING | RESTLESS |
| Active Learning | DEEP LEARNING | MODERATE | DISTRACTED |
| Custom | ON TARGET | MODERATE | OFF TARGET |

---

## 6. Preset-Aware Scoring

Each preset uses a different formula optimized for the target brain state:

### Deep Focus
```
engagement×0.40 + attention×0.25 + relBeta×5.0×0.20 + alertness×0.15
```
Rewards: high beta relative to theta/alpha. Score rises with intense concentration.

### Creative Flow
```
relTheta×4.0×0.30 + relAlpha×4.0×0.25 + thetaRatio×0.25 + engagement×0.20
```
Rewards: elevated theta+alpha (divergent thinking). Score rises in loose, associative mode.

### Relaxed Alert
```
relAlpha×5.0×0.40 + alertness×0.30 + relaxation×0.15 + (1-relBeta)×0.15
```
Rewards: dominant alpha, suppressed beta. Score rises when calm but awake.

### Meditation
```
relTheta×5.0×0.35 + relAlpha×4.0×0.25 + thetaRatio×0.25 + (1-relBeta)×2.0×0.15
```
Rewards: high theta. Score rises in deep meditative states.

### Active Learning
```
engagement×0.30 + relTheta×4.0×0.25 + relBeta×4.0×0.25 + alertness×0.20
```
Rewards: balanced theta (encoding) + beta (attention). For absorbing new material.

### Custom
Uses **cosine similarity** between actual band distribution and target percentages set by sliders. Works for any arbitrary target profile.

### On preset switch
- Auto-calibration history resets (metric distribution is different)
- Manual calibration cleared (except when returning to Deep Focus)
- EMA smoothing resets for fast adaptation
- Score log counter resets so first scores after switch appear in Connection Log
- Preset selection is persisted to localStorage

---

## 7. Auto-Calibration

Maps the raw composite metric (which varies in range per person and per preset) to a 0–100 score.

### Three modes

1. **Manual calibration** (voice-guided 2-minute process): 60s relaxation + 60s mental math. Uses 10th percentile of relaxed phase as floor, 90th percentile of focused phase as ceiling. Persisted to localStorage.

2. **Auto-calibration** (kicks in after 15 samples ~15 seconds): Running percentile mapping. Uses 10th and 90th percentiles of the last 600 samples. The range adapts as more data arrives.

3. **Fallback** (first 15 seconds): Preset-specific fixed ranges:

| Preset | Low | High |
|--------|-----|------|
| Deep Focus | 0.3 | 3.5 |
| Creative Flow | 0.5 | 3.0 |
| Relaxed Alert | 0.6 | 3.5 |
| Meditation | 0.4 | 3.0 |
| Active Learning | 0.4 | 3.5 |
| Custom | 0.2 | 3.5 |

---

## 8. Individual Alpha Frequency (IAF)

Most people's alpha peak is at 10 Hz, but it varies (8–12 Hz). The IAF system detects the individual's actual alpha peak from frontal channels and adjusts all band boundaries ±1 Hz.

- Detection: Find peak in 7–13 Hz range from AF7/AF8 PSD
- Confidence threshold: requires consistent detection across multiple windows
- Band adjustment: Alpha center shifts from 10 Hz to detected IAF; theta and beta boundaries shift proportionally
- Persisted to localStorage alongside calibration data

---

## 9. Audio Engine Architecture

### Routing

```
playTone() → amb.bus → amb.reverb → rg (gain 0.6) → amb.master → destination
                     → amb.delay  → dg (gain 0.2) → amb.master
                     → amb.dry    → (gain 0.65)    → amb.master
```

### Reverb
3-second convolution reverb generated from decaying noise buffer with early reflections boost.

### Master volume
Slider maps directly to amb.master.gain (0.0 to 1.0). Default 50%.

### 11 Audio Styles

**Note-based (focus controls density via scheduleNotes):**
| Style | Type | Character |
|-------|------|-----------|
| Handpan | perc | Percussive with harmonics, D minor scale |
| Gentle Piano | piano | Hammer attack, warm lowpass, arpeggios when focused |
| Lo-fi Chords | lofi | Detuned, vibrato wobble, heavy lowpass |
| Forest Birds | chirp | Pitched chirps with response calls |
| Zen Bells | bell | Inharmonic partials (2.76×, 5.04×), long sustain |
| Singing Bowls | bowl | Inharmonic partials (1.504×, 2.092×, 2.998×), 8s ring, beating pairs |
| Ambient Pads | pad | Slow-swell sine+triangle, lowpassed |
| Solfeggio | solf | Pure sines at 174–963 Hz with gentle beating |

**Continuous generators (persistent noise nodes):**
| Style | Layers | Focus response |
|-------|--------|----------------|
| Rain | Wash + patter + rumble | Filter opens, volume increases |
| Rain & Birds | Rain layers + scheduled bird chirps | Birds: 3-6/event at 70+, rare single at <30 |
| Ocean | Deep rumble + LFO wave body + foam + shore wash | Bigger waves, faster cycle, more foam |

**Custom Audio File:**
User drops a file or provides URL. See section 10.

### Density scaling (note-based styles)

| Focus | Notes/event | Interval | Register bias |
|-------|-------------|----------|---------------|
| 70–100 | 3–5 | 2–3.5s | Upper 60% |
| 40–69 | 1–2 | 3–5s | Middle 35% |
| 0–39 | 1 | 4–7s | Lower 10% |

---

## 10. Custom Audio Processing Chain

```
Audio Element → MediaElementSource → Lowpass Filter → Dry Gain ────→ Mixer → Master
                                                    → Reverb Send → Convolver → Reverb Out → Mixer
                                    Noise Buffer (looped) → LP → Noise Gain → Mixer
```

### Focus modulation (every 1.5 seconds)

| Parameter | Focused (100) | Distracted (0) |
|-----------|---------------|----------------|
| Lowpass cutoff | 12,000 Hz (crystal clear) | 800 Hz (very muffled) |
| Dry volume | 90% of slider | 30% of slider |
| Reverb send | 0.08 (subtle) | 0.50 (heavy, spacey) |
| Reverb output | 15% of slider | 50% of slider |
| Noise veil | 0 (silent) | 10% of slider (hiss) |

**CORS note:** `crossOrigin='anonymous'` is set only for HTTP URLs. Blob URLs from drag-and-drop break with CORS headers.

### File persistence
Dropped files are uploaded to server via POST `/upload-audio` with filename in `X-Filename` header. Saved to `audio/` subdirectory. Browser stores the server URL (`http://localhost:8000/audio/filename.mp3`) in localStorage, so it persists across restarts. The `audio/` directory is in `.gitignore`.

### Bird overlay option
"Add birds" checkbox layers focus-responsive bird chirps over any custom audio. Uses independent `_birdOverlay` scheduler that runs alongside the custom audio chain. Same density scaling as Rain & Birds.

---

## 11. Bird Chirp Synthesis

Each chirp is a short sine oscillator with controlled pitch sweep:

```
Primary chirp:
  freq → freq×1.06 (over 25ms) → freq×0.99 (over 55ms more)
  Attack: 0→peak in 8ms, hold 52ms, decay to silence by 250ms

Response chirp (40% chance):
  Slightly higher pitch (+1-5%), delayed 120-220ms
  Same envelope shape, slightly quieter

Trill (30% chance, focus ≥65 only):
  2-5 rapid staccato notes at 65ms spacing
  Very tight pitch variation (±2%)
```

**Key lesson:** `exponentialRampToValueAtTime` with wide pitch ranges (±15-25%) produces audible warping/wobbling. `linearRampToValueAtTime` with tight ranges (±4-6%) sounds much more natural.

---

## 12. Continuous Sound Generators

Rain and Ocean use persistent `AudioBufferSourceNode` with `loop=true` feeding through modulated filters. This avoids the discrete-burst problem (which sounded like "ball bearings on metal" for rain and "shaking a metal sheet" for ocean).

### Rain: 3 layers
- **Wash:** Noise → HP@400Hz → LP@1500-4500Hz (focus-modulated) → gain
- **Patter:** Noise → BP@3000-7000Hz → gain
- **Rumble:** Noise → LP@180Hz → gain

### Ocean: 4 layers
- **Deep rumble:** Noise → LP@150Hz → gain
- **Wave body:** Noise → LP with LFO sweeping filter (0.06-0.1Hz) → gain
- **Foam:** Noise → HP@2000Hz → LP@8000Hz → gain (LFO on volume)
- **Shore wash:** Noise → BP@500Hz → gain

### Rain & Birds: Rain layers + bird scheduler
Same rain layers plus the `scheduleBirds()` function from the bird chirp system.

---

## 13. Desktop Overlay System

### Architecture

```
Browser → POST /focus-score → Server (caches) → GET /focus-score ← Overlay (polls every 0.5s)
                              Server (bg thread polls window bounds every 1s)
                                            → GET /active-window ← Overlay
                              Server → GET /overlay-settings ← Overlay (every 5s)
```

### Overlay window (PyObjC)
- Transparent, click-through `NSWindow` at level 1000 (above most windows)
- `NSWindowCollectionBehaviorCanJoinAllSpaces | Stationary`
- `GlowView` draws outer glow + inner solid border + optional subliminal text
- Color: HSL gradient mapped from score (hue = t² × 150°, where t = score/100)
- Settings: Brightness (10-200%), Border (1-12px), Glow (0-30px)

### Crash protection
- `drawRect_` wrapped in outer try/except (kills entire view if it throws)
- Subliminal text rendering has its own inner try/except
- `_update_inner()` wrapped in try/except with error counting
- `trigger_subliminal_flash()` and `endFlash_()` wrapped in try/except

### Multi-monitor support
Uses `NSScreen.screens()[0].frame().size.height` (primary screen) for coordinate conversion, NOT `mainScreen()` which follows keyboard focus and gives wrong coordinates.

### Coordinate conversion
```python
appkit_x = osascript_x - glow_width
appkit_y = primary_screen_height - osascript_y - window_height - glow_width
```
(osascript uses top-left origin, AppKit uses bottom-left)

---

## 14. Window Detection

### Three-tier approach

1. **AppleScript AXFocusedWindow** — Most reliable for standard apps. Checks size > 200×200 to skip toolbars.

2. **AppleScript first window / largest window** — Fallback for apps where AXFocusedWindow fails. Iterates all windows, picks largest by area.

3. **Quartz CGWindowList via JXA** — Fallback for apps that don't expose AX windows at all (Camtasia, sometimes PowerPoint). Calls `CGWindowListCopyWindowInfo` via JavaScript for Automation, finds largest on-screen window matching the app name with layer == 0.

### Background polling
Window bounds are polled by a daemon thread every 1 second and cached. The `/active-window` endpoint returns instantly from cache instead of blocking on osascript. This fixed a critical issue where the overlay was hiding between app switches because the synchronous osascript call blocked the server from responding to the overlay's HTTP request.

### Apps with known issues
- **Outlook:** AXFocusedWindow returns a 400×73 toolbar. Fixed by size check (>200×200), falls through to largest window.
- **Camtasia:** No AX windows exposed. Fixed by Quartz CGWindowList fallback.
- **PowerPoint:** Intermittent AX failures. Same Quartz fallback.
- **Negative X coordinates:** Valid — indicates a monitor to the left of primary. Not an error.

---

## 15. Subliminal Message System

### Components
- **subliminal-messages.txt:** One message per line, `#` comments. Keep to 3-5 words.
- **Server endpoint:** `GET /subliminal-messages` reads file from script dir or CWD.
- **Overlay:** `trigger_subliminal_flash()` picks random message, renders at 12% opacity for 100ms.
- **Browser controls:** Subliminal toggle, interval (5-120s), Test button.

### Test mode
Browser POSTs `subliminal_test: true` to overlay settings. Overlay detects this flag, flashes at 70% opacity for 1.5 seconds. Server auto-clears the test flag after overlay reads it.

### Text rendering (PyObjC)
Uses `NSAttributedString` with `NSFont.systemFontOfSize_()` and `NSDictionary.dictionaryWithObjectsAndKeys_()` — NOT Python dicts or `NSMutableParagraphStyle` (both cause crashes in some PyObjC versions).

---

## 16. Server Architecture

### ThreadedHTTPServer
Each HTTP request handled in its own daemon thread. Prevents the overlay's GET requests from blocking while the browser is POSTing.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/active-app` | Returns frontmost app name (from cache) |
| GET | `/active-window` | Returns cached window bounds {app,x,y,w,h} |
| GET/POST | `/focus-score` | Score bridge between browser and overlay |
| GET/POST | `/overlay-settings` | Brightness, border, glow, subliminal config |
| GET | `/subliminal-messages` | Reads subliminal-messages.txt |
| POST | `/upload-audio` | Saves dropped audio files to audio/ directory |
| GET | `/favicon.ico` | Returns 204 (suppresses Chrome's 404 noise) |
| GET | `/*` | Static file server (serves HTML, audio files, etc.) |

### Error handling
- `send_json()` catches `BrokenPipeError` and `ConnectionResetError` silently
- `send_error()` overridden to log the actual path and suppress favicon noise
- Log filter suppresses high-frequency polling endpoints from stdout

---

## 17. Settings Persistence

### localStorage key: `nf_audio_settings`

Stores:
- `ambientOn` — whether ambient tone was enabled
- `style` — selected audio style
- `volume` — volume slider value
- `customUrl` — HTTP URL for custom audio file
- `customFileName` — display name
- `customBirds` — bird overlay toggle
- `preset` — selected band target preset
- `ovBright`, `ovBorder`, `ovGlow` — overlay settings
- `ovSubliminal`, `ovSubInterval` — subliminal settings

### Save triggers
- toggleAmbient(), updateAmbientVol(), updateAmbientStyle()
- handleAudioFile() (after upload), loadCustomAudioFromUrl()
- updateOverlaySettings(), applyPreset()
- beforeunload event

### Restore
On DOMContentLoaded: all UI controls restored, overlay settings pushed to server.

**Ambient auto-start:** Chrome's autoplay policy blocks AudioContext creation without a user gesture. The checkbox is restored to checked state, status shows "Click anywhere to start", and a click/keydown listener calls `toggleAmbient()` synchronously on first interaction. The `setTimeout` wrapper was removed because async calls don't satisfy Chrome's autoplay policy.

### Other localStorage keys
- `nf_calibration` — manual calibration baseline/range + IAF
- `nf_sessions` — session history (up to 100 sessions)

---

## 18. Startup Script (start.sh)

### Cleanup sequence
1. Close existing NeuroFocus Chrome tabs via osascript
2. Kill anything on port 8000 via `lsof -ti:8000 | xargs kill -9`
3. Kill overlay and server processes via `pkill -f`
4. 1-second pause for port release

### Launch sequence
1. Check dependencies (Python 3, warn if PyObjC missing)
2. Start server: `python3 -u neurofocus-server.py > logs/server.log 2>&1 &`
3. Verify server started (check PID)
4. Start overlay: `python3 -u neurofocus-overlay.py > logs/overlay.log 2>&1 &`
5. Open Chrome to `http://localhost:8000/muse-focus-monitor.html`
6. Tail both log files
7. Trap Ctrl+C → stop_all

**`-u` flag:** Required for unbuffered Python stdout. Without it, output is block-buffered when redirected to a file and nothing appears in the logs until the buffer fills.

### Overlay server retry
Overlay retries connecting to server for up to 10 seconds on startup (20 attempts × 0.5s). Handles reboot scenarios where server takes a few seconds to come up.

---

## 19. Bug Fixes & Lessons Learned

### Critical fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Score stuck at 100 | Sigmoid mapping compressed 143 distinct values to 100 | Replaced with auto-calibrating percentile + EMA |
| FIR filter -14dB in delta | FIR design error | Replaced with IIR Butterworth (flat within 0.75dB) |
| Overlay freezes on pause | Browser didn't notify server immediately | Added immediate POST on pause/resume |
| Overlay stuck after pause | Overlay drew amber at stale position | Hide overlay entirely when paused, clear cached bounds |
| Overlay hides between app switches | Server blocked on osascript during HTTP request | Background thread caches window bounds, endpoint returns from cache |
| No overlay on Camtasia/PowerPoint | Apps don't expose AX windows | Added Quartz CGWindowList JXA fallback |
| Outlook toolbar overlay | AXFocusedWindow returned 400×73 toolbar | Size check >200×200, fallback to largest window |
| Audio doesn't start on page load | Chrome autoplay policy | Defer to first user click/keydown, call synchronously (no setTimeout) |
| Local file paths don't work | Browser security blocks file:// in Audio elements | Drag-drop uploads to server, uses HTTP URL |
| Overlay crashes silently | Unhandled exception in drawRect_ kills NSView | Wrapped in try/except at multiple levels |
| BrokenPipeError in server logs | Client disconnects mid-response | try/except in send_json |
| Favicon 404 noise | Chrome requests /favicon.ico | Handle in do_GET, return 204 |
| Python output buffering | Block-buffered when redirected to file | Added `-u` flag to python3 commands |
| Bird chirps sound wobbly | exponentialRamp with ±15-25% pitch | Switched to linearRamp with ±4-6% |
| Rain sounds like ball bearings | Discrete short noise bursts | Replaced with continuous looped noise through modulated filters |
| Ocean sounds like metal sheet | Same discrete burst issue | Same fix: continuous layered noise with LFO-swept filters |
| `applyPreset()` crash on load | Called before `S` state object defined | Added `typeof S !== 'undefined'` guards |
| Overlay fails after reboot | Server not ready when overlay starts | Added 10-second retry loop |

### Design lessons

- **PyObjC is fragile:** Use simplest possible API calls. `NSFont.systemFontOfSize_()` not `systemFontOfSize_weight_()`. `NSDictionary.dictionaryWithObjectsAndKeys_()` not Python dicts for NSAttributedString attributes. Always wrap drawRect_ in try/except.
- **Chrome autoplay policy:** AudioContext must be created/resumed synchronously inside a user gesture event handler. No setTimeout, no Promise.then.
- **Web Bluetooth:** Only works in Chrome, only over HTTPS or localhost. Safari/Firefox do not support it.
- **osascript blocking:** A single osascript call can take 1-3 seconds. Never call it synchronously in an HTTP request handler.
- **Single-threaded HTTP server:** Will block all clients while handling one request. Always use ThreadedHTTPServer or background caching for slow operations.

---

## 20. Known Limitations

- **4 dry electrodes:** Consumer EEG hardware ceiling. Higher noise floor than research-grade systems. Good enough for relative focus tracking, not clinical diagnosis.
- **Channel assignment:** TP9/AF7/AF8/TP10 ordering not cross-validated against known stimuli in this implementation.
- **Overlay on some apps:** Apps with non-standard window hierarchies may still fail even with the Quartz fallback. The overlay gracefully hides rather than showing in the wrong position.
- **Custom audio CORS:** HTTP URLs from other domains need CORS headers on the remote server. Drag-and-drop (upload to local server) always works.
- **macOS only:** Overlay and window detection use macOS-specific APIs (PyObjC, osascript, Quartz). The HTML app itself works on any OS with Chrome + Web Bluetooth.
- **No mobile support:** Web Bluetooth on mobile is limited. The UI is designed for desktop.

---

## 21. Development Conversation History

This project was built across multiple conversations:

1. **Session 1** (2026-03-10): Initial build — BLE protocol reverse engineering, signal processing pipeline, basic UI, connection flow, packet decoding.

2. **Session 2** (2026-03-16): Major feature additions — desktop overlay, audio neurofeedback (5 original styles), widget, focus goals, recording, calibration system.

3. **Session 3** (2026-03-16 continued): Polish — pause system, overlay crash fixes, start.sh, documentation (README + INSTRUCTIONS), .gitignore, full project assembly.

4. **Session 4** (current, 2026-03-19): Extensive additions and fixes:
   - 5 new audio styles (piano, lo-fi, bowls, rain, ocean)
   - Continuous noise generators for rain/ocean
   - Custom audio file with focus-responsive processing chain
   - Drag-and-drop file upload with server persistence
   - Rain & Birds combined style
   - Bird overlay option for custom audio
   - Subliminal message system (overlay + server + browser controls + test mode)
   - Preset-aware scoring formulas (6 different metrics)
   - Preset-specific zone labels
   - Settings persistence (audio, overlay, subliminal, preset, ambient on/off)
   - Threaded server with background window polling
   - Quartz CGWindowList fallback for window detection
   - Overlay retry on startup for post-reboot reliability
   - Unbuffered Python output for real-time logs
   - Bird chirp wobble fix (tighter pitch sweeps)
   - Chrome autoplay policy fix (synchronous gesture handler)
   - Numerous overlay crash protections

### Transcript files
Full conversation transcripts are stored in `/mnt/transcripts/`:
- `2026-03-10-16-22-38-muse-s-eeg-focus-monitor.txt`
- `2026-03-16-13-42-06-neurofocus-muse-eeg-monitor.txt`
- `2026-03-16-15-33-58-muse-s-neurofocus-full-build.txt`

---

*This document should provide sufficient context to resume development from any point without access to the original conversation transcripts.*
