# BioShuttle 本轮交付说明

## 目录

- `miniprogram-1-cloud/`：已改为访问腾讯云 API 的微信小程序源代码。
- `cloud-nuc/`：腾讯云 `cloud_main.py`、NUC `nuc_agent.py`、单次抓拍程序和测试。

## 先后顺序

1. 腾讯云先部署 `cloud-nuc/cloud_main.py`。
2. NUC 先以 `BIOSHUTTLE_DRY_RUN=1` 启动 `cloud-nuc/nuc_agent.py`。
3. 微信开发者工具导入 `miniprogram-1-cloud/`，关闭开发阶段的合法域名校验，完成一次寄件和取件。
4. 在 NUC 单独测试相机：

   ```bash
   python3 capture_photo.py --camera 0 --output /tmp/camera-test.jpg
   ```

   失败时改试 `--camera 1`。
5. 确认 `/tmp/camera-test.jpg` 正常、ESP32 的 `POS` 锁状态能在开锁后变为 `0`、合门后变回 `1`，
   再切换 `BIOSHUTTLE_DRY_RUN=0`。

## 已确认的锁协议

- 串口：115200，当前 NUC 配置 `/dev/ttyUSB0`。
- 开锁：`CTRL,0,0,1,0,0\n`。
- `POS` 第四列：`0=解锁`，`1=锁闭`。
- 没有关锁命令：寄件人或取件人合门，机械锁舌复位；NUC 等待真实反馈后拍摄“闭锁后”照片。

完整部署命令和 API 格式见 `cloud-nuc/README.md`。
