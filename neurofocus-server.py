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

import socket

PORT = 8000

class ReusableHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True
    allow_reuse_port = True

# Shared state
current_score = {'score': -1, 'state': 'unknown', 'paused': False, 'timestamp': 0}
overlay_settings = {'brightness': 100, 'border_width': 4, 'glow_width': 12}
_score_lock = threading.Lock()
_settings_lock = threading.Lock()


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
                return {
                    'app': parts[0].strip(),
                    'x': int(parts[1].strip()),
                    'y': int(parts[2].strip()),
                    'w': int(parts[3].strip()),
                    'h': int(parts[4].strip())
                }
    except Exception:
        pass
    return {'app': 'Unknown', 'x': 0, 'y': 0, 'w': 0, 'h': 0}


class NeuroFocusHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/active-app':
            self.send_json({'app': get_active_app_name()})
        elif self.path == '/focus-score':
            with _score_lock:
                self.send_json(current_score)
        elif self.path == '/active-window':
            self.send_json(get_active_window_bounds())
        elif self.path == '/overlay-settings':
            with _settings_lock:
                self.send_json(overlay_settings)
        else:
            super().do_GET()

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
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def send_json(self, data, code=200):
        response = json.dumps(data)
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(response.encode())

    def log_message(self, format, *args):
        msg = str(args)
        if '/active-app' not in msg and '/focus-score' not in msg and '/active-window' not in msg and '/overlay-settings' not in msg:
            super().log_message(format, *args)


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
    with ReusableHTTPServer(('', PORT), NeuroFocusHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
