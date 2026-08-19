import cv2
import serial
import os
import time
import threading
from datetime import datetime
from flask import Flask, jsonify

# ====== 配置区域（只需改这里）======
CAMERA_INDEX = 0        # 工业摄像头编号
SERIAL_PORT  = "COM4"   # ESP32的COM口号，在设备管理器里确认
BAUD_RATE    = 115200   # 波特率，必须和ESP32代码里Serial.begin()一致
SAVE_FOLDER  = os.path.join(os.path.expanduser("~"), "Pictures", "CameraCapture")
HTTP_PORT    = 5000     # 小程序发开锁请求的端口号

# 防止 HTTP 触发拍照 和 串口监听触发拍照 在同一次开/关锁动作中重复拍照。
# HTTP 触发拍照后，这个时间窗口（秒）内，串口监听检测到对应方向的状态跳变
# 就不会再拍一次。
PHOTO_DEDUPE_WINDOW_SEC = 2.0
# ====================================

app = Flask(__name__)
ser = None

# lock_state 统一语义（与 ESP32 固件一致）：0 = 锁闭，1 = 解锁
last_lock_state = -1

# 记录最近一次由 HTTP 主动触发的拍照方向及时间，用于和串口监听去重
# reason: "开锁" 或 "关锁"
last_http_trigger = {"reason": None, "time": 0.0}
trigger_lock = threading.Lock()

# ============================================================
# 工具函数
# ============================================================

def ensure_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"[系统] 已创建文件夹: {path}")

def take_photo(reason=""):
    """调用工业摄像头拍照并保存"""
    print(f"[拍照] 开始拍照，原因:{reason}")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("[错误] 无法打开摄像头，请检查编号或是否被占用")
        return None

    for _ in range(10):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("[错误] 拍照失败，未能读取到画面")
        return None

    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    filepath = os.path.join(SAVE_FOLDER, filename)
    cv2.imwrite(filepath, frame)
    print(f"[拍照成功] 原因:{reason} 已保存到: {filepath}")
    return filepath

def try_photo_from_serial(reason):
    """
    串口监听检测到状态跳变时，尝试拍照。
    如果最近 PHOTO_DEDUPE_WINDOW_SEC 秒内 HTTP 接口已经因为同样的原因
    触发过一次拍照，这里就跳过，避免同一次动作拍两张。
    """
    with trigger_lock:
        recent = (
            last_http_trigger["reason"] == reason
            and (time.time() - last_http_trigger["time"]) < PHOTO_DEDUPE_WINDOW_SEC
        )
    if recent:
        print(f"[去重] HTTP 已触发过一次「{reason}」拍照，跳过串口重复触发")
        return
    threading.Thread(target=take_photo, args=(reason,), daemon=True).start()

def mark_http_trigger(reason):
    with trigger_lock:
        last_http_trigger["reason"] = reason
        last_http_trigger["time"] = time.time()

# ============================================================
# 解析POS帧
# ============================================================

def parse_pos_frame(line):
    try:
        parts = line.split(",")
        if len(parts) != 7 or parts[0] != "POS":
            return None
        return {
            "enc_left":    int(parts[1]),
            "enc_right":   int(parts[2]),
            "lock_state":  int(parts[3]),
            "temperature": int(parts[4]),
            "humidity":    int(parts[5]),
            "battery":     int(parts[6]),
        }
    except Exception:
        return None

# ============================================================
# 场景1：监听串口
# lock_state 统一语义：0 = 解锁，1 = 锁闭（与 ESP32 固件一致）
# 两个方向的跳变都需要触发拍照
# ============================================================

def serial_listener():
    global ser, last_lock_state

    print(f"[串口] 正在连接 {SERIAL_PORT}，波特率 {BAUD_RATE}...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        print(f"[串口] 连接成功，开始监听...\n")
    except Exception as e:
        print(f"[错误] 串口打开失败: {e}")
        print("请检查：1.COM口号是否正确  2.ESP32是否插好  3.是否被其他程序占用")
        return

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            # 打印ESP32的调试信息
            if line.startswith("[") or line.startswith("==="):
                print(f"[ESP32] {line}")
                continue

            # 解析POS帧
            data = parse_pos_frame(line)
            if data is None:
                print(f"[忽略] 无法解析: {line}")
                continue

            current_lock = data["lock_state"]

            # 开锁：1→0（锁闭→解锁）
            if last_lock_state == 1 and current_lock == 0:
                print(f"[检测] 锁状态变化：锁闭→解锁，触发拍照")
                try_photo_from_serial("开锁")

            # 关锁：0→1（解锁→锁闭）
            if last_lock_state == 0 and current_lock == 1:
                print(f"[检测] 锁状态变化：解锁→锁闭，触发拍照")
                try_photo_from_serial("关锁")

            last_lock_state = current_lock

        except Exception as e:
            print(f"[异常] 串口读取出错: {e}")
            break

# ============================================================
# 场景2：HTTP服务器
# /unlock  发开锁指令后300ms直接触发拍照，不依赖ESP32回传
# /lock    关锁是机械弹簧复位，ESP32没有关锁指令，收到通知直接拍照
# 两者都会标记触发时间，供串口监听去重
# ============================================================

@app.route("/unlock", methods=["POST"])
def handle_unlock():
    global ser
    if ser is None or not ser.is_open:
        return jsonify({"status": "error", "message": "串口未连接"}), 500
    try:
        ser.write(b"CTRL,0,0,1,0,0\n")
        print("[动作] 收到小程序开锁请求，已发送 CTRL,0,0,1,0,0 给ESP32")
        mark_http_trigger("开锁")
        # 发完指令300ms后拍照，等待锁弹开
        threading.Timer(0.3, take_photo, args=("开锁",)).start()
        return jsonify({"status": "ok", "message": "开锁指令已发送"}), 200
    except Exception as e:
        print(f"[错误] 发送开锁指令失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/lock", methods=["POST"])
def handle_lock():
    """
    关锁是机械弹簧复位，ESP32 固件没有"关锁指令"，
    所以这里不发串口指令，只在小程序确认关锁动作后直接拍照。
    """
    try:
        print("[动作] 收到小程序关锁通知")
        mark_http_trigger("关锁")
        # 给锁舌复位留一点时间再拍照
        threading.Timer(0.3, take_photo, args=("关锁",)).start()
        return jsonify({"status": "ok", "message": "已记录关锁并触发拍照"}), 200
    except Exception as e:
        print(f"[错误] 处理关锁请求失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def handle_status():
    global last_lock_state
    return jsonify({
        "status":     "ok",
        "serial":     SERIAL_PORT,
        "camera":     CAMERA_INDEX,
        "lock_state": last_lock_state  # 0=锁闭，1=解锁
    }), 200

# ============================================================
# 主程序入口
# ============================================================

if __name__ == "__main__":
    ensure_folder(SAVE_FOLDER)

    serial_thread = threading.Thread(target=serial_listener, daemon=True)
    serial_thread.start()

    print(f"[HTTP] 接口已启动，监听端口 {HTTP_PORT}")
    print(f"[HTTP] 开锁请求地址: POST http://[本机IP]:{HTTP_PORT}/unlock")
    print(f"[HTTP] 关锁通知地址: POST http://[本机IP]:{HTTP_PORT}/lock")
    print(f"[HTTP] 状态检查地址: GET  http://[本机IP]:{HTTP_PORT}/status\n")

    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False)