# Antigravity Buddy v2: Native Hooks & WiFi WebSocket Developer Handbook

This document serves as an exhaustive, self-contained **Specification and Implementation Plan** for a next-generation terminal/IDE companion system built from scratch. It is designed to allow any agent or developer to immediately compile, run, and verify the entire system without further design cycles.

---

## 🏗️ Architectural Overview & Data Flow

This system replaces SQLite database polling with **active, synchronous event interception** via the native `settings.json` hooks in Antigravity/Gemini agentic loop, communicating over **WiFi WebSockets** on a **single port (`38900`)** to ensure seamless traversal of ISP and enterprise-grade CheckPoint 1500 routers.

```text
  +-------------------+
  |  Antigravity-IDE  |
  +---------+---------+
            | (Runs native hook)
            v (via stdin/stdout)
  +-------------------+      (HTTP POST)      +-------------------+
  |  hook_handler.py  +---------------------->|   Telemetry Hub   |
  +-------------------+                       |   (FastAPI/WS)    |
                                              |    Port 38900     |
                                              +---------+---------+
                                                        |
                                       +----------------+----------------+
                                       | (WebSockets)                    | (WebSockets)
                                       v                                 v
                             +-------------------+             +-------------------+
                             |   Web Simulator   |             |    ESP32 Device   |
                             |  (Browser Widget) |             |    (WiFi Screen)  |
                             +-------------------+             +-------------------+
```

---

## 📂 Project Directory Structure

Create this folder structure in `c:\Users\bazba\Sync\Personal projects\antigravity-buddy-v2`:

```text
antigravity-buddy-v2/
├── README.md                  # Quick-start guide
├── settings.json.patch        # JSON snippet to add to ~/.gemini/settings.json
├── hooks/
│   └── hook_handler.py        # Hook script executed by Antigravity CLI/IDE
├── telemetry-hub/
│   ├── hub.py                 # FastAPI Web & WebSocket server (Single Port: 38900)
│   └── requirements.txt       # Dependencies (fastapi, uvicorn, websockets)
├── web-simulator/
│   ├── index.html             # Glassmorphic simulator dashboard
│   ├── style.css              # Custom styling (Harmonious HSL, Liquid Blob SVG)
│   └── app.js                 # WebSocket client and UI state logic
└── esp32-wifi-fw/             # PlatformIO ESP32 WiFi project
    ├── platformio.ini         # Environment configs (TFT_eSPI, Websockets libraries)
    └── src/
        ├── main.cpp           # WiFi client, WebSocket loop, button debouncing
        ├── buddy.h            # Mascot graphics header
        └── buddy.cpp          # Mascot state rendering definitions
```

---

## 🛠️ Step-by-Step Implementation Details

### Step 0: Hook Configuration (`settings.json.patch`)

Add the following object to `C:\Users\bazba\.gemini\settings.json` (or `~/.antigravity/settings.json`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "name": "Sync Start",
        "type": "command",
        "command": "python \"C:/Users/bazba/Sync/Personal projects/antigravity-buddy-v2/hooks/hook_handler.py\""
      }
    ],
    "BeforeAgent": [
      {
        "name": "State Planning",
        "type": "command",
        "command": "python \"C:/Users/bazba/Sync/Personal projects/antigravity-buddy-v2/hooks/hook_handler.py\""
      }
    ],
    "BeforeModel": [
      {
        "name": "State Thinking",
        "type": "command",
        "command": "python \"C:/Users/bazba/Sync/Personal projects/antigravity-buddy-v2/hooks/hook_handler.py\""
      }
    ],
    "BeforeTool": [
      {
        "name": "Active Shield Interceptor",
        "type": "command",
        "command": "python \"C:/Users/bazba/Sync/Personal projects/antigravity-buddy-v2/hooks/hook_handler.py\"",
        "matcher": "run_command|write_file|multi_replace_file_content"
      }
    ],
    "AfterTool": [
      {
        "name": "State Post-Execution",
        "type": "command",
        "command": "python \"C:/Users/bazba/Sync/Personal projects/antigravity-buddy-v2/hooks/hook_handler.py\""
      }
    ],
    "AfterAgent": [
      {
        "name": "State Concluded",
        "type": "command",
        "command": "python \"C:/Users/bazba/Sync/Personal projects/antigravity-buddy-v2/hooks/hook_handler.py\""
      }
    ]
  }
}
```

---

### Step 1: Hook Handler (`hooks/hook_handler.py`)

This script runs synchronously during the agent execution cycle.
* For **telemetry events** (`BeforeAgent`, `BeforeModel`, etc.), it fires an asynchronous HTTP POST request to update the hub state and exits immediately.
* For **blocking events** (`BeforeTool`), it posts the prompt, polls the hub in a tight loop checking for resolution, outputs the decision JSON on `stdout`, and exits with the appropriate status code.

```python
#!/usr/bin/env python3
import sys
import json
import time
import urllib.request
import urllib.error

