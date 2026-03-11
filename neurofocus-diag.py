#!/usr/bin/env python3
"""Quick diagnostic: waits 5 seconds so you can switch to the target app, then reports window bounds."""
import time, json, urllib.request

print("Switch to the app you want to test (e.g. Outlook)...")
print("You have 5 seconds...")
for i in range(5, 0, -1):
    print(f"  {i}...")
    time.sleep(1)

print("\nQuerying active window NOW:\n")

try:
    with urllib.request.urlopen('http://localhost:8000/active-window', timeout=3) as r:
        data = json.loads(r.read())
        print(f"  App:    {data.get('app', '?')}")
        print(f"  X:      {data.get('x', '?')}")
        print(f"  Y:      {data.get('y', '?')}")
        print(f"  Width:  {data.get('w', '?')}")
        print(f"  Height: {data.get('h', '?')}")

        if data.get('w', 0) < 100 or data.get('h', 0) < 100:
            print("\n  ⚠ Window is very small — this may be a toolbar/panel, not the main window")
        if data.get('x', 0) > 3000 or data.get('y', 0) > 2000:
            print(f"\n  ⚠ Position suggests a secondary monitor")
except Exception as e:
    print(f"  Error: {e}")
    print("  Make sure neurofocus-server.py is running")
