/*
 * BioShuttle - E3 电子锁 & E4 门状态检测
 * 硬件：ESP32 + 12V四线电磁锁 + 继电器 + 微动开关
 * 平台：VS Code + PlatformIO (Arduino框架)
 */

#include <Arduino.h>

// ==================== 引脚定义（按你的实际接线改） ====================
#define PIN_RELAY        5    // 继电器控制
#define PIN_DOOR_SW      18   // 箱门微动开关（INPUT_PULLUP）
#define PIN_LOCK_FB      21   // 锁舌反馈线（INPUT_PULLUP）
#define PIN_PHOTO_TRIG   19   // 拍照触发（预留）

// ==================== 参数常量 ====================
#define UNLOCK_TIME_MS   800   // 电磁锁通电时间
#define REPORT_INTERVAL  100   // POS帧上报周期（ms）
#define CMD_TIMEOUT_MS   1000  // 指令超时保护（ms）
#define DEBOUNCE_MS      50    // 按键/开关去抖时间

// ==================== 全局变量 ====================
// 接收到的NUC指令
int cmd_left_speed  = 0;
int cmd_right_speed = 0;
int cmd_lock        = 0;    // 你关心的：锁指令
int cmd_lid         = 0;    // 你不用
int cmd_photo       = 0;    // 预留

// 状态变量
int door_state      = 1;    // 0=门关，1=门开（从微动开关读）
int lock_fb_state   = 1;    // 0=锁舌缩回（解锁），1=锁舌伸出（锁闭）
int lock_state      = 1;    // 综合锁状态（0=解锁，1=锁闭）

// 通信
String input_buffer = "";
bool cmd_received   = false;
unsigned long last_cmd_time    = 0;
unsigned long last_report_time = 0;

// 模拟数据（待E1、E5同事提供真实变量后替换）
int32_t enc_left    = 0;
int32_t enc_right   = 0;
int16_t temperature = 255;    // 25.5℃
int16_t humidity    = 600;    // 60.0%
uint16_t battery    = 12000;  // 12V in mV


// ==================== 函数声明 ====================
void unlock();
void read_door_switch();
void read_lock_feedback();
void update_lock_state();
void send_pos_frame();
void parse_ctrl_frame(String frame);
void check_cmd_timeout();
void trigger_photo();


// ==================== 初始化 ====================
void setup() {
    Serial.begin(115200);
    delay(100);  // 等串口稳定
    
    // 初始化引脚
    pinMode(PIN_RELAY, OUTPUT);
    pinMode(PIN_DOOR_SW, INPUT_PULLUP);
    pinMode(PIN_LOCK_FB, INPUT_PULLUP);
    pinMode(PIN_PHOTO_TRIG, OUTPUT);
    
    // 初始状态
    digitalWrite(PIN_RELAY, HIGH);
    digitalWrite(PIN_PHOTO_TRIG, LOW);
    
    // // 读取初始状态
    // read_door_switch();
    // read_lock_feedback();
    // update_lock_state();

     // ===== 测试模式：手动指定初始状态 =====
    door_state    = LOW;   // 假设门关闭
    lock_fb_state = HIGH;  // 假设锁舌伸出（锁闭）
    lock_state    = 1;     // 强制锁闭
    
    // 启动信息
    Serial.println("=== BioShuttle E3E4 Module ===");
    Serial.print("Door: ");  Serial.println(door_state == LOW ? "CLOSED" : "OPEN");
    Serial.print("Lock FB: "); Serial.println(lock_fb_state == LOW ? "RETRACTED" : "EXTENDED");
    Serial.print("Lock State: "); Serial.println(lock_state == 1 ? "LOCKED" : "UNLOCKED");
    Serial.println("=============================");
    
    last_cmd_time = millis();
    last_report_time = millis();
}


// ==================== 主循环 ====================
void loop() {
    // 1. 接收串口指令
    while (Serial.available() > 0) {
        char c = Serial.read();
        if (c == '\n') {
            parse_ctrl_frame(input_buffer);
            input_buffer = "";
            cmd_received = true;
            last_cmd_time = millis();
        } else {
            input_buffer += c;
        }
    }
    
    // 2. 处理指令
    if (cmd_received) {
        cmd_received = false;
        
        // 开锁指令
        if (cmd_lock == 1 && lock_state == 1) {
            unlock();
        }
        
        // 拍照预留
        if (cmd_photo == 1) {
            trigger_photo();
        }
    }
    
    // // 3. 读取传感器
    // read_door_switch();
    // read_lock_feedback();
    // update_lock_state();
    
    // 4. 定时上报
    if (millis() - last_report_time >= REPORT_INTERVAL) {
        send_pos_frame();
        last_report_time = millis();
    }
    
    // 5. 超时保护
    check_cmd_timeout();
}