HUB_URL = "http://127.0.0.1:38900"

def log_err(msg):
    # Hook output to stdout MUST remain strictly JSON. Log everything to stderr.
    sys.stderr.write(f"[hook_handler] {msg}\n")
    sys.stderr.flush()

def post_event(payload):
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{HUB_URL}/event",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        log_err(f"Failed to post telemetry event: {e}")
        return None

def poll_resolution(prompt_id):
    start_time = time.time()
    # 60 second timeout fallback
    while time.time() - start_time < 60.0:
        try:
            with urllib.request.urlopen(f"{HUB_URL}/prompt/{prompt_id}", timeout=1.5) as r:
                res = json.loads(r.read().decode('utf-8'))
                if res.get("resolved") is True:
                    return res.get("decision"), res.get("reason", "")
        except Exception as e:
            log_err(f"Polling error: {e}")
        time.sleep(0.5)
    return "deny", "Approval request timed out after 60s"

def main():
    try:
        # Read the raw JSON input passed via stdin from the CLI runner
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            log_err("Received empty stdin.")
            sys.exit(0)
            
        data = json.loads(raw_input)
        event_name = data.get("hook_event_name", "unknown")
        session_id = data.get("session_id", "default_session")
        log_err(f"Triggered hook event: '{event_name}' in session: {session_id}")

        # Construct the basic event data to send to the central hub
        event_payload = {
            "session_id": session_id,
            "event": event_name,
            "timestamp": time.time(),
            "data": data
        }

        # Handle non-blocking telemetry events
        if event_name != "BeforeTool":
            post_event(event_payload)
            # Silence is golden: stdout must remain empty for non-blocking events
            sys.exit(0)

        # Handle blocking tool verification
        tool_name = data.get("tool_name", "ide_action")
        tool_args = data.get("tool_args", {})
        prompt_id = f"prompt_{int(time.time() * 1000)}"
        
        # Format a clear hint of the action to display on screens
        hint = ""
        if "CommandLine" in tool_args:
            hint = tool_args["CommandLine"]
        elif "TargetFile" in tool_args:
            hint = f"Edit {tool_args['TargetFile']}"
        else:
            hint = json.dumps(tool_args)[:60]

        # Post the blocking prompt
        prompt_payload = {
            "session_id": session_id,
            "event": "BeforeTool",
            "prompt": {
                "id": prompt_id,
                "tool": tool_name,
                "hint": hint,
                "opts": ["Approve", "Deny"]
            }
        }
        
        post_event(prompt_payload)
        log_err(f"Tool block registered. Awaiting resolution on {prompt_id}...")

        # Poll the hub for user approval/denial
        decision, reason = poll_resolution(prompt_id)
        log_err(f"Hook resolved with decision: [{decision}] - {reason}")

        # Output the exact JSON output to stdout. CLI parses this to unblock.
        response = {
            "decision": decision,
            "reason": reason,
            "systemMessage": f"Cooperative verification: {decision.upper()}"
        }
        
        print(json.dumps(response))
        sys.stdout.flush()

        # If user denied/blocked, exit with status code 2 to trigger a System Block
        if decision == "deny":
            sys.exit(2)
        else:
            sys.exit(0)

    except Exception as e:
        log_err(f"Fatal exception inside hook handler: {e}")
        # Fail safe: allow the tool to continue on script crash to avoid freezing IDE
        print(json.dumps({"decision": "allow", "reason": f"Hook runner crash: {e}"}))
        sys.exit(0)

