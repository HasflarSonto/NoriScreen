# CLAUDE.md - Development Notes

## Project Overview
NoriScreen is a single-file kiosk UI (`index.html`) for a Raspberry Pi 4 + 7" DSI touchscreen (800x480). It renders an animated kawaii face on a `<canvas>` and communicates with a laptop "Brain Layer" via WebSocket.

## Architecture
- **Single file**: All HTML, CSS, and JS live in `index.html` inside one `<script>` IIFE
- **No build step, no frameworks** — vanilla JS + Canvas 2D
- `config.json` — runtime config (laptop IP, WS ports)
- `test_harness.py` — Python WebSocket server for local testing
- `Start.md` — original developer spec (state machine, protocol, layout)

## Face Rendering Engine (LVGL-style)
The face engine lives between the `// ---- LVGL-style Emotion Face Engine ----` comment and the `// ---- State machine ----` comment (~lines 354-870).

### Key constants
- `SCALE_X = 800/502 (~1.593)`, `SCALE_Y = 480/410 (~1.171)` — LVGL coordinate scaling
- `CX=400, CY=210` — face center (eyes shifted up from canvas center)
- `EYE_SEP = sx(100)` — half-distance between eye centers
- `MAX_RADIUS = 25*SCALE_Y (~29px)` — max corner rounding on eyes
- `MIN_VIS_H = sy(35)` — minimum visible eye height (prevents too-thin eyes)

### Emotion system
10 emotion configs in `EMOTIONS` object: `eyes_only`, `neutral`, `happy`, `sad`, `angry`, `surprised`, `thinking`, `confused`, `excited`, `cat`.

Each config has numeric params (`eye_w`, `eye_h`, `openness`, `mouth_curve`, `mouth_open`, `mouth_w`) and boolean flags (`no_mouth`, `angry_brows`, `look_side`, `tilt_eyes`, `cat_face`).

Interpolation: numerics lerp at 2.5/s, booleans snap at 50% progress.

### Subsystems (all delta-time based)
- **Blink**: Per-eye state machines (`blinkL`, `blinkR`). Close 60ms, hold 30ms, open 140ms. Interval 2-5s. `triggerBlink()` works for both idle blinks and eye-poke winks.
- **Breathing**: 8% sine pulse at 1.5 rad/s on eye height
- **Gaze**: Smooth lerp toward `gazeTargetX/Y` at 3.0/s. Pixel range X ~103px, Y ~73px
- **Face offset**: Whole face shifts when gaze at edges (X: sx(12), Y: sy(15))
- **Idle behavior**: Random gaze drift 1.5-4s, random emotion change 8-20s (weighted: 50% eyes_only, 20% happy, 15% thinking, 10% neutral, 5% excited)

### Drawing functions
- `drawRoundedRect(cx, cy, w, h, r)` — centered rounded rect path
- `drawEye(cx, cy, w, h, openness, blinkAmt, tiltAdj)` — clips at visH, draws full h inside for eyelid effect
- `drawMouth(cx, cy)` — **currently disabled** (`return;` at top). Supports: flat line, smile arc, frown arc, surprised O, cat :3 with whiskers, no mouth
- `drawBrows(lx, ly, rx, ry, eyeW, eyeH)` — white bars when angry_brows active

### Mouth (disabled but preserved)
The mouth is disabled with an early `return;` at the top of `drawMouth()`. Remove that line to re-enable. Mouth types are selected by `emo.cat_face`, `emo.mouth_open > 0.3`, `emo.mouth_curve` sign, and `emo.no_mouth`.

## State Machine
States: `IDLE`, `EXECUTING`, `CONFIRMING`, `COMPLETED`, `ERROR`, `STOPPED`

State-to-emotion mapping in `setState()`:
- IDLE → idle behavior (random emotions + gaze drift)
- EXECUTING → thinking or neutral (random)
- CONFIRMING → confused
- COMPLETED → happy, then excited after 1s, then idle after 3s
- ERROR → sad
- STOPPED → angry (with X-eyes override in drawEye)

## Touch Interactions
- **Double-tap canvas** → toggle controls tray (E-stop + chat button)
- **Drag on canvas** → petting: face follows finger (high sensitivity, /120 and /80), switches to cat emotion, happy on release
- **Tap on eye** → triggers animated blink on that eye via `triggerBlink()`, brief sad reaction
- **Long-press chat button** → settings overlay (change laptop IP)

## WebSocket Protocol
See `Start.md` section 4 for full protocol. Key message types:
- Laptop→Screen: `task_start`, `step_update`, `confirm_request`, `task_complete`, `task_error`, `set_mood`, `set_presets`
- Screen→Laptop: `confirm_response`, `estop`, `user_message`
- `set_mood` accepts both old mood names and direct emotion names from `EMOTIONS`

## Things That Untouched (do not modify without reason)
- Lines 1-353: All HTML structure, CSS, DOM refs, state variables, config loading
- Lines ~940+: WebSocket connection, message handling, presets, E-stop handler, confirm buttons, controls tray, chat, settings, init()

## Common Pitfalls
- The `mood` variable is used by `drawEye` for the stopped/X-eyes check. Always set it when changing states.
- `blinkL`/`blinkR` are objects with `.phase`, `.t`, `.amount`. The convenience aliases `blinkAmountL`/`blinkAmountR` are updated each frame in `updateBlink()`.
- Emotion interpolation uses per-frame lerp on current values, not from a stored source. This means interrupting a transition mid-way works naturally.
- Canvas is 800x480 fixed, CSS stretches to viewport. Pointer events must convert via `canvasXY()`.
