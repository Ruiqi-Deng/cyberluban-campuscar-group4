# 打开方法（发给队友）

这是 BioShuttle 已联调成功的工程：AM2301 温湿度 + 电子锁。

## 你怎么用

1. 解压到一个**纯英文路径**，例如 `D:\bioshuttle-sensors`。不要解压到带中文的文件夹。
2. 安装 VSCode 插件 **PlatformIO IDE**。
3. VSCode：文件 → 打开文件夹 → 选这个解压出来的文件夹（能看到 `platformio.ini`）。
4. 把 ESP32 插上 USB。
5. 若烧录失败，打开 `platformio.ini`，把 `COM7` 改成你电脑设备管理器里的串口号。
6. 底部：对勾 Build → 右箭头 Upload → 插头 Monitor。
7. 看到 `[OK] AM2301 ...` 即传感器成功。
8. 测开锁：关掉 Monitor，在本文件夹运行 `python -m pip install pyserial` 然后 `python unlock.py`（同样改脚本里的 COM 口）。

接线、协议见 `电子锁使用说明.md`。
