#!/usr/bin/env python3
"""
NoriScreen Test Harness
=======================
Simulates the Brain Layer for testing the NoriScreen UI.
- WebSocket server on port 9090 at /screen
- HTTP POST endpoint at /estop
- Interactive CLI to send test messages

Requirements:
    pip install websockets

Usage:
    python test_harness.py
"""

import asyncio
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    import websockets
    from websockets.server import serve
except ImportError:
    print("ERROR: 'websockets' package required. Install with:")
    print("  pip install websockets")
    raise SystemExit(1)

# Connected screen clients
clients = set()


# ---- WebSocket server ----

async def handler(websocket, path=None):
    """Handle a screen client connection."""
    clients.add(websocket)
    remote = websocket.remote_address
    print(f"\n[+] Screen connected from {remote[0]}:{remote[1]}")
    print(f"    Active clients: {len(clients)}")
    try:
        async for message in websocket:
            try:
                msg = json.loads(message)
                print(f"\n[RECV] {json.dumps(msg, indent=2)}")
                handle_screen_message(msg)
            except json.JSONDecodeError:
                print(f"\n[RECV] (invalid JSON) {message}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        print(f"\n[-] Screen disconnected. Active clients: {len(clients)}")


def handle_screen_message(msg):
    """Process messages from the screen."""
    t = msg.get("type", "")
    if t == "estop":
        print("  *** E-STOP RECEIVED ***")
        print(f"  Timestamp: {msg.get('timestamp', 'N/A')}")
    elif t == "confirm_response":
        approved = msg.get("approved", False)
        print(f"  Confirm '{msg.get('id', '?')}': {'APPROVED' if approved else 'REJECTED'}")
    elif t == "user_message":
        print(f"  User message: \"{msg.get('text', '')}\"")


async def broadcast(msg):
    """Send a message to all connected screen clients."""
    data = json.dumps(msg)
    for ws in list(clients):
        try:
            await ws.send(data)
        except websockets.exceptions.ConnectionClosed:
            clients.discard(ws)


# ---- HTTP E-stop endpoint ----

class EstopHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/estop":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            print(f"\n[HTTP E-STOP] {body.decode('utf-8', errors='replace')}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"received"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress default logging


def run_http_server():
    server = HTTPServer(("0.0.0.0", 9091), EstopHandler)
    print("[HTTP] E-stop endpoint on http://0.0.0.0:9091/estop")
    server.serve_forever()


# ---- Interactive CLI ----

MENU = """
╔══════════════════════════════════════════╗
║         NoriScreen Test Harness          ║
╠══════════════════════════════════════════╣
║  1. Run full task demo                   ║
║  2. Send task_start                      ║
║  3. Send step_update                     ║
║  4. Send confirm_request                 ║
║  5. Send task_complete                   ║
║  6. Send task_error                      ║
║  7. Set mood (idle)                      ║
║  8. Set mood (choose)                    ║
║  9. Send presets                         ║
║  0. Quit                                 ║
╚══════════════════════════════════════════╝
"""

loop = None  # will be set to the asyncio event loop


def send(msg):
    """Thread-safe broadcast."""
    if loop and clients:
        asyncio.run_coroutine_threadsafe(broadcast(msg), loop)
        print(f"[SENT] {json.dumps(msg)}")
    elif not clients:
        print("[WARN] No screen clients connected.")


def demo_sequence():
    """Run a full task lifecycle demo."""
    print("\n--- Starting demo sequence ---")

    send({"type": "set_presets", "presets": ["Come here", "Go to kitchen", "Stop"]})
    time.sleep(1)

    send({"type": "task_start", "task_name": "Clean up the table", "total_steps": 5})
    time.sleep(2)

    for step in range(1, 6):
        names = ["Scan table", "Identify objects", "Pick up mug", "Place in sink", "Wipe surface"]
        send({"type": "step_update", "current_step": step, "step_name": names[step-1], "total_steps": 5})
        if step == 3:
            time.sleep(1.5)
            send({"type": "confirm_request", "id": "conf_001", "prompt": "Pick up the red mug from the left side of the table?"})
            print("  (Waiting for user confirmation...)")
            time.sleep(5)  # wait for user to respond
        time.sleep(2)

    send({"type": "task_complete", "task_name": "Clean up the table", "success": True})
    print("--- Demo complete ---\n")


def cli_loop():
    """Interactive command loop."""
    time.sleep(1)  # let servers start
    print(MENU)

    while True:
        try:
            choice = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            threading.Thread(target=demo_sequence, daemon=True).start()
        elif choice == "2":
            name = input("  Task name [Clean table]: ").strip() or "Clean table"
            steps = input("  Total steps [5]: ").strip() or "5"
            send({"type": "task_start", "task_name": name, "total_steps": int(steps)})
        elif choice == "3":
            step = input("  Current step [1]: ").strip() or "1"
            name = input("  Step name [Pick up mug]: ").strip() or "Pick up mug"
            total = input("  Total steps [5]: ").strip() or "5"
            send({"type": "step_update", "current_step": int(step), "step_name": name, "total_steps": int(total)})
        elif choice == "4":
            prompt = input("  Prompt [Pick up the red mug?]: ").strip() or "Pick up the red mug?"
            cid = f"conf_{int(time.time())}"
            send({"type": "confirm_request", "id": cid, "prompt": prompt})
        elif choice == "5":
            send({"type": "task_complete", "task_name": "task", "success": True})
        elif choice == "6":
            msg = input("  Error message [Grasp failed]: ").strip() or "Grasp failed after 2 retries"
            send({"type": "task_error", "message": msg})
        elif choice == "7":
            send({"type": "set_mood", "mood": "idle"})
        elif choice == "8":
            moods = ["idle", "executing", "confirming", "completed", "error", "stopped"]
            print(f"  Moods: {', '.join(moods)}")
            m = input("  Mood: ").strip()
            if m in moods:
                send({"type": "set_mood", "mood": m})
            else:
                print(f"  Invalid mood. Choose from: {', '.join(moods)}")
        elif choice == "9":
            p = input("  Presets (comma-separated) [Come here,Go to kitchen,Stop]: ").strip()
            p = p or "Come here,Go to kitchen,Stop"
            presets = [x.strip() for x in p.split(",") if x.strip()]
            send({"type": "set_presets", "presets": presets})
        elif choice == "0":
            print("Shutting down...")
            break
        else:
            print(MENU)


# ---- Main ----

async def main():
    global loop
    loop = asyncio.get_event_loop()

    # Start HTTP E-stop server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    # Start WebSocket server
    print(f"[WS] WebSocket server on ws://0.0.0.0:9090/screen")
    async with serve(handler, "0.0.0.0", 9090):
        # Run CLI in a thread
        cli_thread = threading.Thread(target=cli_loop, daemon=True)
        cli_thread.start()

        # Keep the server running
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
