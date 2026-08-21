# BioShuttle：生物样本校内外智能接驳机器人

> 🏆 Cyber鲁班2026校园智能机器人 · 第4组


## 📌 项目简介

BioShuttle 是一套面向校园实验室的生物样本无人化接驳系统，实现生物样品从**实验室门口到校门口接驳点**的闭环运输，解决生物样本校内外接驳的真实痛点。

本项目基于校园无人小车平台，搭载NUC计算单元、ESP32底层控制器、RTK定位模块及多种传感器，构建完整的智能接驳系统。


## ✨ 已完成功能

| 模块 | 功能说明 | 状态 |
|------|----------|------|
| 温湿度监测 | DHT22 实时采集箱内温湿度 | ✅ 已完成 |
| 电子锁控制 | 远程开锁/关锁，状态实时反馈 | ✅ 已完成 |
| 交接拍照 | 开锁/关锁时自动触发相机拍照留证 | ✅ 已完成 |
| 串口通信 | NUC ↔ ESP32 双向通信（CTRL/POS帧） | ✅ 已完成 |
| 状态机 | 状态流转（IDLE→PICKUP→TRANSIT→HANDOVER→RETURN） | ✅ 已完成 |
| RTK定位 | NMEA协议解析，pynmea2库验证通过 | ✅ 逻辑验证完成 |
| 小程序 | 寄件、取件、物流看板三大页面 | ✅ 已完成 |
| 箱体建模 | SolidWorks 3D模型设计 | ✅ 已完成 |


## 🛠️ 核心硬件

| 硬件 | 型号 | 用途 |
|------|------|------|
| 核心计算 | ASUS NUC 14 Essential | 运行ROS2、状态机、串口通信 |
| 定位模块 | RTK + 天线 | 定位 |
| 底层控制 | ESP32 | 电子锁、温湿度传感器、继电器 |
| 视觉相机 | 工业相机 | 交接拍照留证 |
| 温湿度传感器 | DHT22 | 箱内温湿度监测 |
| 电磁锁 | 12V插销锁 | 箱体锁闭控制 |
| 继电器模块 | 5V/12V 2路 | 电磁锁驱动 |


## 📁 目录结构

