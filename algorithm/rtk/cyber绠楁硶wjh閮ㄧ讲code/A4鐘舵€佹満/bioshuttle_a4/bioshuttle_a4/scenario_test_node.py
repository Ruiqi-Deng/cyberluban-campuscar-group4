"""Automatic ROS 2 scenario publisher for the A4 state machine."""

from typing import Dict, List, Tuple

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from bioshuttle_a4.state_machine_node import EVENT_TOPICS


ScenarioItem = Tuple[float, str, bool, str]


class ScenarioTestNode(Node):
    """Publish a complete state-machine test sequence."""

    def __init__(self) -> None:
        super().__init__("bioshuttle_a4_scenario_test")

        self.publishers: Dict[str, object] = {
            name: self.create_publisher(Bool, topic, 10)
            for name, topic in EVENT_TOPICS.items()
        }

        self.state_sub = self.create_subscription(
            String,
            "/bioshuttle/state_name",
            self._state_callback,
            10,
        )

        self.scenario: List[ScenarioItem] = [
            (0.5, "lid_closed", True, "箱盖关闭"),
            (0.6, "locked", True, "电子锁锁闭"),
            (1.0, "new_task", True, "发布新任务"),
            (2.0, "arrived_pickup", True, "到达取件点"),
            (3.0, "obstacle", True, "前方出现障碍物"),
            (4.0, "obstacle", False, "障碍物移开"),
            (5.5, "arrived_handover", True, "到达接驳点"),
            (6.5, "handover_done", True, "交接完成"),
            (7.5, "arrived_home", True, "返回充电点"),
            (8.5, "error", True, "模拟通信/定位异常"),
            (9.2, "error", False, "异常信号清除"),
            (9.5, "manual_reset", True, "人工复位"),
        ]

        self.start_time = self.get_clock().now()
        self.next_index = 0
        self.last_state = ""
        self.timer = self.create_timer(0.05, self._tick)

        self.get_logger().info("A4 自动测试场景开始")

    def _elapsed(self) -> float:
        delta = self.get_clock().now() - self.start_time
        return delta.nanoseconds / 1_000_000_000.0

    def _state_callback(self, msg: String) -> None:
        if msg.data != self.last_state:
            self.last_state = msg.data
            self.get_logger().info(f"观测到状态: {msg.data}")

    def _tick(self) -> None:
        elapsed = self._elapsed()

        while self.next_index < len(self.scenario):
            due, event_name, value, description = self.scenario[self.next_index]
            if elapsed < due:
                break

            msg = Bool()
            msg.data = value
            self.publishers[event_name].publish(msg)
            self.get_logger().info(
                f"T+{elapsed:.1f}s {description}: "
                f"{event_name}={value}"
            )
            self.next_index += 1

        if self.next_index >= len(self.scenario) and elapsed >= 11.0:
            self.get_logger().info(
                f"自动测试结束，最终观测状态: {self.last_state or '未知'}"
            )
            self.timer.cancel()
            rclpy.shutdown()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScenarioTestNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