if __name__ == '__main__':
    main()
```

---

### Step 2: Telemetry Hub (`telemetry-hub/hub.py`)

A single-port FastAPI server that aggregates HTTP telemetry/hook POSTs and broadcasts them instantly to all connected WebSocket clients (Simulators & Devices). It maintains active state in-memory.

*Dependencies (`requirements.txt`):*
```text
fastapi>=0.100.0
uvicorn>=0.22.0
websockets>=11.0.0
```

*Server Code (`telemetry-hub/hub.py`):*
```python
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Optional
import json

app = FastAPI(title="Antigravity Buddy v2 Hub")

# Global In-Memory State
class HubState:
    def __init__(self):
        self.mascot_state = "idle"
        self.active_prompt: Optional[dict] = None
        self.tokens_in = 0
        self.tokens_out = 0
        self.active_connections: List[WebSocket] = []
        self.resolved_prompts: Dict[str, dict] = {} # prompt_id -> {decision, reason}

state = HubState()

class EventPayload(BaseModel):
    session_id: str
    event: str
    timestamp: float
    data: Optional[dict] = None
    prompt: Optional[dict] = None

class ResolutionPayload(BaseModel):
    decision: str  # "allow" or "deny"
    reason: Optional[str] = ""

async def broadcast(message: dict):
    payload = json.dumps(message)
    disconnected = []
    for ws in state.active_connections:
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in state.active_connections:
            state.active_connections.remove(ws)

@app.post("/event")
async def receive_event(payload: EventPayload):
    # Parse mascot states based on hook event
    event = payload.event
    if event == "SessionStart":
        state.mascot_state = "celebrate"
        state.active_prompt = None
    elif event == "BeforeAgent":
        state.mascot_state = "idle"
    elif event == "BeforeModel":
        state.mascot_state = "thinking"
    elif event == "AfterModel":
        state.mascot_state = "busy"
    elif event == "AfterAgent":
        state.mascot_state = "sleep"
    elif event == "BeforeTool" and payload.prompt:
        state.mascot_state = "attention"
        state.active_prompt = payload.prompt

    # Build WebSocket broadcast payload
    broadcast_payload = {
        "type": "state_sync",
        "mascot_state": state.mascot_state,
        "active_prompt": state.active_prompt
    }
    
    await broadcast(broadcast_payload)
    return {"ok": True, "mascot_state": state.mascot_state}

@app.get("/prompt/{prompt_id}")
async def get_prompt_status(prompt_id: str):
    if prompt_id in state.resolved_prompts:
        res = state.resolved_prompts[prompt_id]
        return {"resolved": True, "decision": res["decision"], "reason": res["reason"]}
    return {"resolved": False}

