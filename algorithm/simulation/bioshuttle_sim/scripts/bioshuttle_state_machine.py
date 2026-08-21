#!/usr/bin/env python3
"""Seven-state BioShuttle mission supervisor with obstacle-triggered AVOID."""

import math
from enum import Enum

import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range
from std_msgs.msg import Float64, String


class State(str, Enum):
    IDLE = 'IDLE'
    PICKUP = 'PICKUP'
    TRANSIT = 'TRANSIT'
    AVOID = 'AVOID'
    HANDOVER = 'HANDOVER'
    RETURN = 'RETURN'
    ERROR = 'ERROR'


class BioShuttleStateMachine(Node):
    def __init__(self) -> None:
        super().__init__('bioshuttle_state_machine')
        self.declare_parameter('obstacle_threshold', 1.0)
        self.declare_parameter('clear_wait_seconds', 2.0)
        self.declare_parameter('front_sector_degrees', 60.0)

        state_qos = QoSProfile(depth=1)
        state_qos.reliability = ReliabilityPolicy.RELIABLE
        state_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self.state_pub = self.create_publisher(String, '/bioshuttle/state', state_qos)
        self.distance_pub = self.create_publisher(Float64, '/bioshuttle/obstacle_distance', 10)
        self.create_subscription(String, '/bioshuttle/task_command', self.command_callback, 10)
        self.create_subscription(LaserScan, '/scan', self.scan_callback, qos_profile_sensor_data)
        for name in ('front', 'front_left', 'front_right'):
            self.create_subscription(
                Range,
                f'/range/{name}',
                lambda msg, sensor=name: self.range_callback(sensor, msg),
                qos_profile_sensor_data,
            )

        self.state = State.IDLE
        self.resume_state = State.TRANSIT
        self.lidar_distance = math.inf
        self.range_distances = {name: math.inf for name in ('front', 'front_left', 'front_right')}
        self.clear_since = None
        self.last_published_state = None
        self.create_timer(0.10, self.update)
        self.get_logger().info(
            'State machine ready. Commands: start, picked_up, handover, return, complete, error, reset'
        )
        self.publish_state(force=True)

    def transition(self, new_state: State, reason: str) -> None:
        if new_state == self.state:
            return
        old_state = self.state
        self.state = new_state
        self.clear_since = None
        self.get_logger().info(f'{old_state.value} -> {new_state.value}: {reason}')
        self.publish_state(force=True)

    def command_callback(self, msg: String) -> None:
        command = msg.data.strip().lower()
        transitions = {
            'start': (State.PICKUP, 'new pickup mission'),
            'pickup': (State.PICKUP, 'go to pickup point'),
            'picked_up': (State.TRANSIT, 'sample loaded'),
            'transit': (State.TRANSIT, 'start transport'),
            'handover': (State.HANDOVER, 'arrived at handover point'),
            'return': (State.RETURN, 'return to laboratory'),
            'complete': (State.IDLE, 'mission complete'),
            'idle': (State.IDLE, 'operator command'),
            'error': (State.ERROR, 'operator fault injection'),
            'reset': (State.IDLE, 'operator reset'),
            'clear_error': (State.IDLE, 'error cleared'),
        }
        target = transitions.get(command)
        if target is None:
            self.get_logger().warning(f'Unknown task command: {msg.data!r}')
            return
        self.transition(*target)

    def scan_callback(self, msg: LaserScan) -> None:
        half_sector = math.radians(float(self.get_parameter('front_sector_degrees').value)) / 2.0
        distances = []
        for index, value in enumerate(msg.ranges):
            angle = msg.angle_min + index * msg.angle_increment
            if abs(angle) <= half_sector and math.isfinite(value) and msg.range_min <= value <= msg.range_max:
                distances.append(value)
        self.lidar_distance = min(distances, default=math.inf)

    def range_callback(self, sensor: str, msg: Range) -> None:
        value = msg.range
        self.range_distances[sensor] = value if math.isfinite(value) else math.inf

    def nearest_obstacle(self) -> float:
        return min([self.lidar_distance, *self.range_distances.values()])

    def update(self) -> None:
        distance = self.nearest_obstacle()
        self.distance_pub.publish(Float64(data=distance))
        threshold = float(self.get_parameter('obstacle_threshold').value)
        moving_states = {State.PICKUP, State.TRANSIT, State.RETURN}

        if self.state in moving_states and distance < threshold:
            self.resume_state = self.state
            self.transition(State.AVOID, f'obstacle at {distance:.2f} m')
            return

        if self.state == State.AVOID:
            if distance < threshold:
                self.clear_since = None
            elif self.clear_since is None:
                self.clear_since = self.get_clock().now()
            else:
                wait = Duration(seconds=float(self.get_parameter('clear_wait_seconds').value))
                if self.get_clock().now() - self.clear_since >= wait:
                    self.transition(self.resume_state, 'path clear after observation delay')
                    return
        self.publish_state()

    def publish_state(self, force: bool = False) -> None:
        if force or self.last_published_state != self.state:
            self.state_pub.publish(String(data=self.state.value))
            self.last_published_state = self.state


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BioShuttleStateMachine()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
