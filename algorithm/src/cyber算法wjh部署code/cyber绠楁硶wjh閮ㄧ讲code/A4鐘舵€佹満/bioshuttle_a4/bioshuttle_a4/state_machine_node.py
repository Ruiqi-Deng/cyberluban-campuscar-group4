"""ROS 2 node wrapping the BioShuttle A4 state machine."""

from functools import partial
from typing import Dict

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String, UInt8

from bioshuttle_a4.state_machine_core import (
    BioShuttleStateMachine,
    State,
    Transition,
)


EVENT_TOPICS = {
    "new_task": "/bioshuttle/events/new_task",
    "arrived_pickup": "/bioshuttle/events/arrived_pickup",
    "obstacle": "/bioshuttle/events/obstacle",
    "lid_closed": "/bioshuttle/events/lid_closed",
    "locked": "/bioshuttle/events/locked",
    "arrived_handover": "/bioshuttle/events/arrived_handover",
    "handover_done": "/bioshuttle/events/handover_done",
    "arrived_home": "/bioshuttle/events/arrived_home",
    "error": "/bioshuttle/events/error",
    "manual_reset": "/bioshuttle/events/manual_reset",
}


class BioShuttleStateMachineNode(Node):
    """Receive ROS events, evaluate the state machine, and publish state."""

    def __init__(self) -> None:
        super().__init__("bioshuttle_state_machine")

        self.declare_parameter("obstacle_clear_seconds", 1.0)
        self.declare_parameter("evaluation_hz", 20.0)
        self.declare_parameter("state_publish_hz", 2.0)

        obstacle_clear_seconds = float(
            self.get_parameter("obstacle_clear_seconds").value
        )
        evaluation_hz = float(self.get_parameter("evaluation_hz").value)
        state_publish_hz = float(self.get_parameter("state_publish_hz").value)

        if evaluation_hz <= 0.0:
            raise ValueError("evaluation_hz must be > 0")
        if state_publish_hz <= 0.0:
            raise ValueError("state_publish_hz must be > 0")

        self.machine = BioShuttleStateMachine(
            obstacle_clear_seconds=obstacle_clear_seconds
        )

        self.events: Dict[str, bool] = {name: False for name in EVENT_TOPICS}

        event_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        state_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self.state_pub = self.create_publisher(
            UInt8, "/bioshuttle/state", state_qos
        )
        self.state_name_pub = self.create_publisher(
            String, "/bioshuttle/state_name", state_qos
        )
        self.transition_pub = self.create_publisher(
            String, "/bioshuttle/transition", 10
        )
        self.motion_enable_pub = self.create_publisher(
            Bool, "/bioshuttle/motion_enable", state_qos
        )

        self.subscriptions = []
        for event_name, topic_name in EVENT_TOPICS.items():
            subscription = self.create_subscription(
                Bool,
                topic_name,
                partial(self._event_callback, event_name),
                event_qos,
            )
            self.subscriptions.append(subscription)

        self.evaluate_timer = self.create_timer(
            1.0 / evaluation_hz, self._evaluate
        )
        self.publish_timer = self.create_timer(
            1.0 / state_publish_hz, self._publish_state
        )

        self._publish_state()
        self.get_logger().info(
            "A4 状态机节点已启动：初始状态 IDLE；"
            f"障碍物清除确认时间 {obstacle_clear_seconds:.1f}s"
        )

    def _event_callback(self, event_name: str, msg: Bool) -> None:
        self.events[event_name] = bool(msg.data)
        self.get_logger().debug(
            f"事件更新: {event_name}={self.events[event_name]}"
        )
        self._evaluate()

    def _now_seconds(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    def _evaluate(self) -> None:
        transition = self.machine.update(
            now=self._now_seconds(),
            **self.events,
        )
        if transition is not None:
            self._handle_transition(transition)

    def _handle_transition(self, transition: Transition) -> None:
        self.get_logger().info(
            f"状态: {transition.previous.name} -> "
            f"{transition.current.name} ({transition.reason})"
        )

        transition_msg = String()
        transition_msg.data = (
            f"{transition.previous.name}->{transition.current.name}:"
            f"{transition.reason}"
        )
        self.transition_pub.publish(transition_msg)

        # Consume one-shot signals after the corresponding transition so an old
        # CLI test message cannot accidentally trigger a later mission.
        if transition.current == State.PICKUP:
            self.events["new_task"] = False
        elif (
            transition.previous == State.PICKUP
            and transition.current == State.TRANSIT
        ):
            self.events["arrived_pickup"] = False
        elif transition.current == State.HANDOVER:
            self.events["arrived_handover"] = False
        elif transition.current == State.RETURN:
            self.events["handover_done"] = False
        elif (
            transition.previous == State.RETURN
            and transition.current == State.IDLE
        ):
            self.events["arrived_home"] = False
        elif (
            transition.previous == State.ERROR
            and transition.current == State.IDLE
        ):
            self.events["manual_reset"] = False

        self._publish_state()

    def _publish_state(self) -> None:
        state = self.machine.state

        code_msg = UInt8()
        code_msg.data = int(state)
        self.state_pub.publish(code_msg)

        name_msg = String()
        name_msg.data = state.name
        self.state_name_pub.publish(name_msg)

        motion_msg = Bool()
        motion_msg.data = state in {
            State.PICKUP,
            State.TRANSIT,
            State.RETURN,
        }
        self.motion_enable_pub.publish(motion_msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BioShuttleStateMachineNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("收到 Ctrl+C，状态机节点退出")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
