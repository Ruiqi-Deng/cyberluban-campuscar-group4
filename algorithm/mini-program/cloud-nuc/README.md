# 生物样品接驳联调版 v2

这套代码保留原 API 的主要入口，并补上原先缺失的“云端命令队列 → NUC 拉取 →
设备动作 → 状态/照片回传”。云端不再直接访问串口，任务使用 SQLite 持久化。

## 一天半内的验收边界

1. A 在小程序填写样品名称、温湿度要求、起点和终点，调用 `POST /api/tasks`。
2. 云端返回 `sample_code`（样品编码）和四位 `pickup_code`（取件码）。
3. NUC 拉取 `run_delivery` 命令。底盘未跑通期间用 `BIOSHUTTLE_DRY_RUN=1` 和短延时模拟到站；
   ESP32、相机协议确认后改为真实模式。
4. 起点动作：开锁 → 拍照 → 等待放样 → 闭锁 → 拍照。
5. 任务进入 `awaiting_pickup`。
6. B 输入样品编码和取件码，调用 `POST /api/pickup`；验证通过后云端向 NUC 下发
   `release_sample`。
7. 终点动作：开锁 → 拍照 → 等待取样 → 闭锁 → 拍照，状态变为 `completed`。

## 腾讯云部署

```bash
cd /opt/bioshuttle
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-cloud.txt
export BIOSHUTTLE_ROBOT_TOKEN='请换成一段随机长字符串'
export BIOSHUTTLE_CORS_ORIGINS='https://你的正式域名'
uvicorn cloud_main:app --host 0.0.0.0 --port 8000
```

联调阶段可先访问 `http://服务器IP:8000/docs`。微信真机正式请求通常需要已备案 HTTPS 域名，
并在微信公众平台配置 request 合法域名；开发者工具临时联调可关闭“校验合法域名”。不要把
8000 端口长期直接暴露，正式演示前应由 Nginx/Caddy 提供 HTTPS。

## NUC 部署

```bash
cd ~/bioshuttle
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-nuc.txt
export BIOSHUTTLE_CLOUD_URL='http://111.230.241.59:8000'
export BIOSHUTTLE_ROBOT_TOKEN='与云端完全相同'
export BIOSHUTTLE_ESP32_PORT='/dev/ttyUSB0'
export BIOSHUTTLE_RTK_PORT='/dev/ttyACM3'
export BIOSHUTTLE_DRY_RUN=1
python3 nuc_agent.py
```

`DRY_RUN=1` 会真实上传 RTK/ESP32 遥测并跑完整状态机，但不会向锁发送命令；四张“照片”会用
文本证据代替。这适合今天先跑通软件闭环。

已从 ESP32 固件确认：`CTRL,0,0,1,0,0` 是开锁命令；当前机械锁没有关锁命令，
人合上箱门后锁舌自动复位，NUC 等待 `POS` 帧中的 `lock_status` 从 `0` 回到 `1`。
真实硬件模式只需要配置相机抓拍命令：

```bash
export BIOSHUTTLE_DRY_RUN=0
export BIOSHUTTLE_LOCK_OPEN_COMMAND='CTRL,0,0,1,0,0'
export BIOSHUTTLE_CAMERA_COMMAND='python3 /home/hkust-gz-nuc/bioshuttle/capture_photo.py --camera 0 --output {output}'
python3 nuc_agent.py
```

程序在真实模式缺少相机配置时会保护退出，开锁或锁闭反馈超过 60 秒也会停止当前任务并上报失败。
`nuc_agent.py` 对 ESP32 使用单一持久
串口，读传感器和写锁命令共用互斥锁，避免原代码同时两次打开 `/dev/ttyUSB0`。

## 小程序请求格式

创建寄件：

```javascript
wx.request({
  url: API_BASE + '/api/tasks',
  method: 'POST',
  data: {
    sample_name: '血清样品',
    temp_humidity: '2–8°C，湿度≤60%',
    sender_id: 'A',
    origin: { name: '实验楼A', latitude: 22.8923, longitude: 113.4760 },
    target: { name: '实验楼B', latitude: 22.8930, longitude: 113.4770 }
  },
  success: ({data}) => {
    // 展示并保存 data.sample_code 和 data.pickup_code
  }
})
```

终点取件：

```javascript
wx.request({
  url: API_BASE + '/api/pickup',
  method: 'POST',
  data: { sample_code, pickup_code },
  success: ({data}) => wx.showToast({ title: data.message, icon: 'none' })
})
```

查询状态：`GET /api/tasks/{sample_code}`；机器人总状态：`GET /api/robot/status`。

## 立即需要补齐的现场信息

- 请上传微信项目源目录 `C:\\Users\\cmm22\\WeChatProjects\\miniprogram-1` 中的
  `app.js`、`app.json`、`project.config.json`、`utils/` 和相关 `pages/`。不要修改
  `WeappSimulator/.../WeappFileSystem` 下的缓存副本。
- 在 NUC 上先执行 `python3 capture_photo.py --camera 0 --output /tmp/camera-test.jpg`；如果失败，
  再把 `--camera 0` 改成 `--camera 1`。确认当前 OpenCV 驱动能否读取相机。若 Hikrobot GigE
  相机没有映射成 VideoCapture 设备，则还需把
  `capture_photo.py` 的内部实现替换成 MVS SDK 抓拍，但 NUC agent 的调用接口不需要再改。

## 快速 API 手工测试

```bash
curl -s http://服务器IP:8000/
curl -s -X POST http://服务器IP:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"sample_name":"血清","temp_humidity":"2-8C","sender_id":"A","origin":{"name":"A点","latitude":22.89,"longitude":113.47},"target":{"name":"B点","latitude":22.90,"longitude":113.48}}'
```

记录返回的两个编码。启动 NUC agent 后查询任务，状态应到 `awaiting_pickup`；再用：

```bash
curl -s -X POST http://服务器IP:8000/api/pickup \
  -H 'Content-Type: application/json' \
  -d '{"sample_code":"返回的样品编码","pickup_code":"返回的取件码"}'
```

最终状态应为 `completed`，任务详情中应有起点和终点共四条 evidence 记录。
