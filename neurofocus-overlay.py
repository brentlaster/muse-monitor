
#!/usr/bin/env python3
"""
NeuroFocus Overlay — draws a glowing colored border around the active macOS window
that reflects your real-time focus level.

Requirements:
    pip3 install pyobjc-framework-Cocoa pyobjc-framework-Quartz

Usage:
    1. Start neurofocus-server.py in one terminal
    2. Open muse-focus-monitor.html in Chrome
    3. Run this in another terminal:
       python3 neurofocus-overlay.py

    The overlay will appear as a colored glow around your active window.
    Press Ctrl+C to stop.

Color mapping:
    Deep red     →  Score 0-15   (very distracted)
    Orange       →  Score 30-45
    Amber/Yellow →  Score 50-65
    Green        →  Score 70-85  (focused)
    Teal-green   →  Score 90-100 (deep focus)
    Amber pulse  →  Paused
    Grey         →  No signal
"""

import sys
import json
import urllib.request
import math
import time
import signal
import random
import os

try:
    import objc
    from AppKit import (
        NSApplication, NSWindow, NSView, NSColor, NSBezierPath,
        NSBackingStoreBuffered, NSWindowStyleMaskBorderless,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorStationary,
        NSScreen, NSTimer, NSRunLoop, NSDefaultRunLoopMode, NSApp,
        NSApplicationActivationPolicyAccessory,
        NSFont, NSFontAttributeName, NSForegroundColorAttributeName
    )
    from Foundation import NSAttributedString, NSDictionary
    from Quartz import (
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID
    )
except ImportError:
    print("""
╔══════════════════════════════════════════════════╗
║  NeuroFocus Overlay requires PyObjC              ║
║                                                  ║
║  Install with:                                   ║
║    pip3 install pyobjc-framework-Cocoa \\          ║
║                 pyobjc-framework-Quartz           ║
║                                                  ║
║  Then run again:                                  ║
║    python3 neurofocus-overlay.py                  ║
╚══════════════════════════════════════════════════╝
""")
    sys.exit(1)


SERVER_URL = 'http://localhost:8000'
BORDER_WIDTH = 4
GLOW_WIDTH = 12
POLL_INTERVAL = 0.5  # seconds
CORNER_RADIUS = 10
BRIGHTNESS = 1.0  # 0.0 to 2.0 multiplier

# Live settings (updated from server)
overlay_cfg = {'border_width': BORDER_WIDTH, 'glow_width': GLOW_WIDTH, 'brightness': 100}

# Subliminal message system
subliminal = {
    'enabled': False,
    'messages': [],
    'current_msg': '',
    'flash_active': False,
    'flash_alpha': 0.0,
    'interval': 20,      # Seconds between flashes
    'flash_duration': 0.1,  # Seconds the text is visible (100ms)
    'last_flash': 0,
}


def score_to_hsl(score):
    """Convert focus score (0-100) to HSL values matching the widget gradient."""
    t = score / 100.0
    hue = t * t * 150        # 0° (red) → 150° (teal)
    sat = 0.60 + t * 0.25    # 60-85%
    lit = 0.40 + t * 0.15    # 40-55%
    return hue, sat, lit