@app.post("/prompt/{prompt_id}/resolve")
async def resolve_prompt(prompt_id: str, resolution: ResolutionPayload):
    state.resolved_prompts[prompt_id] = {
        "decision": resolution.decision,
        "reason": resolution.reason
    }
    # Clear the active prompt
    if state.active_prompt and state.active_prompt.get("id") == prompt_id:
        state.active_prompt = None
        state.mascot_state = "celebrate" if resolution.decision == "allow" else "dizzy"
        
    await broadcast({
        "type": "state_sync",
        "mascot_state": state.mascot_state,
        "active_prompt": None
    })
    return {"ok": True}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.active_connections.append(websocket)
    # Send baseline state to newly connected client
    try:
        await websocket.send_json({
            "type": "state_sync",
            "mascot_state": state.mascot_state,
            "active_prompt": state.active_prompt
        })
        while True:
            # Maintain connection and listen for resolution commands directly from WebSockets
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("event") == "resolve" and state.active_prompt:
                p_id = state.active_prompt.get("id")
                state.resolved_prompts[p_id] = {
                    "decision": msg.get("decision", "deny"),
                    "reason": msg.get("reason", "WebSocket resolution")
                }
                state.active_prompt = None
                state.mascot_state = "celebrate" if msg.get("decision") == "allow" else "dizzy"
                await broadcast({
                    "type": "state_sync",
                    "mascot_state": state.mascot_state,
                    "active_prompt": None
                })
    except WebSocketDisconnect:
        if websocket in state.active_connections:
            state.active_connections.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=38900)
```

---

### Step 3: Web Simulator (`web-simulator/`)

A futuristic, highly responsive glassmorphic browser simulator that connects to the hub's WebSockets. It renders a beautiful, floating liquid SVG mascot that dynamically responds to status changes.

*Markup (`web-simulator/index.html`):*
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Antigravity Buddy v2 Simulator</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="glass-container">
    <div class="header">
      <div class="status-badge" id="status-text">DISCONNECTED</div>
      <h1>Antigravity Buddy v2</h1>
    </div>

    <!-- Liquid SVG Morphing Blob Mascot -->
    <div class="mascot-container">
      <svg class="blob-svg" viewBox="0 0 200 200">
        <defs>
          <linearGradient id="blob-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="var(--gradient-start)" />
            <stop offset="100%" stop-color="var(--gradient-end)" />
          </linearGradient>
        </defs>
        <path id="blob-path" d="M100,20 C140,20 180,60 180,100 C180,140 140,180 100,180 C60,180 20,140 20,100 C20,60 60,20 100,20 Z" fill="url(#blob-gradient)"></path>
      </svg>
      <div class="mascot-face" id="mascot-eye-layout">
        <div class="eye left"></div>
        <div class="eye right"></div>
      </div>
    </div>

    <!-- Active Tool Permission Dialog overlay -->
    <div class="prompt-box hidden" id="prompt-panel">
      <h3>⚠️ Action Approval Required</h3>
      <p class="tool-name" id="tool-name">executing run_command</p>
      <div class="hint-box" id="tool-hint">git commit -m "update"</div>
      <div class="btn-group">
        <button class="btn btn-allow" onclick="resolvePrompt('allow')">Approve (BOOT)</button>
        <button class="btn btn-deny" onclick="resolvePrompt('deny')">Cancel</button>
      </div>
    </div>
  </div>
  <script src="app.js"></script>
</body>
</html>
```

