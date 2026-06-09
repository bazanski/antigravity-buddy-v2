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

// ── Physical button pins on Seeed Xiao ESP32-S3 circular expansion board ─────
#define BTN_APPROVE  D5   // [A] Green  — approve permission (D5/D6 depending on revision)
#define BTN_CANCEL   D4   // [C] Red    — deny/cancel permission
#define BTN_SCROLL   D7   // [B] Blue   — scroll multi-choice options

unsigned long last_debounce_time = 0;
const unsigned long debounce_delay = 250;

bool has_active_prompt = false;
char active_prompt_id[64] = "";
char active_tool[64] = "";
char active_hint[128] = "";
char prompt_options[4][32] = {0};
int prompt_options_count = 0;
int selected_option_idx = 0;

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

void showPromptScreen() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_RED, TFT_BLACK);
    tft.drawCentreString("SECURITY BLOCK", 120, 20, 2);
    
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawString("Tool:", 20, 55, 2);
    tft.drawString(active_tool, 65, 55, 2);
    
    tft.drawString("Hint:", 20, 80, 2);
    tft.drawString(active_hint, 20, 105, 1);
    
    // Draw option select guidelines
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    if (prompt_options_count > 0) {
        char opt_msg[64];
        snprintf(opt_msg, sizeof(opt_msg), "Opt: > %s", prompt_options[selected_option_idx]);
        tft.drawCentreString(opt_msg, 120, 145, 2);
        
        tft.setTextColor(TFT_WHITE, TFT_BLACK);
        tft.drawCentreString("[A] OK  [B] Next  [C] No", 120, 190, 2);
    } else {
        tft.drawCentreString("[A] Approve        [C] Cancel", 120, 190, 2);
    }
}

void showIdleScreen() {
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.drawCentreString("BUDDY ONLINE", 120, 20, 2);
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
            
            strncpy(active_prompt_id, prompt["id"] | "", sizeof(active_prompt_id));
            strncpy(active_tool, prompt["tool"] | "", sizeof(active_tool));
            strncpy(active_hint, prompt["hint"] | "", sizeof(active_hint));
            
            prompt_options_count = 0;
            selected_option_idx = 0;
            if (prompt.containsKey("opts")) {
                JsonArray opts = prompt["opts"];
                for (size_t i = 0; i < opts.size() && i < 4; i++) {
                    strncpy(prompt_options[i], opts[i] | "", 31);
                    prompt_options[i][31] = '\0';
                    prompt_options_count++;
                }
            }
            
            showPromptScreen();
        } else {
            has_active_prompt = false;
            active_prompt_id[0] = '\0';
            prompt_options_count = 0;
            showIdleScreen();
            drawMascot(state);
        }
    }
}

void handleButtonPresses() {
    if (!has_active_prompt) return;
    
    unsigned long current_time = millis();
    if (current_time - last_debounce_time < debounce_delay) return;
    
    // Check [B] SCROLL button (D7 - LOW when pressed)
    if (prompt_options_count > 0 && digitalRead(BTN_SCROLL) == LOW) {
        last_debounce_time = current_time;
        selected_option_idx = (selected_option_idx + 1) % prompt_options_count;
        Serial.printf("Option cycled to: %s\n", prompt_options[selected_option_idx]);
        showPromptScreen();
        while (digitalRead(BTN_SCROLL) == LOW) delay(10);
    }
    
    // Check [A] APPROVE button (D5 - LOW when pressed)
    if (digitalRead(BTN_APPROVE) == LOW) {
        last_debounce_time = current_time;
        Serial.println("Approved from physical [A] button!");
        
        String decision = "allow";
        if (prompt_options_count > 0) {
            // Send selected option index in decision (e.g. opt_0, opt_1, etc.)
            decision = "opt_" + String(selected_option_idx);
        }
        
        StaticJsonDocument<256> doc;
        doc["event"] = "resolve";
        doc["decision"] = decision;
        doc["reason"] = "Approved via physical Xiao button";
        
        String payload;
        serializeJson(doc, payload);
        client.send(payload);
        while (digitalRead(BTN_APPROVE) == LOW) delay(10);
    }
    
    // Check [C] CANCEL button (D4 - LOW when pressed)
    if (digitalRead(BTN_CANCEL) == LOW) {
        last_debounce_time = current_time;
        Serial.println("Denied from physical [C] button!");
        
        StaticJsonDocument<256> doc;
        doc["event"] = "resolve";
        doc["decision"] = "deny";
        doc["reason"] = "Rejected via physical Xiao button";
        
        String payload;
        serializeJson(doc, payload);
        client.send(payload);
        while (digitalRead(BTN_CANCEL) == LOW) delay(10);
    }
}

void setup() {
    Serial.begin(115200);
    
    // Setup Button GPIO Pins with internal pull-up (active-LOW)
    pinMode(BTN_APPROVE, INPUT_PULLUP);
    pinMode(BTN_CANCEL, INPUT_PULLUP);
    pinMode(BTN_SCROLL, INPUT_PULLUP);
    
    // Init GC9A01 Display
    tft.init();
    tft.setRotation(2);
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawCentreString("Connecting WiFi...", 120, 110, 2);
    
    // Connect to WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi Connected!");
    
    tft.fillScreen(TFT_BLACK);
    tft.drawCentreString("Connecting Hub...", 120, 110, 2);
    
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