def hsl_to_rgb(h, s, l):
    """Convert HSL (h in degrees, s and l 0-1) to RGB (0-1)."""
    h = h / 360.0
    if s == 0:
        return l, l, l
    def hue2rgb(p, q, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return hue2rgb(p, q, h + 1/3), hue2rgb(p, q, h), hue2rgb(p, q, h - 1/3)


def fetch_json(path):
    """Fetch JSON from the server."""
    try:
        req = urllib.request.Request(f'{SERVER_URL}{path}', method='GET')
        req.add_header('Accept', 'application/json')
        with urllib.request.urlopen(req, timeout=1) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


class GlowView(NSView):
    """Custom view that draws a glowing border."""

    score = -1
    paused = False
    _pulse_phase = 0.0

    def drawRect_(self, rect):
      try:
        bounds = self.bounds()
        w = bounds.size.width
        h = bounds.size.height

        # Read live settings
        gw = overlay_cfg.get('glow_width', GLOW_WIDTH)
        bw = overlay_cfg.get('border_width', BORDER_WIDTH)
        bright = max(0, min(200, overlay_cfg.get('brightness', 100))) / 100.0

        if self.score < 0 and not self.paused:
            r, g, b = 0.28, 0.33, 0.41
            alpha = 0.25
        elif self.paused:
            self._pulse_phase += 0.08
            pulse = 0.3 + 0.15 * math.sin(self._pulse_phase)
            r, g, b = 0.96, 0.62, 0.04
            alpha = pulse
        else:
            hue, sat, lit = score_to_hsl(self.score)
            r, g, b = hsl_to_rgb(hue, sat, lit)
            alpha = 0.35 + (self.score / 100.0) * 0.35

        alpha = min(1.0, alpha * bright)

        color = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha)
        glow_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha * 0.4)

        # Outer glow
        outer_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((0, 0), (w, h)), CORNER_RADIUS + gw, CORNER_RADIUS + gw
        )
        inner_cut = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((gw, gw), (w - gw * 2, h - gw * 2)),
            CORNER_RADIUS, CORNER_RADIUS
        )
        outer_path.appendBezierPath_(inner_cut.bezierPathByReversingPath())
        glow_color.setFill()
        outer_path.fill()

        # Inner solid border
        border_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((gw, gw), (w - gw * 2, h - gw * 2)),
            CORNER_RADIUS, CORNER_RADIUS
        )
        inner_cut2 = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            ((gw + bw, gw + bw),
             (w - (gw + bw) * 2, h - (gw + bw) * 2)),
            max(0, CORNER_RADIUS - bw), max(0, CORNER_RADIUS - bw)
        )
        border_path.appendBezierPath_(inner_cut2.bezierPathByReversingPath())
        color.setFill()
        border_path.fill()

        # Subliminal message flash
        if subliminal.get('flash_active') and subliminal.get('current_msg'):
            try:
                msg = subliminal['current_msg']
                fa = subliminal.get('flash_alpha', 0.12)
                font_size = max(12, min(min(w, h) * 0.035, 28))
                font = NSFont.systemFontOfSize_(font_size)
                text_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 1.0, 1.0, fa)
                attrs = NSDictionary.dictionaryWithObjectsAndKeys_(
                    font, NSFontAttributeName,
                    text_color, NSForegroundColorAttributeName,
                    None
                )
                ns_str = NSAttributedString.alloc().initWithString_attributes_(msg, attrs)
                sz = ns_str.size()
                ns_str.drawAtPoint_(((w - sz.width) / 2, (h - sz.height) / 2))
            except Exception:
                pass  # Don't let subliminal crash the overlay

      except Exception as e:
        # Never let drawRect_ crash — it kills the entire overlay
        pass