*Styling (`web-simulator/style.css`):*
```css
:root {
  --gradient-start: #7f00ff;
  --gradient-end: #e100ff;
  --glass-bg: rgba(25, 25, 35, 0.65);
  --glass-border: rgba(255, 255, 255, 0.08);
}

body {
  background: radial-gradient(circle at center, #0f0c1b, #05020a);
  color: #fff;
  font-family: 'Outfit', sans-serif;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  margin: 0;
  overflow: hidden;
}

.glass-container {
  background: var(--glass-bg);
  backdrop-filter: blur(25px);
  border: 1px solid var(--glass-border);
  border-radius: 24px;
  width: 380px;
  padding: 30px;
  text-align: center;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
}

.status-badge {
  font-size: 0.75rem;
  background: rgba(255, 0, 0, 0.2);
  border: 1px solid rgba(255, 0, 0, 0.4);
  color: #ff5555;
  padding: 4px 12px;
  border-radius: 12px;
  display: inline-block;
  font-weight: 700;
  letter-spacing: 1px;
}

.status-badge.connected {
  background: rgba(0, 255, 100, 0.15);
  border: 1px solid rgba(0, 255, 100, 0.4);
  color: #55ff55;
}

.mascot-container {
  position: relative;
  width: 220px;
  height: 220px;
  margin: 30px auto;
}

.blob-svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 10px 20px rgba(127, 0, 255, 0.3));
  transition: all 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.mascot-face {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  gap: 20px;
}

.eye {
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  position: relative;
  transition: all 0.3s ease;
}

.eye::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 6px;
  background: #000;
  border-radius: 50%;
  top: 4px;
  left: 4px;
}

/* Mascot State Morph Animations */
.blob-svg.thinking {
  transform: scale(0.95) rotate(45deg);
  --gradient-start: #00dbde;
  --gradient-end: #fc00ff;
}

.blob-svg.attention {
  transform: scale(1.05);
  --gradient-start: #ff416c;
  --gradient-end: #ff4b2b;
}

.blob-svg.celebrate {
  animation: bounce 0.5s infinite alternate;
  --gradient-start: #11998e;
  --gradient-end: #38ef7d;
}

@keyframes bounce {
  0% { transform: translateY(0) scale(1); }
  100% { transform: translateY(-15px) scale(0.95); }
}

.prompt-box {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  margin-top: 20px;
}

.hidden { display: none !important; }

.btn-group {
  display: flex;
  gap: 15px;
  margin-top: 15px;
}

.btn {
  flex: 1;
  border: none;
  padding: 12px;
  border-radius: 10px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn:hover { opacity: 0.85; }
.btn-allow { background: #38ef7d; color: #000; }
.btn-deny { background: #ff4b2b; color: #fff; }
```

*Logic (`web-simulator/app.js`):*
```javascript
let ws;
const statusBadge = document.getElementById("status-text");
const blobSvg = document.querySelector(".blob-svg");
const promptPanel = document.getElementById("prompt-panel");
const toolNameEl = document.getElementById("tool-name");
const toolHintEl = document.getElementById("tool-hint");

function connect() {
  ws = new WebSocket("ws://127.0.0.1:38900/ws");
  
  ws.onopen = () => {
    statusBadge.innerText = "ONLINE";
    statusBadge.className = "status-badge connected";
  };
  
  ws.onclose = () => {
    statusBadge.innerText = "OFFLINE";
    statusBadge.className = "status-badge";
    setTimeout(connect, 2000); // Auto-reconnect loop
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "state_sync") {
      updateMascotState(data.mascot_state);
      if (data.active_prompt) {
        showPrompt(data.active_prompt);
      } else {
        hidePrompt();
      }
    }
  };
}

function updateMascotState(state) {
  // Clear any existing state animation classes
  blobSvg.className = "blob-svg";
  if (state) {
    blobSvg.classList.add(state);
  }
}

function showPrompt(prompt) {
  toolNameEl.innerText = `executing: ${prompt.tool}`;
  toolHintEl.innerText = prompt.hint;
  promptPanel.classList.remove("hidden");
}

function hidePrompt() {
  promptPanel.classList.add("hidden");
}

function resolvePrompt(decision) {
  ws.send(JSON.stringify({
    event: "resolve",
    decision: decision,
    reason: "Approved from Web Simulator"
  }));
}

connect();
```

---

### Step 4: ESP32 WiFi Firmware (`esp32-wifi-fw/`)

Configured for **PlatformIO**. It runs on the Seeed Xiao ESP32-S3 (GC9A01 240x240 circular screen) or ESP32-C6 DevKit (ST7789 172x320 rectangular screen).
* Connections: Local WiFi (`Homelab-wireless` / `52288488`).
* Connection Protocol: Fast WebSocket interface straight to `ws://192.168.1.xxx:38900/ws` (replace with your local development host IP or host MDNS `antigravity-hub.local`).

