
#include <Arduino.h>
#include <WiFi.h>
#include <SocketIoClient.h>
#include <ArduinoJson.h>

// --- CONFIGURATION ---
const char* SSID = "Xebec_Base_Station";
const char* PASSWORD = "secure_password";
const char* SERVER_IP = "192.168.1.100"; // IP of your Laptop running main.py
const int SERVER_PORT = 8000;

const String DRONE_ID = "Drone-1"; // UNIQUE ID FOR THIS HARDWARE

// Motor Pins (PWM)
const int MOTOR_FL = 12;
const int MOTOR_FR = 13;
const int MOTOR_BL = 14;
const int MOTOR_BR = 15;

SocketIoClient socket;

// --- MOTOR CONTROL ---
void setMotors(int throttle, int pitch, int roll, int yaw) {
    // Simple mixing algorithm for Quad X
    int m1 = throttle + pitch + roll + yaw;
    int m2 = throttle + pitch - roll - yaw;
    int m3 = throttle - pitch + roll - yaw;
    int m4 = throttle - pitch - roll + yaw;
    
    // Clamp values 0-255
    m1 = constrain(m1, 0, 255);
    m2 = constrain(m2, 0, 255);
    m3 = constrain(m3, 0, 255);
    m4 = constrain(m4, 0, 255);

    analogWrite(MOTOR_FL, m1);
    analogWrite(MOTOR_FR, m2);
    analogWrite(MOTOR_BL, m3);
    analogWrite(MOTOR_BR, m4);
}

// --- SOCKET EVENTS ---
void onConnect(const char * payload, size_t length) {
    Serial.println("✅ CONNECTED to Hive Mind!");
    socket.emit("register", ("{\"id\": \"" + DRONE_ID + "\"}").c_str());
}

void onDroneUpdate(const char * payload, size_t length) {
    // payload is a JSON array of all drones
    DynamicJsonDocument doc(4096);
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        Serial.print("deserializeJson() failed: ");
        Serial.println(error.c_str());
        return;
    }

    // Find MY command in the fleet data
    for (JsonObject drone : doc.as<JsonArray>()) {
        if (drone["id"] == DRONE_ID) {
            String status = drone["status"];
            float targetX = drone["x"];
            float targetY = drone["y"];
            float battery = drone["battery"];

            Serial.printf("🚁 CMD: %s -> Fly to (%.1f, %.1f) | Batt: %.0f%%\n", 
                          status.c_str(), targetX, targetY, battery * 100);

            // LOGIC: Translate Virtual Coords to Physical Flight
            if (status == "scanning" || status == "responding") {
                // ARM MOTORS & FLY
                setMotors(180, 0, 0, 0); // Hover/Cruise throttle
            } else if (status == "idle") {
                // LAND / IDLE
                setMotors(50, 0, 0, 0); // Idle spin
            } else if (status == "returning") {
                // RETURN HOME
                Serial.println("🔋 LOW BATTERY - RTH TRIGGERED");
                setMotors(200, 0, 0, 0); // High speed return
            }
        }
    }
}

void setup() {
    Serial.begin(115200);

    // Setup Motors
    pinMode(MOTOR_FL, OUTPUT);
    pinMode(MOTOR_FR, OUTPUT);
    pinMode(MOTOR_BL, OUTPUT);
    pinMode(MOTOR_BR, OUTPUT);

    // Connect WiFi
    WiFi.begin(SSID, PASSWORD);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println(" Connected!");

    // Setup Socket.IO
    socket.on("connect", onConnect);
    socket.on("drone_update", onDroneUpdate); // Listen to the AI Brain
    
    socket.begin(SERVER_IP, SERVER_PORT, "/socket.io/?transport=websocket");
}

void loop() {
    socket.loop();
    
    // Failsafe: Land if disconnected
    if (WiFi.status() != WL_CONNECTED) {
        setMotors(0, 0, 0, 0);
    }
}
