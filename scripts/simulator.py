"""Live sensor simulator control (stdlib only).
  python scripts/simulator.py start [--step 10]   # stream simulated wearable + cuff data
  python scripts/simulator.py stop | status
The twin, risk horizon and alerts update live in the dashboard while it runs."""
import argparse, json, sys, urllib.request

def call(base, path, method="GET", body=None):
    req = urllib.request.Request(base + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")

ap = argparse.ArgumentParser()
ap.add_argument("action", choices=["start", "stop", "status"])
ap.add_argument("--base", default="http://localhost:8000")
ap.add_argument("--step", type=float, default=10.0, help="seconds per simulated day")
a = ap.parse_args()
try:
    if a.action == "start":
        print(call(a.base, "/api/simulation/start", "POST", {"step_seconds": a.step}))
    elif a.action == "stop":
        print(call(a.base, "/api/simulation/stop", "POST"))
    print(call(a.base, "/api/simulation/status"))
except Exception as e:
    sys.exit(f"Simulator control failed: {e}")
