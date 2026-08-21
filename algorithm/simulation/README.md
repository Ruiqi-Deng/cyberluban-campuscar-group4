# BioShuttle V2 仿真环境

本目录提供与实车工程隔离的 ROS 2 Humble + Gazebo Classic 11 仿真。它不会加载 STM32 串口驱动，也不会访问 `/dev/ttyUSB0`。仿真默认使用 `ROS_DOMAIN_ID=42`，避免与同一网络中实车的 ROS 2 节点互相发现。

## 已搭建内容

- 四轮两侧联动差速底盘：四个物理轮，Gazebo 用两组轮对模拟左右两个电机。
- 实车尺寸：车体 `0.60 × 0.45 m`、轮径 `0.165 m`、前后轴相对中心 `±0.20 m`。
- 校园场景：实验室取件区、十字路口、校门交接区、GPS 弱信号棚、静态障碍物和标志板。
- 传感器：二维激光雷达、RGB 相机、IMU、三个超声波/红外等效距离传感器、合成 GPS。
- 定位接口：轮速里程计、IMU、GPS、合成 AprilTag 位姿，以及可选 `robot_localization` 配置。
- 七状态机：`IDLE / PICKUP / TRANSIT / AVOID / HANDOVER / RETURN / ERROR`。
- Windows/WSL2 安装脚本、Ubuntu 构建/启动/自检脚本，以及无界面 Docker 镜像。

当前阶段搭建的是“算法可开发、接口可测试”的仿真底座。`/apriltag/pose` 是基于仿真真值生成的定位观测，用于先测试定位源切换；它不代表真实相机 AprilTag 识别已经验收。实际视觉算法应再接入 `apriltag_ros` 并使用 `/camera/color/image_raw` 验证。

## 统一接口

| 功能 | 仿真话题 | 实车/算法用途 |
|---|---|---|
| 运动命令 | `/cmd_vel` (`geometry_msgs/Twist`) | 与实车一致 |
| 轮式里程计 | `/odom` | Nav2、定位融合 |
| 激光雷达 | `/scan` | 建图、避障、代价地图 |
| IMU | `/imu/data` | 姿态/里程计融合 |
| GPS | `/gps/fix` | 室外绝对定位 |
| GPS 可用性 | `/bioshuttle/gps_available` | 弱信号时切换 AprilTag |
| AprilTag 位姿 | `/apriltag/pose` | 室内/弱信号区绝对定位 |
| AprilTag 可见 | `/bioshuttle/apriltag_visible` | 定位源选择 |
| 前方距离 | `/range/front` | 超声波/红外避障 |
| 左前/右前距离 | `/range/front_left`、`/range/front_right` | 近距离避障 |
| RGB 图像 | `/camera/color/image_raw` | AprilTag、视觉算法 |
| 任务状态 | `/bioshuttle/state` | 七状态机输出 |
| 状态机命令 | `/bioshuttle/task_command` | 任务流程测试 |

## 推荐环境：游戏本 Windows 11 + WSL2 Ubuntu 22.04

当前这台游戏本有 `wsl.exe`，但尚未安装 Linux 发行版；Docker Desktop 也未安装。因此必须先完成一次 Windows 管理员安装，Gazebo 才能真正运行。

### 1. Windows 管理员 PowerShell

在开始菜单中右击 PowerShell，选择“以管理员身份运行”，然后执行：

```powershell
cd F:\campusCar-new-stm32-hikrobot
powershell -ExecutionPolicy Bypass -File .\simulation\scripts\setup_windows_wsl.ps1
```

如果 Windows 要求重启，先重启。随后从开始菜单打开 `Ubuntu 22.04`，按提示创建 Linux 用户名和密码。这个密码只用于 WSL 内部的 `sudo`。

### 2. Ubuntu 22.04（WSL）终端

下面命令全部在 Ubuntu 终端执行，不是在 Windows PowerShell，也不是在 NUC：

```bash
cd /mnt/f/campusCar-new-stm32-hikrobot
chmod +x simulation/scripts/*.sh
./simulation/scripts/install_wsl_humble.sh
./simulation/scripts/build_sim.sh
```

安装包含 ROS 2 Humble、Gazebo Classic、RViz2、Nav2、SLAM Toolbox、`robot_localization`、遥控工具和可用时的 `apriltag_ros`。

### 3. 启动仿真（Ubuntu/WSL 终端 1）

```bash
cd /mnt/f/campusCar-new-stm32-hikrobot
./simulation/scripts/run_sim.sh
```

正常情况下会同时打开 Gazebo 和 RViz。第一次启动较慢。若 WSLg/OpenGL 显示异常：

```bash
export LIBGL_ALWAYS_SOFTWARE=1
./simulation/scripts/run_sim.sh
```

只运行无界面仿真：

```bash
./simulation/scripts/run_sim.sh gui:=false rviz:=false
```

启用 GPS/里程计/IMU/AprilTag 融合输出：

```bash
./simulation/scripts/run_sim.sh localization_fusion:=true
```

这会额外发布 `/odometry/filtered`、`/odometry/gps` 和 `/odometry/global`。默认关闭是为了先把底盘和传感器逐项验收，避免一次启动过多节点掩盖问题。

### 4. 控制虚拟小车（Ubuntu/WSL 终端 2）

