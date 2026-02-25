# HomeBot-Brain Screen Interface — Developer Spec

**Owner:** [Your coworker's name]
**Hardware:** Raspberry Pi 4 + 7" official DSI touchscreen (800×480)
**Runtime:** Chromium kiosk mode running a local web app (HTML/CSS/JS)
**Comms:** WebSocket to the companion laptop (where the Brain Layer runs)

---

## 1. What this screen does

The Pi touchscreen is the robot's face and its only local I/O surface. It serves five functions, listed by priority:

| Priority | Function | Description |
|----------|----------|-------------|
| **P0** | Emergency stop | Always-accessible button that immediately halts all motor activity |
| **P1** | Animated eyes (idle face) | Default state — two large animated eyes that convey the robot is alive and idle |
| **P2** | Task progress | Shows current task name, step count ("Step 3/5"), and a progress bar |
| **P3** | Confirmation prompts | "The robot wants to pick up the mug. Approve / Reject?" with two big touch buttons |
| **P4** | Send message to laptop | Simple text input or preset quick-reply buttons for the user to communicate back |

The screen should **always** show the E-stop. Everything else layers on top of or replaces the eyes view.

---

## 2. Screen states (state machine)

```
┌─────────────┐
│   IDLE       │  ← Default. Animated eyes. E-stop in corner.
│   (eyes)     │
└─────┬───────┘
      │ Brain sends "task_start"
      ▼
┌─────────────┐
│  EXECUTING   │  ← Eyes shrink to top. Progress bar + step label below.
│  (progress)  │
└─────┬───────┘
      │ Brain sends "confirm_request"
      ▼
┌─────────────┐
│  CONFIRMING  │  ← Eyes go to "thinking" expression. Two big buttons:
│  (approve?)  │    [✓ Approve]  [✗ Reject]
└─────┬───────┘
      │ User taps approve/reject → sends response → returns to EXECUTING
      ▼
┌─────────────┐
│  COMPLETED   │  ← Eyes go to "happy" expression. Shows "Done!" for 3s.
│  (success)   │    Then returns to IDLE.
└─────┬───────┘
      │ 3 second timeout
      ▼
      IDLE

ERROR state: reachable from any state. Eyes go to "sad/confused" expression.
             Shows error message. Returns to IDLE on tap or after timeout.
```

The E-STOP button is a **persistent overlay** in the bottom-right corner across all states. It is never hidden, never obscured, never animated away.

---

## 3. Eye animation spec

The eyes are the robot's personality. Keep it simple, but cute, aim at being cute. 

Think pixel art, two simple rounded retangles.


Implementation guidance:
- Use `<canvas>` or SVG for the eyes — not GIFs or sprite sheets. You want smooth parametric control over pupil position, eyelid openness, and blink timing.
- The entire face area should be one component that accepts a `mood` prop or state variable: `idle | executing | confirming | completed | error | stopped`.
- Blink = tween eyelid height to 0 over 100ms, hold 80ms, tween back over 100ms.
- All animations should run at 30fps minimum to feel smooth on the Pi.

---

## 4. WebSocket protocol

The screen app connects to the Brain Layer (running on the companion laptop) via a single WebSocket.

**Connection:** `ws://<LAPTOP_IP>:9090/screen`

The laptop is the server. The Pi screen is the client. If the connection drops, the screen shows the IDLE state with a small "disconnected" indicator in the corner and retries every 2 seconds.

### Messages: Laptop → Screen

```json
{ "type": "task_start", "task_name": "Clean up the table", "total_steps": 5 }

{ "type": "step_update", "current_step": 3, "step_name": "Pick up mug", "total_steps": 5 }

{ "type": "confirm_request", "id": "conf_001", "prompt": "Pick up the red mug from the left side?" }

{ "type": "task_complete", "task_name": "Clean up the table", "success": true }

{ "type": "task_error", "message": "Failed to grasp object after 2 retries" }

{ "type": "set_mood", "mood": "idle" }
```

### Messages: Screen → Laptop

```json
{ "type": "confirm_response", "id": "conf_001", "approved": true }

{ "type": "confirm_response", "id": "conf_001", "approved": false }

{ "type": "estop", "timestamp": 1709000000 }

{ "type": "user_message", "text": "come to the kitchen" }
```

### E-stop behavior

When the user taps E-stop:
1. Screen **immediately** sends `{ "type": "estop" }` over WebSocket
2. Screen **immediately** switches to STOPPED state (X eyes) **without waiting for acknowledgment**
3. Laptop receives estop → kills all motor commands, halts policy inference, sends `{ "type": "set_mood", "mood": "idle" }` when safe to resume
4. Screen returns to IDLE only when it receives the `set_mood` message

The E-stop must work even if the WebSocket is laggy. The screen should also attempt to send the estop message via a redundant HTTP POST to `http://<LAPTOP_IP>:9090/estop` as a fallback.

---

## 5. Layout (800×480 landscape)

```
┌────────────────────────────────────────────────────┐
│                                                    │
│              ◉              ◉                      │
│           (left eye)    (right eye)                │
│                                                    │
│                                                    │
├────────────────────────────────────────────────────┤
│  Step 3/5: Pick up mug         ████████░░░░  60%  │
│                                                    │
│                                           [E-STOP] │
└────────────────────────────────────────────────────┘
```

- **Top 70%:** Eye canvas area. Eyes are centered, roughly 120–150px diameter each, spaced ~100px apart.
- **Bottom 30%:** Status bar area. Shows progress when executing, confirmation buttons when confirming, or is blank/transparent when idle (eyes take full screen).
- **E-stop button:** Fixed bottom-right corner, always visible, red, minimum 80×80px touch target. Do not make it small or subtle — it's a safety control.

For confirmation prompts, the bottom area expands and shows:
```
┌────────────────────────────────────────────────────┐
│              ◉              ◉                      │
│           (smaller, top)                           │
├────────────────────────────────────────────────────┤
│  "Pick up the red mug from the left side?"         │
│                                                    │
│     [ ✓ Approve ]           [ ✗ Reject ]           │
│                                           [E-STOP] │
└────────────────────────────────────────────────────┘
```

Approve = large green button, left side. Reject = large red button, right side. Both at least 150×80px touch targets. The prompt text should be max 2 lines, truncated with ellipsis if longer.

---

## 6. Tech stack recommendation

| Layer | Choice | Reason |
|-------|--------|--------|
| Display | Chromium kiosk (`--kiosk --noerrdialogs`) | Already on Pi OS, no native app needed |
| Frontend | Single HTML file, vanilla JS + Canvas | Keep it dead simple, no build step, easy to iterate |
| WebSocket client | Native `WebSocket` API | No dependencies needed |
| Eye rendering | `<canvas>` 2D context | Smooth parametric animation, low overhead |
| Process manager | systemd service | Auto-start on boot, restart on crash |

Do **not** use React, Vue, or any framework. This is a single-screen kiosk app with 5 states. Vanilla JS with a canvas and some divs is the right level of complexity. Your coworker should be able to open one HTML file and understand the entire UI.

---

## 7. Startup & deployment

1. Pi boots into Raspberry Pi OS Lite (or Desktop with auto-login)
2. systemd service starts a minimal HTTP server (`python -m http.server 8080` in the app directory)
3. systemd service launches Chromium in kiosk mode pointed at `http://localhost:8080`
4. The web app opens a WebSocket to the laptop IP (configured via a `config.json` file or environment variable)
5. Screen shows IDLE (animated eyes) until the Brain Layer connects and sends commands

The laptop IP should be configurable without editing code — either a `config.json` file on the Pi, or a simple settings screen accessible by a long-press gesture on the eyes.

---

## 8. What to build first (suggested order)

1. **Static eyes on canvas** — two ellipses, one blink animation, running in Chromium kiosk. Confirm the Pi can render it smoothly at 30fps.
2. **WebSocket connection** — connect to a test server on the laptop, send/receive one JSON message, confirm round-trip works.
3. **E-stop button** — wire it through WebSocket, test that it sends immediately on tap.
4. **State machine** — implement all 5 states with transitions driven by incoming WebSocket messages.
5. **Progress bar and confirmation UI** — the bottom panel that appears/disappears based on state.
6. **Eye expressions** — the mood variations (focused, questioning, happy, confused, dead).
7. **User message input** — a simple text field or preset buttons for sending messages back. This is lowest priority.

---

## 9. Testing without the robot

The screen app should be fully testable without any robot hardware. Build a simple test harness — a Python script on the laptop that:

- Opens the WebSocket server on port 9090
- Sends a sequence of messages simulating a task (task_start → step_updates → confirm_request → task_complete)
- Logs any messages received from the screen (confirm responses, estop, user messages)

This lets your coworker develop and iterate on the UI entirely independently from the robot hardware and Brain Layer code.

---

## 10. Open questions for Antonio to decide

- [ ] Should the screen play audio? (Beep on confirmation request, chime on completion?) If so, the Pi needs a speaker or audio output.
- [ ] Should the eyes track the user via the head camera? (Cool but adds coupling to the vision pipeline — probably defer to post-MVP.)
- [ ] What color scheme? Suggestion: dark background (#1a1a2e), white eyes, colored accents for progress (blue) and buttons (green/red).
- [ ] Should the user message feature be free-text (on-screen keyboard) or preset buttons only? On-screen keyboards on 7" screens are painful — presets are probably better for the demo.