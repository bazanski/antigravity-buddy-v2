# Antigravity Buddy v2 🛸

> **IDE Compatibility:** Built exclusively for **[Antigravity IDE](https://antigravity.ai)** — Google's Gemini-based coding agent. Not compatible with Claude Code, Cursor, or other IDEs.

A next-generation active terminal/IDE companion system built from scratch. It replaces passive database polling with **active, synchronous event interception** using native `settings.json` hooks in the **Antigravity IDE** agentic loop, communicating over **WiFi WebSockets** to a beautiful glassmorphic simulator and physical microcontroller companion screens.

---

## 🏗️ Architectural Overview & Data Flow

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

```text
antigravity-buddy-v2/
├── README.md                  # Quick-start guide
├── settings.json.patch        # JSON snippet to add to ~/.gemini/settings.json
├── hooks/
│   └── hook_handler.py        # Hook script executed by Antigravity CLI/IDE
├── telemetry-hub/
│   ├── hub.py                 # FastAPI Web & WebSocket server (Port: 38900)
│   └── requirements.txt       # Dependencies (fastapi, uvicorn, websockets)
├── web-simulator/
│   ├── index.html             # Glassmorphic simulator dashboard
│   ├── style.css              # Custom styling (Harmonious HSL, Liquid Blob SVG)
│   └── app.js                 # WebSocket client and UI state logic
└── esp32-wifi-fw/             # PlatformIO ESP32 WiFi project
    ├── platformio.ini         # Environment configs (TFT_eSPI, Websockets libraries)
    └── src/
        └── main.cpp           # WiFi client, WebSocket loop, button debouncing
```

---

## ⚡ Quick Start

### 1. Launch Telemetry Hub
Navigate to `telemetry-hub` and run the FastAPI server:
```bash
cd telemetry-hub
pip install -r requirements.txt
python hub.py
```

### 2. Run Web Simulator
Simply open `web-simulator/index.html` in your favorite web browser. The interface will automatically connect to `ws://127.0.0.1:38900/ws` and display **ONLINE**.

### 3. Setup IDE Hooks
Apply `settings.json.patch` into your global `C:\Users\bazba\.gemini\settings.json` directory. All actions will now route through the cooperative approval gateway!