*Platformio Config (`esp32-wifi-fw/platformio.ini`):*
```ini
[env:seeed_xiao_esp32s3]
platform = espressif32
board = seeed_xiao_esp32s3
framework = arduino
monitor_speed = 115200
lib_deps =
    bodmer/TFT_eSPI@^2.5.31
    gilmaimon/ArduinoWebsockets@^0.5.3
    bblanchon/ArduinoJson@^6.21.3
build_flags =
    -DUSER_SETUP_LOADED=1
    -DGC9A01_DRIVER=1
    -DTFT_WIDTH=240
    -DTFT_HEIGHT=240
    -DTFT_MOSI=9
    -DTFT_SCLK=8
    -DTFT_CS=5
    -DTFT_DC=4
    -DTFT_RST=3
    -DTFT_BL=2
```

*Firmware Logic (`esp32-wifi-fw/src/main.cpp`):*
```cpp
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>

const char* ssid = "Homelab-wireless";
const char* password = "52288488";
// Change this to match your central server development machine IP running on port 38900
const char* ws_url = "ws://192.168.1.150:38900/ws"; 

using namespace websockets;
WebsocketsClient client;
TFT_eSPI tft = TFT_eSPI();

// GPIO Buttons Configuration
const int BTN_APPROVE = 0; // BOOT button on Xiao ESP32S3
const int BTN_CANCEL = 1;  // GPIO1 external button
unsigned long last_debounce_time = 0;
const unsigned long debounce_delay = 250;

bool has_active_prompt = false;

// Graphic ASCII representations of Zero-G Mascot states (60x60 grid)
void drawMascot(const char* state) {
    tft.fillRect(90, 80, 60, 60, TFT_BLACK);
    if (strcmp(state, "thinking") == 0) {
        // Render thinking face
        tft.fillCircle(120, 110, 25, TFT_CYAN);
        tft.fillCircle(110, 105, 3, TFT_BLACK);
        tft.fillCircle(130, 105, 3, TFT_BLACK);
        tft.drawFastHLine(115, 120, 10, TFT_BLACK);
    } else if (strcmp(state, "attention") == 0) {
        // Red alerts
        tft.fillCircle(120, 110, 28, TFT_RED);
        tft.fillCircle(110, 105, 4, TFT_WHITE);
        tft.fillCircle(130, 105, 4, TFT_WHITE);
        tft.drawCircle(120, 120, 5, TFT_WHITE);
    } else {
        // Default idle slime shape
        tft.fillCircle(120, 110, 25, TFT_MAGENTA);
        tft.fillCircle(110, 105, 3, TFT_WHITE);
        tft.fillCircle(130, 105, 3, TFT_WHITE);
        tft.drawFastHLine(113, 118, 14, TFT_WHITE);
    }
}

void showPromptScreen(const char* tool, const char* hint) {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.drawString("SECURITY BLOCK", 50, 20, 4);
    
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawString("Tool:", 20, 60, 2);
    tft.drawString(tool, 65, 60, 2);
    
    tft.drawString("Hint:", 20, 90, 2);
    tft.drawString(hint, 20, 115, 1);
    
    tft.drawString("[Xiao BOOT Button] Approve", 25, 180, 2);
    tft.drawString("[Cancel Button] Deny", 45, 205, 2);
}

void showIdleScreen() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.drawString("BUDDY ONLINE", 65, 20, 2);
    drawMascot("idle");
}

void onMessageCallback(WebsocketsMessage message) {
    StaticJsonDocument<1024> doc;
    DeserializationError error = deserializeJson(doc, message.data());
    
    if (error) {
        Serial.print("JSON Deserialization failed: ");
        Serial.println(error.c_str());
        return;
    }
    
    const char* type = doc["type"];
    if (strcmp(type, "state_sync") == 0) {
        const char* state = doc["mascot_state"];
        
        if (doc.containsKey("active_prompt") && !doc["active_prompt"].isNull()) {
            has_active_prompt = true;
            JsonObject prompt = doc["active_prompt"];
            showPromptScreen(prompt["tool"], prompt["hint"]);
        } else {
            has_active_prompt = false;
            showIdleScreen();
            drawMascot(state);
        }
    }
}

void handleButtonPresses() {
    if (!has_active_prompt) return;
    
    unsigned long current_time = millis();
    if (current_time - last_debounce_time < debounce_delay) return;
    
    // Check BOOT button (Approve - LOW when pressed)
    if (digitalRead(BTN_APPROVE) == LOW) {
        last_debounce_time = current_time;
        Serial.println("Approved from physical BOOT button!");
        
        StaticJsonDocument<256> doc;
        doc["event"] = "resolve";
        doc["decision"] = "allow";
        doc["reason"] = "Approved via physical Xiao BOOT button";
        
        String payload;
        serializeJson(doc, payload);
        client.send(payload);
    }
    
    // Check Cancel button (Deny - LOW when pressed)
    if (digitalRead(BTN_CANCEL) == LOW) {
        last_debounce_time = current_time;
        Serial.println("Denied from physical cancel button!");
        
        StaticJsonDocument<256> doc;
        doc["event"] = "resolve";
        doc["decision"] = "deny";
        doc["reason"] = "Rejected via physical cancel button";
        
        String payload;
        serializeJson(doc, payload);
        client.send(payload);
    }
}

void setup() {
    Serial.begin(115200);
    
    // Setup Button GPIO Pins
    pinMode(BTN_APPROVE, INPUT_PULLUP);
    pinMode(BTN_CANCEL, INPUT_PULLUP);
    
    // Init GC9A01 Display
    tft.init();
    tft.setRotation(2);
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawString("Connecting WiFi...", 40, 110, 2);
    
    // Connect to WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi Connected!");
    
    tft.fillScreen(TFT_BLACK);
    tft.drawString("Connecting Hub...", 45, 110, 2);
    
    // Connect to WebSocket Server
    client.onMessage(onMessageCallback);
    while (!client.connect(ws_url)) {
        delay(1000);
        Serial.println("WebSocket Connection to Hub failed. Retrying...");
    }
    Serial.println("WebSocket Connection established!");
    showIdleScreen();
}

void loop() {
    client.poll();
    handleButtonPresses();
    delay(20);
}
```