class OverlayController:
    """Manages the overlay window and polling."""

    def __init__(self):
        self.app = NSApplication.sharedApplication()
        self.app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        # Create a transparent, click-through, always-on-top window
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (100, 100)),  # Initial size, will be updated
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False
        )
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setLevel_(1000)  # Above most windows
        self.window.setIgnoresMouseEvents_(True)  # Click-through
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces |
            NSWindowCollectionBehaviorStationary
        )
        self.window.setHasShadow_(False)

        self.glow_view = GlowView.alloc().initWithFrame_(((0, 0), (100, 100)))
        self.window.setContentView_(self.glow_view)
        self.window.orderFront_(None)

        self.last_bounds = None
        self.visible = False

        # Load subliminal messages
        self.load_subliminal_messages()

    def load_subliminal_messages(self):
        """Load messages from server."""
        data = fetch_json('/subliminal-messages')
        if data and data.get('messages'):
            subliminal['messages'] = data['messages']
            print(f"  ✓  Loaded {len(subliminal['messages'])} subliminal messages")
        else:
            # Try loading directly from file as fallback
            try:
                msg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'subliminal-messages.txt')
                if os.path.exists(msg_file):
                    with open(msg_file, 'r') as f:
                        subliminal['messages'] = [l.strip() for l in f.readlines() if l.strip() and not l.strip().startswith('#')]
                    print(f"  ✓  Loaded {len(subliminal['messages'])} subliminal messages from file")
            except Exception:
                pass
        if not subliminal['messages']:
            print("  ⚠  No subliminal messages loaded")

    def trigger_subliminal_flash(self):
        """Start a subliminal flash."""
        try:
            if not subliminal.get('enabled') or not subliminal.get('messages') or not self.visible:
                return
            now = time.time()
            interval = subliminal.get('interval', 20)
            if now - subliminal.get('last_flash', 0) < interval:
                return
            subliminal['current_msg'] = random.choice(subliminal['messages'])
            subliminal['flash_alpha'] = 0.12
            subliminal['flash_active'] = True
            subliminal['last_flash'] = now
            self.glow_view.setNeedsDisplay_(True)
            # Schedule flash end using a simple delayed call
            dur = subliminal.get('flash_duration', 0.1)
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                dur, self, 'endFlash:', None, False
            )
        except Exception:
            subliminal['flash_active'] = False

    def endFlash_(self, timer):
        """End the subliminal flash."""
        try:
            subliminal['flash_active'] = False
            subliminal['flash_alpha'] = 0.0
            subliminal['current_msg'] = ''
            self.glow_view.setNeedsDisplay_(True)
        except Exception:
            subliminal['flash_active'] = False

    def update(self):
        """Poll server and update overlay."""
        try:
            self._update_inner()
        except Exception as e:
            if not hasattr(self, '_err_count'): self._err_count = 0
            self._err_count += 1
            if self._err_count <= 3 or self._err_count % 100 == 0:
                print(f"  [error] update failed: {e}")

    def _update_inner(self):
        if not hasattr(self, '_tick'): self._tick = 0
        self._tick += 1

        # Get focus score
        score_data = fetch_json('/focus-score')
        if not score_data or (score_data.get('score', -1) == -1 and not score_data.get('paused')):
            if self.visible:
                self.window.orderOut_(None)
                self.visible = False
                self.last_bounds = None
            return

        # Hide overlay entirely when paused
        if score_data.get('paused'):
            if self.visible:
                self.window.orderOut_(None)
                self.visible = False
                self.last_bounds = None
            return

        score = score_data.get('score', -1)
        paused = score_data.get('paused', False)

        # Get active window bounds
        win_data = fetch_json('/active-window')
        if not win_data:
            if self.visible:
                self.window.orderOut_(None)
                self.visible = False
            return

        app_name = win_data.get('app', '')

        if win_data['w'] == 0 and win_data['h'] == 0:
            if self.visible:
                self.window.orderOut_(None)
                self.visible = False
            return

        # Fetch overlay settings periodically (every 10 polls = ~5 seconds)
        if self._tick % 10 == 0:
            settings = fetch_json('/overlay-settings')
            if settings:
                overlay_cfg.update(settings)
                subliminal['enabled'] = settings.get('subliminal', False)
                subliminal['interval'] = max(5, settings.get('subliminal_interval', 20))
                if subliminal['enabled'] and not subliminal['messages']:
                    self.load_subliminal_messages()
                # Handle test request — flash at visible opacity
                if settings.get('subliminal_test') and subliminal.get('messages'):
                    subliminal['current_msg'] = random.choice(subliminal['messages'])
                    subliminal['flash_alpha'] = 0.7  # Clearly visible for testing
                    subliminal['flash_active'] = True
                    subliminal['last_flash'] = time.time()
                    self.glow_view.setNeedsDisplay_(True)
                    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                        1.5, self, 'endFlash:', None, False  # Visible for 1.5 seconds
                    )
                    print(f"  [subliminal] TEST flash: \"{subliminal['current_msg']}\" at 70% opacity")

        gw = overlay_cfg.get('glow_width', GLOW_WIDTH)

        # Convert coordinates: osascript uses top-left origin, AppKit uses bottom-left
        screens = NSScreen.screens()
        primary_h = screens[0].frame().size.height if screens else 1080

        x = win_data['x'] - gw
        y = primary_h - win_data['y'] - win_data['h'] - gw
        w = win_data['w'] + gw * 2
        h = win_data['h'] + gw * 2

        # Sanity check
        if w < 50 or h < 50:
            if self.visible:
                self.window.orderOut_(None)
                self.visible = False
            return

        bounds = (x, y, w, h)

        # Update position only if changed
        if bounds != self.last_bounds:
            self.window.setFrame_display_(((x, y), (w, h)), True)
            self.glow_view.setFrame_(((0, 0), (w, h)))
            self.last_bounds = bounds

        # Update score and redraw
        self.glow_view.score = score
        self.glow_view.paused = paused
        self.glow_view.setNeedsDisplay_(True)

        if not self.visible:
            self.window.orderFront_(None)
            self.visible = True

        # Subliminal flash check
        self.trigger_subliminal_flash()

    def poll_(self, timer):
        """Timer callback."""
        self.update()


def main():
    print("""
╔══════════════════════════════════════════════════╗
║        NeuroFocus Window Overlay v1.0            ║
║                                                  ║
║  Draws a focus-colored glow around your active   ║
║  window. Color shifts from red (distracted)      ║
║  through amber to green (deep focus).            ║
║                                                  ║
║  Requires neurofocus-server.py running on :8000  ║
║  Press Ctrl+C to stop                            ║
╚══════════════════════════════════════════════════╝
""")

    # Verify server is reachable (retry for up to 10 seconds after boot)
    connected = False
    for attempt in range(20):
        test = fetch_json('/focus-score')
        if test is not None:
            connected = True
            break
        if attempt == 0:
            print("  ⏳  Waiting for server at localhost:8000...")
        time.sleep(0.5)

    if not connected:
        print("  ✗  Cannot reach server at localhost:8000 after 10 seconds")
        print("     Start neurofocus-server.py first.\n")
        sys.exit(1)
    print("  ✓  Connected to NeuroFocus server")
    print("  ✓  Overlay active — glow will appear when headband is streaming\n")

    controller = OverlayController()

    # Set up a repeating timer on the NSRunLoop
    timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        POLL_INTERVAL, controller, 'poll:', None, True
    )
    NSRunLoop.currentRunLoop().addTimer_forMode_(timer, NSDefaultRunLoopMode)

    # Handle Ctrl+C gracefully
    def sigint_handler(sig, frame):
        print("\n  Overlay stopped.")
        NSApp.terminate_(None)
    signal.signal(signal.SIGINT, sigint_handler)

    # Run the event loop
    NSApp.run()


if __name__ == '__main__':
    main()

