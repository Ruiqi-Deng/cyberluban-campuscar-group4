#include <Arduino.h>
#include <DHT.h>

#include <cmath>

// AM2301
constexpr uint8_t PIN_AM2301 = 27;    // yellow DATA
constexpr uint8_t DHT_TYPE = DHT21;

// Lock (from D:\cyber\BioShuttle)
constexpr uint8_t PIN_RELAY = 5;      // relay IN, active LOW
constexpr uint8_t PIN_DOOR_SW = 18;   // door switch, INPUT_PULLUP
constexpr uint8_t PIN_LOCK_FB = 21;   // bolt feedback, INPUT_PULLUP
constexpr uint8_t PIN_BOOT_BTN = 0;   // lab debug only

constexpr uint32_t UNLOCK_TIME_MS = 800;
constexpr uint32_t DEBOUNCE_MS = 50;
constexpr uint32_t SENSOR_INTERVAL_MS = 2000;
constexpr uint32_t REPORT_INTERVAL_MS = 500;

DHT am2301(PIN_AM2301, DHT_TYPE);

int door_state = 1;     // 0=closed, 1=open
int lock_fb_state = 1;  // 0=retracted, 1=extended
int lock_state = 1;     // 0=unlocked, 1=locked

int32_t enc_left = 0;
int32_t enc_right = 0;
int16_t temperature = 255;  // tenths of C
int16_t humidity = 600;     // tenths of %
uint16_t battery = 12000;

String input_buffer = "";
unsigned long last_report_time = 0;
unsigned long last_sensor_time = 0;

int last_boot_raw = HIGH;
unsigned long last_boot_change = 0;
bool boot_stable_low = false;
bool prev_boot_stable_low = false;

void unlock();
void read_lock_inputs();
void read_am2301();
void send_pos_frame();
void parse_line(String line);

void setup() {
    Serial.begin(115200);
    delay(1500);

    pinMode(PIN_RELAY, OUTPUT);
    pinMode(PIN_DOOR_SW, INPUT_PULLUP);
    pinMode(PIN_LOCK_FB, INPUT_PULLUP);
    pinMode(PIN_BOOT_BTN, INPUT_PULLUP);
    digitalWrite(PIN_RELAY, HIGH);

    am2301.begin();
    delay(2000);
    read_am2301();

    Serial.println("========================================");
    Serial.println("BioShuttle AM2301 + electronic lock");
    Serial.printf("[INFO] AM2301 DATA GPIO%u  relay IN GPIO%u\n",
                  PIN_AM2301, PIN_RELAY);
    Serial.println("[INFO] PC unlock: CTRL,0,0,1,0,0");
    Serial.println("[INFO] BOOT button is lab debug only");
    Serial.println("========================================");

    last_report_time = millis();
    last_sensor_time = millis();
}

void loop() {
    while (Serial.available() > 0) {
        const char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (input_buffer.length() > 0) {
                parse_line(input_buffer);
                input_buffer = "";
            }
        } else {
            input_buffer += c;
        }
    }

    read_lock_inputs();

    if (boot_stable_low && !prev_boot_stable_low) {
        Serial.println("[CMD] BOOT (debug)");
        unlock();
    }
    prev_boot_stable_low = boot_stable_low;

    const unsigned long now = millis();
    if (now - last_sensor_time >= SENSOR_INTERVAL_MS) {
        last_sensor_time = now;
        read_am2301();
    }

    if (now - last_report_time >= REPORT_INTERVAL_MS) {
        last_report_time = now;
        send_pos_frame();
    }
}

void parse_line(String line) {
    line.trim();
    if (!line.startsWith("CTRL,")) {
        return;
    }

    int values[5] = {0, 0, 0, 0, 0};
    int idx = 0;
    int last = 4;

    for (int i = 5; i <= line.length() && idx < 5; i++) {
        if (i == line.length() || line[i] == ',') {
            values[idx++] = line.substring(last + 1, i).toInt();
            last = i;
        }
    }

    Serial.printf("[CMD] CTRL lock=%d photo=%d\n", values[2], values[4]);
    if (values[2] == 1) {
        unlock();
    }
}

void read_lock_inputs() {
    door_state = digitalRead(PIN_DOOR_SW);
    lock_fb_state = digitalRead(PIN_LOCK_FB);
    lock_state = (lock_fb_state == LOW) ? 0 : 1;

    const int raw = digitalRead(PIN_BOOT_BTN);
    if (raw != last_boot_raw) {
        last_boot_change = millis();
        last_boot_raw = raw;
    }
    if (millis() - last_boot_change > DEBOUNCE_MS) {
        boot_stable_low = (raw == LOW);
    }
}

void read_am2301() {
    const float hum = am2301.readHumidity();
    const float tempC = am2301.readTemperature();

    if (!isfinite(hum) || !isfinite(tempC) ||
        hum < 0.0F || hum > 100.0F ||
        tempC < -40.0F || tempC > 80.0F) {
        Serial.println("[ERROR] AM2301 read failed");
        return;
    }

    temperature = static_cast<int16_t>(tempC * 10.0F);
    humidity = static_cast<int16_t>(hum * 10.0F);

    Serial.printf(
        "[OK] AM2301 %.2f C, %.2f %% | lock=%s\n",
        tempC,
        hum,
        lock_state == 1 ? "LOCKED" : "UNLOCKED"
    );
}

void unlock() {
    Serial.println("[ACTION] Unlocking, relay LOW 800 ms...");
    digitalWrite(PIN_RELAY, LOW);
    delay(UNLOCK_TIME_MS);
    digitalWrite(PIN_RELAY, HIGH);
    Serial.println("[ACTION] Unlock pulse done");
}

void send_pos_frame() {
    Serial.print("POS,");
    Serial.print(enc_left);
    Serial.print(",");
    Serial.print(enc_right);
    Serial.print(",");
    Serial.print(lock_state);
    Serial.print(",");
    Serial.print(temperature);
    Serial.print(",");
    Serial.print(humidity);
    Serial.print(",");
    Serial.println(battery);
}