cyberluban-campuscar-group4/
├── README.md
│
├── algorithm/                         # 算法组代码
│   ├── camera/
│   │   └── camera_serial_v2.py
│   └── rtk/                           # RTK与状态机
│       ├── cyber算法wjh部分code/
│       │   ├── A3 RTK/
│       │   │   └── A3_rtk_standalone.py
│       │   ├── A4状态机/
│       │   │   └── bioshuttle_a4/
│       │   │       ├── package.xml
│       │   │       ├── README.md
│       │   │       ├── setup.cfg
│       │   │       ├── setup.py
│       │   │       ├── bioshuttle_a4/
│       │   │       │   ├── scenario_test_node.py
│       │   │       │   ├── state_machine_core.py
│       │   │       │   ├── state_machine_node.py
│       │   │       │   └── __init__.py
│       │   │       ├── launch/
│       │   │       │   └── a4_state_machine.launch.py
│       │   │       ├── resource/
│       │   │       │   └── bioshuttle_a4
│       │   │       └── test/
│       │   │           └── test_state_machine_core.py
│       │   └── A5 串口通信/
│       │       └── A5_serial_comm_nuc.py
│       └── __MACOSX/                   # macOS 系统元数据文件夹，可删除
│
├── docs/                               # 项目文档
│   ├── protocols/                      # 协议文档（当前为空）
│   └── 测试记录/                       # 所有测试日志
│       ├── rtk天线/
│       │   ├── rtk天线测试记录.md
│       │   └── images/
│       │       ├── rtk_数据传送.png
│       │       ├── 串口通信_POS帧.png
│       │       └── 状态机_状态流转截图.png
│       ├── 小程序前端调试/
│       │   ├── 小程序调试记录.md
│       │   └── images/
│       │       ├── 小程序展示1.png
│       │       ├── 小程序展示2.png
│       │       └── 小程序展示3.png
│       ├── 电子锁+温湿度传感器/
│       │   ├── 电子锁+温湿度传感器联调记录.md
│       │   └── images/
│       │       ├── 电子锁与温湿度传感器联调1.png
│       │       └── 电子锁与温湿度传感器联调2.png
│       └── 相机模块/
│           ├── 相机模块测试记录.md
│           └── images/
│               └── 相机模块调试记录.jpg
│
├── embedded/                           # 电控组代码
│   ├── Chassis_Drive/                  # 底盘驱动（STM32）
│   │   └── campusCar-new-stm32-hikrobot/
│   │       ├── .gitignore
│   │       ├── .gitattributes
│   │       ├── AGENTS.md
│   │       ├── CLAUDE.md
│   │       ├── README.md
│   │       ├── esp32_pwm_gesture.ino
│   │       ├── mediamtx.yml
│   │       ├── PWM切换组合参数使用说明.md
│   │       ├── config/                 # 配置文件
│   │       ├── docker/                 # Docker相关
│   │       ├── docs/                   # 文档
│   │       ├── hardware/               # 硬件驱动（hoverboard）
│   │       ├── scripts/                # 启动脚本
│   │       ├── src/                    # Python源码
│   │       ├── _forks/                 # 外部依赖
│   │       └── ...（其他配置文件）
│   │
│   ├── Electronic Lock/                # 电子锁模块（ESP32）
│   │   ├── platformio.ini
│   │   ├── BioShuttle.code-workspace
│   │   ├── .gitignore
│   │   ├── src/
│   │   │   ├── main.cpp
│   │   │   └── camera_serial.py
│   │   ├── include/README
│   │   ├── lib/README
│   │   └── test/README
│   │
│   ├── Integrated Test/                # 集成测试
│   │   └── bioshuttle-sensors/
│   │       ├── platformio.ini
│   │       ├── README.md
│   │       ├── .gitignore
│   │       ├── unlock.py
│   │       ├── 电子锁使用说明.md
│   │       └── src/main.cpp
│   │
│   └── Temperature_Humidity/           # 温湿度模块（ESP32）
│       ├── include/
│       │   └── README.txt
│       └── src/
│           ├── main.cpp
│           └── platformio.ini
│
└── mechanical/                         # 机械组文件
    ├── CAD_files/                      # 3D模型源文件
    │   ├── 接驳车装配体.SLDASM
    │   ├── 接驳车装配体-工程图.SLDDRW
    │   ├── 箱体.SLDPRT
    │   ├── 箱盖.SLDPRT
    │   ├── 电子锁锁体.SLDPRT
    │   ├── 电子锁锁扣.SLDPRT
    │   ├── 温湿度传感器.SLDPRT
    │   ├── 相机.SLDPRT
    │   ├── 合页夹.SLDPRT
    │   ├── 铰链合页装配体.sldasm
    │   ├── 转轴.SLDPRT
    │   └── 四驱车.SLDPRT
    └── Images/                         # sw建模截图
        ├── Overall-1.png
        ├── Overall-2.png
        ├── Overall-3.png
        ├── Overall-4.png
        └── Drawing-Document.png

## 硬件连接说明

| 模块 | 主控 | 关键引脚 |
|------|------|----------|
| 温湿度传感器（DHT22） | ESP32 | GPIO27 |
| 电子锁（继电器） | ESP32 | GPIO5 |
| 相机 | NUC | USB |
| RTK 天线 | NUC | USB |
| 底盘驱动 | STM32 | USB / UART |

## 电源供电情况

系统采用 36V 动力锂电池作为总电源，一分为三分别供电：

| 分支 | 电压转换 | 供电对象 |
|------|----------|----------|
| 分支1 | 36V → 19V（降压模块） | NUC 14 Essential |
| 分支2 | 36V → 12V（降压模块） | 电子锁 |
| 分支3 | 36V 直供 | 底盘驱动（STM32 / 电机） |

其余模块通过 USB 接口由 NUC 或 ESP32 供电：

| 模块 | 供电方式 | 说明 |
|------|----------|------|
| ESP32 | NUC USB | 同时承担串口通信 |
| RTK 天线 | NUC USB | 定位数据回传 |
| 相机 | NUC USB | 拍照留证 |