// ==================== 功能函数 ====================

// 开锁
// void unlock() {
//     Serial.println("[ACTION] Unlocking...");
//     lock_state = 0;    
//     digitalWrite(PIN_RELAY, LOW);
//     delay(UNLOCK_TIME_MS);
//     digitalWrite(PIN_RELAY, HIGH);
    
//     Serial.println("[ACTION] Unlock pulse done");
//     // 注意：lock_state 会在 update_lock_state() 里根据锁反馈线自动更新

// }

void unlock() {
    Serial.println("[ACTION] Unlocking...");
    lock_state = 0;    
    Serial.println("[DEBUG] before relay LOW");
    digitalWrite(PIN_RELAY, LOW);
    Serial.println("[DEBUG] relay LOW, before delay");
    delay(UNLOCK_TIME_MS);
    Serial.println("[DEBUG] after delay, before relay HIGH");
    digitalWrite(PIN_RELAY, HIGH);
    Serial.println("[ACTION] Unlock pulse done");
}



// 读箱门微动开关（去抖）
void read_door_switch() {
    static int last_raw = -1;
    static unsigned long last_change = 0;
    
    int raw = digitalRead(PIN_DOOR_SW);
    
    if (raw != last_raw) {
        last_change = millis();
        last_raw = raw;
    }
    
    if (millis() - last_change > DEBOUNCE_MS) {
        door_state = raw;  // LOW=门关，HIGH=门开
    }
}

// 读锁舌反馈线（去抖）
void read_lock_feedback() {
    static int last_raw = -1;
    static unsigned long last_change = 0;
    
    int raw = digitalRead(PIN_LOCK_FB);
    
    if (raw != last_raw) {
        last_change = millis();
        last_raw = raw;
    }
    
    if (millis() - last_change > DEBOUNCE_MS) {
        lock_fb_state = raw;  // LOW=锁舌缩回（解锁），HIGH=锁舌伸出（锁闭）
    }
}

// 综合判断锁状态
void update_lock_state() {
    // 锁舌伸出 + 门关闭 = 真正锁好
    // 锁舌缩回 = 已解锁
    if (lock_fb_state == LOW) {
        lock_state = 0;  // 锁舌缩回，确定解锁
    } else if (lock_fb_state == HIGH && door_state == LOW) {
        lock_state = 1;  // 锁舌伸出 + 门关闭 = 锁好
    } else {
        // 锁舌伸出但门还开着 = 异常状态，保守上报锁闭
        lock_state = 1;
    }
}

// 发送POS帧
void send_pos_frame() {
    // 格式：POS,左编码器,右编码器,锁状态,温度,湿度,电量
    Serial.print("POS,");
    Serial.print(enc_left);   Serial.print(",");
    Serial.print(enc_right);  Serial.print(",");
    Serial.print(lock_state); Serial.print(",");
    Serial.print(temperature); Serial.print(",");
    Serial.print(humidity);   Serial.print(",");
    Serial.println(battery);
}

// 解析CTRL帧
void parse_ctrl_frame(String frame) {
    if (!frame.startsWith("CTRL,")) {
        return;  // 不是控制帧，忽略
    }
    
    String data = frame.substring(5);
    int values[5] = {0, 0, 0, 0, 0};
    int idx = 0;
    int last = -1;
    
    for (int i = 0; i < data.length() && idx < 5; i++) {
        if (data[i] == ',' || i == data.length() - 1) {
            int end = (data[i] == ',') ? i : i + 1;
            values[idx++] = data.substring(last + 1, end).toInt();
            last = i;
        }
    }
    
    cmd_left_speed  = values[0];
    cmd_right_speed = values[1];
    cmd_lock        = values[2];
    cmd_lid         = values[3];
    cmd_photo       = values[4];
    
    Serial.print("[CMD] lock=");
    Serial.print(cmd_lock);
    Serial.print(" photo=");
    Serial.println(cmd_photo);
}

// 指令超时保护
void check_cmd_timeout() {
    if (millis() - last_cmd_time > CMD_TIMEOUT_MS) {
        // 超过1秒没收到指令
        // 你的模块不需要急停，但如果需要可以加保护逻辑
    }
}

// 拍照触发（预留）
void trigger_photo() {
    Serial.println("[PHOTO] Trigger pulse");
    digitalWrite(PIN_PHOTO_TRIG, HIGH);
    delay(100);
    digitalWrite(PIN_PHOTO_TRIG, LOW);
}