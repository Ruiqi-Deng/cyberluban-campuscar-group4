import cv2
import os
import time
import threading
from datetime import datetime
from flask import Flask, jsonify

# ====== 配置区域（只需改这里）======
CAMERA_INDEX = 0        # 摄像头编号 (Linux下通常为0，对应/dev/video0)
SAVE_FOLDER = os.path.join(os.path.expanduser("~"), "Pictures", "CameraCapture")
HTTP_PORT = 5002        # HTTP服务监听端口
# ====================================

app = Flask(__name__)

# ============================================================
# 工具函数
# ============================================================

def ensure_folder(path):
    """确保存储目录存在"""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        print(f"[系统] 已创建照片存储文件夹: {path}")

def take_photo(reason=""):
    """
    调用摄像头拍照并保存
    注意：Linux下优先使用 V4L2 后端
    """
    print(f"[拍照] 开始拍照，原因: {reason}")
    
    # Linux下必须使用 CAP_V4L2 或不指定后端
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    
    if not cap.isOpened():
        # 尝试不带后端参数再次打开，增加兼容性
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            print("[错误] 无法打开摄像头，请检查 CAMERA_INDEX 或 USB 连接")
            return None

    # 工业相机/普通摄像头预热：连续读取并丢弃前几帧，防止曝光不足或黑屏
    for _ in range(15):
        cap.read()
        time.sleep(0.03)

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print("[错误] 拍照失败，未能从摄像头读取到有效画面")
        return None

    # 生成带时间戳的文件名
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    filepath = os.path.join(SAVE_FOLDER, filename)
    
    # 保存照片
    success = cv2.imwrite(filepath, frame)
    if success:
        print(f"[拍照成功] 原因: {reason} | 已保存至: {filepath}")
        return filepath
    else:
        print(f"[错误] 文件写入失败: {filepath}")
        return None

# ============================================================
# HTTP 接口
# 负责接收外部指令，直接控制摄像头拍照
# ============================================================

@app.route("/capture", methods=["POST"])
def handle_capture():
    """
    触发拍照接口
    在子线程中拍照，避免阻塞 HTTP 响应
    """
    try:
        print("[动作] 收到拍照请求")
        threading.Thread(target=take_photo, args=("HTTP手动触发",), daemon=True).start()
        return jsonify({"status": "ok", "message": "拍照指令已接收，正在处理"}), 200
    except Exception as e:
        print(f"[错误] 拍照流程异常: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def handle_status():
    """
    服务状态查询接口
    """
    return jsonify({
        "status": "ok",
        "camera_index": CAMERA_INDEX,
        "save_folder": SAVE_FOLDER
    }), 200

# ============================================================
# 主程序入口
# ============================================================

if __name__ == "__main__":
    ensure_folder(SAVE_FOLDER)

    print("=" * 50)
    print(f"[HTTP] 服务已启动，监听端口: {HTTP_PORT}")
    print(f"[HTTP] 拍照接口: POST http://<本机IP>:{HTTP_PORT}/capture")
    print(f"[HTTP] 状态查询: GET  http://<本机IP>:{HTTP_PORT}/status")
    print("=" * 50 + "\n")

    # 启动 Flask 服务
    app.run(host="0.0.0.0", port=HTTP_PORT, debug=False, use_reloader=False)

