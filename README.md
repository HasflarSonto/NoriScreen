# NoriScreen

Animated face and control interface for HomeBot, running on a Raspberry Pi 4 with a 7" DSI touchscreen (800x480).

## What it does

- Displays an animated kawaii face with blinking, breathing, gaze, and emotion transitions
- Communicates with the Brain Layer (laptop) over WebSocket
- Provides E-stop, task progress, confirmation prompts, preset messages, and chat

## Files

| File | Purpose |
|------|---------|
| `index.html` | The entire app — HTML, CSS, JS in one file |
| `config.json` | Connection settings (laptop IP, ports) |
| `test_harness.py` | Python test server for development without the robot |
| `Start.md` | Original developer spec |

## Setup on Raspberry Pi

### 1. Install Raspberry Pi OS

Use Raspberry Pi OS Lite or Desktop with auto-login enabled.

### 2. Copy files to the Pi

```bash
scp index.html config.json pi@<PI_IP>:~/noriscreen/
```

### 3. Edit config.json

Set `laptop_ip` to your laptop's IP address on the local network:

```json
{
  "laptop_ip": "192.168.1.100",
  "ws_port": 9090,
  "ws_path": "/screen",
  "estop_port": 9091,
  "estop_path": "/estop"
}
```

### 4. Launch (one command)

Kills any existing server on port 8080, starts a new one in the background, and opens Chromium fullscreen:

```bash
cd ~/Desktop/NoriScreen
fuser -k 8080/tcp 2>/dev/null; python3 -m http.server 8080 & DISPLAY=:0 chromium --kiosk --start-fullscreen http://localhost:8080/index.html
```

### 6. (Optional) Auto-start on boot with systemd

Create `/etc/systemd/system/noriscreen-server.service`:

```ini
[Unit]
Description=NoriScreen HTTP Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/noriscreen
WorkingDirectory=/home/pi/Desktop/NoriScreen
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/noriscreen-browser.service`:

```ini
[Unit]
Description=NoriScreen Kiosk Browser
After=noriscreen-server.service graphical.target
Wants=noriscreen-server.service

[Service]
Type=simple
User=pi
Environment=DISPLAY=:0
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/chromium --kiosk --start-fullscreen http://localhost:8080/index.html
Restart=always

[Install]
WantedBy=graphical.target
```

Enable both:

```bash
sudo systemctl enable noriscreen-server noriscreen-browser
sudo systemctl start noriscreen-server noriscreen-browser
```

## Testing without the robot

On your laptop, run the test harness:

```bash
pip install websockets
python3 test_harness.py
```

This starts a WebSocket server on port 9090 and an HTTP E-stop listener on port 9091. Use the interactive menu to send test messages:

```
1 = Run full demo sequence (task_start → steps → confirm → complete)
2 = Send task_start
3 = Send step_update
4 = Send confirm_request
5 = Send task_complete
6 = Send task_error
7 = Send set_mood (prompts for mood name)
8 = Send set_presets
9 = Quit
```

Then open `index.html` in a browser (or point the Pi at your laptop's IP if testing remotely).

## UI Controls

| Action | What happens |
|--------|-------------|
| **Double-tap** the face | Reveals/hides the controls tray (E-stop + chat) |
| **Tap** E-stop button | Immediately stops all robot activity |
| **Tap** chat button | Opens text input to send a message to the laptop |
| **Long-press** chat button | Opens settings to change the laptop IP |
| **Drag** on the face | Petting interaction — face follows finger, cat expression |
| **Tap** on an eye | That eye winks, brief sad reaction |

## Emotions

The face supports 10 emotions: `eyes_only`, `neutral`, `happy`, `sad`, `angry`, `surprised`, `thinking`, `confused`, `excited`, `cat`.

Send any emotion name via WebSocket:

```json
{ "type": "set_mood", "mood": "happy" }
```

## WebSocket Protocol

See `Start.md` for the full protocol specification.

### Laptop to Screen

- `task_start` — begin a task with progress tracking
- `step_update` — update progress bar
- `confirm_request` — show approve/reject prompt
- `task_complete` — show completion, return to idle
- `task_error` — show error message
- `set_mood` — change face emotion
- `set_presets` — set quick-reply buttons

### Screen to Laptop

- `confirm_response` — user approved/rejected
- `estop` — emergency stop triggered
- `user_message` — user sent a text message

## Changing the laptop IP at runtime

Double-tap the face to reveal controls, then long-press the "chat" button to open the settings overlay. Enter the new IP and tap Save. The WebSocket will reconnect automatically.