---

## 🏁 Verification Plan for the Next Agent

Execute the following testing checklist to verify the system at each phase boundary:

1. **Verify Phase 1 (Core Web Simulator & Hub):**
   * Start `hub.py` locally.
   * Open `web-simulator/index.html` in Chrome/Edge and confirm WebSocket states transitions from `DISCONNECTED` to `ONLINE`.
   * Open a secondary shell and run a cURL POST to inject a fake block request:
     ```bash
     curl -X POST http://127.0.0.1:38900/event -H "Content-Type: application/json" -d "{\"session_id\":\"test\",\"event\":\"BeforeTool\",\"prompt\":{\"id\":\"12345\",\"tool\":\"run_command\",\"hint\":\"rm -rf /\",\"opts\":[\"Approve\",\"Deny\"]}}"
     ```
   * Confirm the Web Simulator instantly morphs into the **Red Attention** state, renders the prompt, and that clicking "Approve" resets it to green `celebrate`.
2. **Verify Phase 2 (Native IDE Interception):**
   * Copy `settings.json.patch` into your global settings directory.
   * Run any Antigravity-IDE workflow that triggers a command execution.
   * Verify that the terminal **completely blocks** and halts execution, while the browser simulator pops up with the prompt in real-time.
   * Click "Approve" in the browser and verify the command resumes execution in your terminal instantly without lagging.
3. **Verify Phase 3 & 4 (Physical Device WiFi Sync):**
   * Compile and upload `esp32-wifi-fw` via PlatformIO to your Seeed Xiao.
   * Monitor serial output to confirm success connection to your router `Homelab-wireless` on port `38900`.
   * Perform an IDE block execution. Confirm the physical circular GC9A01 LCD screen updates to render the `BeforeTool` prompt in sync.
   * Press the physical Xiao `BOOT` button. Verify the prompt clears and your agent continues execution.
