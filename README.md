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
```text
cyberluban-campuscar-group4/
├─algorithm
│  ├─camera
│  ├─mini-program
│  │  ├─cloud-nuc
│  │  └─miniprogram-1-cloud
│  │      ├─pages
│  │      │  ├─index
│  │      │  ├─logs
│  │      │  └─work
│  │      └─utils
│  ├─rtk
│  │  ├─cyber绠楁硶wjh閮ㄧ讲code
│  │  │  ├─A3 RTK
│  │  │  ├─A4鐘舵€佹満
│  │  │  │  └─bioshuttle_a4
│  │  │  │      ├─bioshuttle_a4
│  │  │  │      ├─launch
│  │  │  │      ├─resource
│  │  │  │      └─test
│  │  │  └─A5 涓插彛閫氫俊
│  │  └─__MACOSX
│  │      └─cyber绠楁硶wjh閮ㄧ讲code
│  │          ├─A3 RTK
│  │          ├─A4鐘舵€佹満
│  │          │  └─bioshuttle_a4
│  │          │      ├─bioshuttle_a4
│  │          │      ├─launch
│  │          │      ├─resource
│  │          │      └─test
│  │          └─A5 涓插彛閫氫俊
│  └─simulation
│      ├─bioshuttle_sim
│      │  ├─config
│      │  ├─launch
│      │  ├─scripts
│      │  ├─urdf
│      │  └─worlds
│      ├─docker
│      └─scripts
├─docs
│  ├─protocols
│  └─测试记录
│      ├─rtk天线
│      │  └─images
│      ├─小程序前端调试
│      │  └─images
│      ├─电子锁+温湿度传感器
│      │  └─images
│      └─相机模块
│          └─images
├─embedded
│  ├─Chassis_Drive
│  │  └─campusCar-new-stm32-hikrobot
│  │      ├─.claude
│  │      ├─.codex
│  │      ├─.codex-memory
│  │      │  └─systems
│  │      ├─.git
│  │      │  ├─hooks
│  │      │  ├─info
│  │      │  ├─logs
│  │      │  │  └─refs
│  │      │  │      └─heads
│  │      │  │          ├─codex
│  │      │  │          └─hardware
│  │      │  ├─objects
│  │      │  │  ├─info
│  │      │  │  └─pack
│  │      │  └─refs
│  │      │      ├─heads
│  │      │      │  ├─codex
│  │      │      │  └─hardware
│  │      │      └─tags
│  │      ├─.github
│  │      │  └─instructions
│  │      ├─.vscode
│  │      ├─config
│  │      │  └─profiles
│  │      ├─docker
│  │      ├─docs
│  │      ├─hardware
│  │      │  └─hoverboard_driver
│  │      │      ├─.github
│  │      │      │  └─workflows
│  │      │      ├─bringup
│  │      │      │  ├─config
│  │      │      │  └─launch
│  │      │      ├─description
│  │      │      │  ├─launch
│  │      │      │  ├─ros2_control
│  │      │      │  └─urdf
│  │      │      ├─doc
│  │      │      └─hardware
│  │      │          └─include
│  │      │              └─hoverboard_driver
│  │      ├─scripts
│  │      ├─src
│  │      │  └─rtk_tools
│  │      │      └─core
│  │      └─_forks
│  ├─Electronic Lock
│  │  ├─.pio
│  │  │  └─build
│  │  │      └─esp32dev
│  │  │          ├─FrameworkArduino
│  │  │          │  └─libb64
│  │  │          └─src
│  │  ├─.vscode
│  │  ├─include
│  │  ├─lib
│  │  ├─src
│  │  └─test
│  ├─Integrated Test
│  │  └─bioshuttle-sensors
│  │      ├─.vscode
│  │      └─src
│  └─Temperature_Humidity
│      ├─include
│      └─src
└─mechanical
    ├─CAD
    └─Images
```
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
