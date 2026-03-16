#!/usr/bin/env python3
"""
NeuroFocus Server — serves the focus monitor app, provides active app detection,
and bridges focus score data to the desktop overlay.

Usage:
    cd to the directory containing this file and muse-focus-monitor.html, then:
    python3 neurofocus-server.py

    Open http://localhost:8000/muse-focus-monitor.html in Chrome.

Endpoints:
    GET  /active-app          — returns frontmost macOS app name
    POST /focus-score         — browser sends current focus score
    GET  /focus-score         — overlay reads current focus score
    GET  /active-window       — returns frontmost window bounds {x,y,w,h,app}
"""

import http.server
import json
import subprocess
import os
import threading
import time

import socket

PORT = 8000

class ReusableHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True
    allow_reuse_port = True

class ThreadedHTTPServer(ReusableHTTPServer):
    """Handle each request in a separate thread."""
    def process_request(self, request, client_address):
        t = threading.Thread(target=self._handle, args=(request, client_address), daemon=True)
        t.start()
    def _handle(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            pass
        try:
            self.shutdown_request(request)
        except Exception:
            pass

# Shared state
current_score = {'score': -1, 'state': 'unknown', 'paused': False, 'timestamp': 0}
overlay_settings = {'brightness': 100, 'border_width': 4, 'glow_width': 12, 'subliminal': False, 'subliminal_interval': 20}
_score_lock = threading.Lock()
_settings_lock = threading.Lock()

# Cached window bounds — updated by background thread so endpoints respond instantly
_window_cache = {'app': 'unknown', 'x': 0, 'y': 0, 'w': 0, 'h': 0}
_window_lock = threading.Lock()

def _window_poller():
    """Background thread: polls active window bounds every ~1 second."""
    while True:
        try:
            data = get_active_window_bounds()
            if data:
                with _window_lock:
                    _window_cache.update(data)
        except Exception:
            pass
        time.sleep(1.0)


def get_active_app_name():
    try:
        result = subprocess.run(
            ['osascript', '-e',
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() if result.returncode == 0 else 'Unknown'
    except Exception:
        return 'Unknown'


def get_active_window_bounds():
    script = '''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        set appName to name of frontApp

        -- Helper: find largest window
        set bestResult to appName & ",0,0,0,0"
        try
            set wins to windows of frontApp
            set bestA to 0
            repeat with aWin in wins
                try
                    set {wx, wy} to position of aWin
                    set {ww, wh} to size of aWin
                    if ww * wh > bestA then
                        set bestA to ww * wh
                        set bestResult to appName & "," & wx & "," & wy & "," & ww & "," & wh
                    end if
                end try
            end repeat
        end try

        -- Try AXFocusedWindow first
        try
            set focusedWin to value of attribute "AXFocusedWindow" of frontApp
            set {x, y} to value of attribute "AXPosition" of focusedWin
            set {w, h} to value of attribute "AXSize" of focusedWin
            -- Only use if it looks like a real window (not a toolbar/panel)
            if w > 200 and h > 200 then
                return appName & "," & x & "," & y & "," & w & "," & h
            end if
        end try

        -- Try first window
        try
            set frontWin to first window of frontApp
            set {x, y} to position of frontWin
            set {w, h} to size of frontWin
            if w > 200 and h > 200 then
                return appName & "," & x & "," & y & "," & w & "," & h
            end if
        end try

        -- Fall through to largest window
        return bestResult
    end tell
    '''
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            if len(parts) >= 5:
                data = {
                    'app': parts[0].strip(),
                    'x': int(parts[1].strip()),
                    'y': int(parts[2].strip()),
                    'w': int(parts[3].strip()),
                    'h': int(parts[4].strip())
                }
                # If AppleScript got valid bounds, return them
                if data['w'] > 50 and data['h'] > 50:
                    return data
                # Otherwise try Quartz CGWindowList fallback
                return _get_window_bounds_quartz(data['app']) or data
    except Exception:
        pass
    return {'app': 'Unknown', 'x': 0, 'y': 0, 'w': 0, 'h': 0}


def _get_window_bounds_quartz(app_name):
    """Fallback: use Quartz CGWindowListCopyWindowInfo via JXA.
    Works for apps that don\'t expose AX windows (Camtasia, PowerPoint, etc.)."""
    try:
        jxa_script = """
        ObjC.import("Quartz");
        var opts = $.kCGWindowListOptionOnScreenOnly | $.kCGWindowListExcludeDesktopElements;
        var list = $.CGWindowListCopyWindowInfo(opts, 0);
        var count = $.CFArrayGetCount(list);
        var best = null, bestArea = 0;
        var appName = "APPNAME";
        for (var i = 0; i < count; i++) {
            var info = ObjC.castRefToObject($.CFArrayGetValueAtIndex(list, i));
            var owner = info.objectForKey("kCGWindowOwnerName");
            if (owner) {
                var ownerStr = owner.js;
                if (ownerStr.indexOf(appName) >= 0) {
                    var layer = info.objectForKey("kCGWindowLayer").js;
                    if (layer > 0) continue;
                    var b = info.objectForKey("kCGWindowBounds");
                    if (b) {
                        var wx = b.objectForKey("X").js;
                        var wy = b.objectForKey("Y").js;
                        var ww = b.objectForKey("Width").js;
                        var wh = b.objectForKey("Height").js;
                        if (ww > 200 && wh > 200 && ww * wh > bestArea) {
                            bestArea = ww * wh;
                            best = Math.round(wx) + "," + Math.round(wy) + "," + Math.round(ww) + "," + Math.round(wh);
                        }
                    }
                }
            }
        }
        best || "0,0,0,0";
        """.replace("APPNAME", app_name.replace('"', '\\"'))

        result = subprocess.run(
            ['osascript', '-l', 'JavaScript', '-e', jxa_script],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            if len(parts) >= 4:
                x, y, w, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                if w > 50 and h > 50:
                    return {'app': app_name, 'x': x, 'y': y, 'w': w, 'h': h}
    except Exception:
        pass
    return None


class NeuroFocusHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/active-app':
            with _window_lock:
                self.send_json({'app': _window_cache.get('app', 'unknown')})
        elif self.path == '/focus-score':
            with _score_lock:
                self.send_json(current_score)
        elif self.path == '/active-window':
            with _window_lock:
                self.send_json(dict(_window_cache))
        elif self.path == '/overlay-settings':
            with _settings_lock:
                self.send_json(overlay_settings)
        elif self.path == '/subliminal-messages':
            self.send_subliminal_messages()
        elif self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        else:
            super().do_GET()

    def send_subliminal_messages(self):
        """Read messages from subliminal-messages.txt."""
        try:
            fname = 'subliminal-messages.txt'
            # Check multiple locations
            candidates = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), fname),  # Same dir as script
                os.path.join(os.getcwd(), fname),                                 # Current working dir
                os.path.abspath(fname),                                           # Relative to CWD
            ]
            msg_file = None
            for c in candidates:
                if os.path.exists(c):
                    msg_file = c
                    break

            if msg_file:
                with open(msg_file, 'r') as f:
                    lines = [l.strip() for l in f.readlines() if l.strip() and not l.strip().startswith('#')]
                print(f"  [subliminal] Loaded {len(lines)} messages from {msg_file}")
                self.send_json({'messages': lines})
            else:
                checked = ', '.join(os.path.dirname(c) for c in candidates)
                print(f"  [subliminal] subliminal-messages.txt not found. Checked: {checked}")
                self.send_json({'messages': [], 'error': f'subliminal-messages.txt not found (checked: {checked})'})
        except Exception as e:
            print(f"  [subliminal] Error: {e}")
            self.send_json({'messages': [], 'error': str(e)})

    def do_POST(self):
        if self.path == '/focus-score':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                with _score_lock:
                    current_score.update(data)
                self.send_json({'ok': True})
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif self.path == '/overlay-settings':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                with _settings_lock:
                    overlay_settings.update(data)
                self.send_json({'ok': True})
            except Exception as e:
                self.send_json({'error': str(e)}, 400)
        elif self.path.startswith('/upload-audio'):
            self.handle_audio_upload()
        else:
            self.send_error(404)

    def handle_audio_upload(self):
        """Save uploaded audio file to the audio/ subdirectory."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 50 * 1024 * 1024:  # 50MB limit
                self.send_json({'error': 'File too large (50MB max)'}, 400)
                return
            body = self.rfile.read(content_length)

            # Get filename from header or query param
            filename = self.headers.get('X-Filename', 'custom-audio.mp3')
            # Sanitize filename
            filename = os.path.basename(filename).replace(' ', '_')
            if not filename:
                filename = 'custom-audio.mp3'

            # Save to audio/ subdirectory
            audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audio')
            os.makedirs(audio_dir, exist_ok=True)
            filepath = os.path.join(audio_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(body)

            url = f'/audio/{filename}'
            print(f"  [upload] Saved audio: {filename} ({len(body)//1024}KB)")
            self.send_json({'ok': True, 'url': url, 'filename': filename})
        except Exception as e:
            self.send_json({'error': str(e)}, 400)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Filename')
        self.end_headers()

    def send_json(self, data, code=200):
        try:
            response = json.dumps(data)
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(response.encode())
        except (BrokenPipeError, ConnectionResetError):
            pass  # Client disconnected — harmless

    def log_message(self, format, *args):
        msg = str(args)
        if '/active-app' not in msg and '/focus-score' not in msg and '/active-window' not in msg and '/overlay-settings' not in msg and '/subliminal' not in msg and '/upload-audio' not in msg and '/favicon' not in msg:
            super().log_message(format, *args)

    def send_error(self, code, message=None, explain=None):
        """Override to show which path generated the error and suppress favicon noise."""
        if hasattr(self, 'path') and '/favicon' in self.path:
            return  # Suppress favicon 404 noise entirely
        if code == 404 and hasattr(self, 'path'):
            print(f"  [404] {self.path}")
        super().send_error(code, message, explain)


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
    print(f"""
╔══════════════════════════════════════════════════╗
║           NeuroFocus Server v2.0                 ║
║                                                  ║
║  Open in Chrome:                                 ║
║  http://localhost:{PORT}/muse-focus-monitor.html   ║
║                                                  ║
║  Endpoints:                                      ║
║    /active-app      — frontmost app name         ║
║    /focus-score     — GET/POST focus score        ║
║    /active-window   — window bounds for overlay   ║
║                                                  ║
║  For focus glow overlay, run in another terminal: ║
║    python3 neurofocus-overlay.py                  ║
║                                                  ║
║  Press Ctrl+C to stop                            ║
╚══════════════════════════════════════════════════╝
""")
    with ThreadedHTTPServer(('', PORT), NeuroFocusHandler) as httpd:
        # Start background window bounds poller
        t = threading.Thread(target=_window_poller, daemon=True)
        t.start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