```bash
source /opt/ros/humble/setup.bash
source ~/bioshuttle_sim_ws/install/setup.bash
export ROS_DOMAIN_ID=42
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

也可以只发送一个低速前进命令：

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.10}, angular: {z: 0.0}}"
```

按 `Ctrl+C` 后立即发送停止：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 0.0}}"
```

### 5. 一键接口和运动自检（Ubuntu/WSL 终端 2）

仿真保持运行时执行：

```bash
cd /mnt/f/campusCar-new-stm32-hikrobot
./simulation/scripts/smoke_test.sh
```

自检确认所有核心话题存在，并让虚拟机器人以 `0.10 m/s` 前进 2 秒后停止。该脚本固定使用仿真域 `42`，不会向默认域中的实车发送命令。

## 七状态机测试

另开一个 Ubuntu/WSL 终端并完成 `source` 与 `ROS_DOMAIN_ID=42` 设置，然后按顺序执行：

```bash
ros2 topic echo /bioshuttle/state
```

在另一个终端发送事件：

```bash
ros2 topic pub --once /bioshuttle/task_command std_msgs/msg/String "{data: start}"
ros2 topic pub --once /bioshuttle/task_command std_msgs/msg/String "{data: picked_up}"
ros2 topic pub --once /bioshuttle/task_command std_msgs/msg/String "{data: handover}"
ros2 topic pub --once /bioshuttle/task_command std_msgs/msg/String "{data: return}"
ros2 topic pub --once /bioshuttle/task_command std_msgs/msg/String "{data: complete}"
```

当机器人处于 `PICKUP`、`TRANSIT` 或 `RETURN` 且前方 1 米内出现障碍时，状态自动切到 `AVOID`；障碍清除并观察 2 秒后恢复先前状态。状态机目前只负责决策状态，不直接抢占 `/cmd_vel`，后续应通过 Nav2 行为树或 `twist_mux` 实现强制停车。

## 场景中的定位切换测试

- 仿真原点附近为正常 GPS 区，`/bioshuttle/gps_available=true`。
- 机器人进入 `x=2.75~5.25 m, y=-2~2 m` 的有顶棚区域后，GPS 发布 `STATUS_NO_FIX`，可用性变为 `false`。
- 接近取件点或交接点 3.5 米内时，`/bioshuttle/apriltag_visible=true`，并发布 `/apriltag/pose`。
- 这使算法组可以先验证“GPS 正常 → GPS 弱 → AprilTag 接管 → GPS 恢复”的状态逻辑。

## 在 NUC 上运行（可选）

NUC 已是 Ubuntu 22.04 + ROS 2 Humble，可以把本目录放入独立仿真工作区，不要放进已有且含重复 `hoverboard_driver` 的实车工作区：

```bash
cd ~/school_car_ws/src/campusCar
chmod +x simulation/scripts/*.sh
./simulation/scripts/install_wsl_humble.sh
./simulation/scripts/build_sim.sh
./simulation/scripts/run_sim.sh
```

如果 NUC 没有合适的 GPU/显示器，使用 `gui:=false rviz:=false`。推荐仍在游戏本运行图形仿真，把 NUC 留给实车调试。

## Docker（无界面/CI 备用）

当前游戏本没有 Docker Desktop，因此这不是首选路径。安装 Docker 后，在仓库根目录执行：

```bash
docker compose -f simulation/docker/compose.yaml up --build
```

容器默认无界面运行，适合编译和接口回归测试；Windows 图形显示仍建议使用原生 WSLg 路径。

## 目录说明

```text
simulation/
├── bioshuttle_sim/
│   ├── launch/bioshuttle_sim.launch.py
│   ├── urdf/bioshuttle_sim.urdf.xacro
│   ├── worlds/bioshuttle_campus.world
│   ├── config/localization.yaml
│   ├── config/bioshuttle.rviz
│   └── scripts/                 # GPS、AprilTag、七状态机节点
├── scripts/                     # WSL 安装、构建、启动、自检
└── docker/                      # 无界面容器
```

## 后续算法接入边界

环境已经提供 Nav2 所需的 `/odom`、`odom -> base_footprint`、`/scan`、机器人 TF 和 `/cmd_vel`。下一阶段应独立完成：

1. 用 SLAM Toolbox 建校园测试地图，或导入实测地图。
2. 配置 Nav2 footprint（建议按 `0.70 × 0.55 m` 含安全余量）和速度上限。
3. 把路口节点的 `0.3 m/s + 停车观察 2 秒` 放入任务状态机/Nav2 行为树。
4. 将合成 AprilTag 节点替换为真实 `apriltag_ros` 检测。
5. 将 AVOID 状态接到 `twist_mux` 或 Nav2 velocity smoother，保证状态切换能强制输出零速度。
6. 温湿度、箱盖和电子锁用独立 ROS 2 话题/服务仿真，不应耦合进底盘插件。

## 官方依据

- ROS 2 Humble Gazebo 教程：<https://docs.ros.org/en/humble/Tutorials/Advanced/Simulators/Gazebo.html>
- Nav2 Gazebo Classic 配置指南：<https://docs.nav2.org/setup_guides/gazebo_classic.html>
- Nav2 里程计要求：<https://docs.nav2.org/setup_guides/odom/setup_odom_gz_classic.html>
- Nav2 传感器要求：<https://docs.nav2.org/setup_guides/sensors/setup_sensors_gz_classic.html>

