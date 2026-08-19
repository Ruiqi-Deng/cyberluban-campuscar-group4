# BioShuttle A4 ROS 2 状态机

这是把原来的纯 Python 测试状态机改成可部署到 ASUS NUC、可通过 ROS 2 Humble
话题测试的 `ament_python` 包。

## 与简单测试版相比

- 7 个状态仍使用手册编码：`IDLE=0 ... ERROR=6`
- 任意状态遇到异常立即进入 `ERROR`
- `PICKUP -> TRANSIT` 必须同时满足：
  - 到达取件点
  - 箱盖关闭
  - 电子锁锁闭
- `AVOID -> TRANSIT` 要求障碍物连续消失 1 秒
- 发布状态编码、状态名、状态转移和运动许可
- 附带自动场景节点和 `pytest` 单元测试

## 话题

### 输入（`std_msgs/msg/Bool`）

| 话题 | 含义 |
|---|---|
| `/bioshuttle/events/new_task` | 收到任务 |
| `/bioshuttle/events/arrived_pickup` | 到达取件点 |
| `/bioshuttle/events/obstacle` | 检测到障碍物 |
| `/bioshuttle/events/lid_closed` | 箱盖关闭 |
| `/bioshuttle/events/locked` | 电子锁锁闭 |
| `/bioshuttle/events/arrived_handover` | 到达接驳点 |
| `/bioshuttle/events/handover_done` | 交接完成 |
| `/bioshuttle/events/arrived_home` | 到达充电点/起点 |
| `/bioshuttle/events/error` | 通信、定位、碰撞等异常 |
| `/bioshuttle/events/manual_reset` | 人工复位 |

### 输出

| 话题 | 类型 | 含义 |
|---|---|---|
| `/bioshuttle/state` | `std_msgs/msg/UInt8` | 状态编码 0~6 |
| `/bioshuttle/state_name` | `std_msgs/msg/String` | 状态名称 |
| `/bioshuttle/transition` | `std_msgs/msg/String` | 最近一次状态转移 |
| `/bioshuttle/motion_enable` | `std_msgs/msg/Bool` | 是否允许规划器输出运动指令 |

## 在 NUC 上构建

假设已安装 Ubuntu 22.04 和 ROS 2 Humble：

```bash
source /opt/ros/humble/setup.bash

mkdir -p ~/bioshuttle_ws/src
cp -r bioshuttle_a4 ~/bioshuttle_ws/src/

cd ~/bioshuttle_ws
rosdep install -i --from-path src --rosdistro humble -y
colcon build --symlink-install --packages-select bioshuttle_a4
source install/setup.bash
```

建议加入 `~/.bashrc`：

```bash
source /opt/ros/humble/setup.bash
source ~/bioshuttle_ws/install/setup.bash
```

## 自动 ROS 2 测试

一个终端即可：

```bash
ros2 launch bioshuttle_a4 a4_state_machine.launch.py run_scenario:=true
```

预期状态顺序：

```text
IDLE -> PICKUP -> TRANSIT -> AVOID -> TRANSIT
     -> HANDOVER -> RETURN -> IDLE -> ERROR -> IDLE
```

## 手工话题测试

终端 1：

```bash
ros2 run bioshuttle_a4 state_machine
```

终端 2，观察状态：

```bash
ros2 topic echo /bioshuttle/state_name
```

终端 3，逐步发送事件：

```bash
ros2 topic pub --once /bioshuttle/events/lid_closed std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /bioshuttle/events/locked std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /bioshuttle/events/new_task std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /bioshuttle/events/arrived_pickup std_msgs/msg/Bool "{data: true}"

ros2 topic pub --once /bioshuttle/events/obstacle std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /bioshuttle/events/obstacle std_msgs/msg/Bool "{data: false}"
sleep 1.2

ros2 topic pub --once /bioshuttle/events/arrived_handover std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /bioshuttle/events/handover_done std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /bioshuttle/events/arrived_home std_msgs/msg/Bool "{data: true}"
```

异常测试：

```bash
ros2 topic pub --once /bioshuttle/events/error std_msgs/msg/Bool "{data: true}"
ros2 topic pub --once /bioshuttle/events/error std_msgs/msg/Bool "{data: false}"
ros2 topic pub --once /bioshuttle/events/manual_reset std_msgs/msg/Bool "{data: true}"
```

## 单元测试

```bash
cd ~/bioshuttle_ws
colcon test --packages-select bioshuttle_a4
colcon test-result --verbose
```

也可直接运行核心测试：

```bash
python3 -m pytest src/bioshuttle_a4/test/test_state_machine_core.py -q
```

## 接入 A2/A3/A5

- A2 避障节点发布 `/bioshuttle/events/obstacle`
- A3 定位/导航节点发布三个到达事件
- A5 串口节点发布 `locked`、通信异常等，并订阅状态或
  `/bioshuttle/motion_enable`
- 实车电机速度仍应由导航/规划节点产生，状态机只负责流程和安全门控
