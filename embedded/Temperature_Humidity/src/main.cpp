#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>

#include <cmath>

// ================================
// Pin configuration
// ================================

// DS18B20 DIO -> ESP32 GPIO26
constexpr uint8_t DS18B20_DATA_PIN = 26;

// DHT22 DATA yellow wire -> ESP32 GPIO27
constexpr uint8_t DHT22_DATA_PIN = 27;

// DHT sensor type
constexpr uint8_t DHT_TYPE = DHT22;

// Read interval
constexpr uint32_t READ_INTERVAL_MS = 2000;

// ================================
// Sensor objects
// ================================

OneWire oneWire(DS18B20_DATA_PIN);
DallasTemperature ds18b20(&oneWire);

DHT dht22(DHT22_DATA_PIN, DHT_TYPE);

uint32_t lastReadMs = 0;

// ================================
// DS18B20 read function
// ================================

void readDS18B20() {
    ds18b20.requestTemperatures();

    const float temperatureC = ds18b20.getTempCByIndex(0);

    if (!isfinite(temperatureC) ||
        temperatureC == DEVICE_DISCONNECTED_C) {

        Serial.println(
            "[ERROR] DS18B20 read failed. "
            "Check VCC, GND and DIO -> GPIO26."
        );
        return;
    }

    if (temperatureC < -55.0F ||
        temperatureC > 125.0F) {

        Serial.printf(
            "[ERROR] DS18B20 invalid temperature: %.2f C\n",
            temperatureC
        );
        return;
    }

    Serial.printf(
        "[OK] DS18B20 temperature: %.2f C\n",
        temperatureC
    );
}

// ================================
// DHT22 read function
// ================================

void readDHT22() {
    const float humidity = dht22.readHumidity();
    const float temperatureC = dht22.readTemperature();

    if (!isfinite(humidity) || !isfinite(temperatureC)) {
        Serial.println(
            "[ERROR] DHT22 read failed. "
            "Check VCC, GND and DATA yellow wire -> GPIO27. "
            "If wiring is correct, try adding a 4.7k~10k pull-up resistor."
        );
        return;
    }

    if (humidity < 0.0F || humidity > 100.0F) {
        Serial.printf(
            "[ERROR] DHT22 invalid humidity: %.2f %%\n",
            humidity
        );
        return;
    }

    if (temperatureC < -40.0F || temperatureC > 80.0F) {
        Serial.printf(
            "[ERROR] DHT22 invalid temperature: %.2f C\n",
            temperatureC
        );
        return;
    }

    Serial.printf(
        "[OK] DHT22 temperature: %.2f C, humidity: %.2f %%\n",
        temperatureC,
        humidity
    );
}

// ================================
// Read all sensors
// ================================

void readAllSensors() {
    Serial.println("----------------------------------------");

    readDS18B20();
    readDHT22();

    Serial.println("----------------------------------------");
}

// ================================
// Setup
// ================================

void setup() {
    Serial.begin(115200);
    delay(1500);

    Serial.println();
    Serial.println("========================================");
    Serial.println("BioShuttle DS18B20 + DHT22 hardware test");

    Serial.printf(
        "[INFO] DS18B20 data pin: GPIO%u\n",
        DS18B20_DATA_PIN
    );

    Serial.printf(
        "[INFO] DHT22 data pin: GPIO%u\n",
        DHT22_DATA_PIN
    );

    // Init DS18B20
    ds18b20.begin();

    const int ds18b20DeviceCount = ds18b20.getDeviceCount();

    Serial.printf(
        "[INFO] DS18B20 device count: %d\n",
        ds18b20DeviceCount
    );

    if (ds18b20DeviceCount == 0) {
        Serial.println(
            "[ERROR] No DS18B20 detected."
        );
        Serial.println(
            "[CHECK] DS18B20: VCC -> 3V3, GND -> GND, DIO -> GPIO26."
        );
    } else {
        Serial.println(
            "[INFO] DS18B20 detected successfully."
        );
    }

    // Init DHT22
    dht22.begin();

    Serial.println(
        "[INFO] DHT22 initialized."
    );

    Serial.println("========================================");

    // First read
    delay(2000);
    readAllSensors();
}

// ================================
// Loop
// ================================

void loop() {
    const uint32_t now = millis();

    if (now - lastReadMs >= READ_INTERVAL_MS) {
        lastReadMs = now;
        readAllSensors();
    }

    delay(10);
}
