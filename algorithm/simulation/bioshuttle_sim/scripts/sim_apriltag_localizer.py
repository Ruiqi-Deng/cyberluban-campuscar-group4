#!/usr/bin/env python3
"""Publish a synthetic AprilTag pose near the pickup and handover stations.

This tests localization-source switching without pretending to test the real
camera detector. Replace this node with apriltag_ros for perception validation.
"""

import copy
import math
import random

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Bool


class SimAprilTagLocalizer(Node):
    def __init__(self) -> None:
        super().__init__('bioshuttle_sim_apriltag_localizer')
        self.declare_parameter('max_detection_range', 3.5)
        self.declare_parameter('position_noise_stddev', 0.03)
        self.declare_parameter('publish_rate', 10.0)
        self.latest_odom = None
        self.random = random.Random(84)
        self.tag_positions = [(-7.0, -3.6), (6.9, 4.0)]

        self.pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, '/apriltag/pose', qos_profile_sensor_data
        )
        self.visible_pub = self.create_publisher(Bool, '/bioshuttle/apriltag_visible', 10)
        self.create_subscription(Odometry, '/odom', self.odom_callback, qos_profile_sensor_data)
        rate = max(0.2, float(self.get_parameter('publish_rate').value))
        self.create_timer(1.0 / rate, self.publish_pose)
        self.get_logger().info('Synthetic AprilTag localization ready at pickup/handover zones')

    def odom_callback(self, msg: Odometry) -> None:
        self.latest_odom = msg

    def publish_pose(self) -> None:
        if self.latest_odom is None:
            return
        pose = self.latest_odom.pose.pose
        max_range = float(self.get_parameter('max_detection_range').value)
        visible = any(
            math.hypot(pose.position.x - tx, pose.position.y - ty) <= max_range
            for tx, ty in self.tag_positions
        )
        self.visible_pub.publish(Bool(data=visible))
        if not visible:
            return

        noise = float(self.get_parameter('position_noise_stddev').value)
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.pose.pose = copy.deepcopy(pose)
        msg.pose.pose.position.x += self.random.gauss(0.0, noise)
        msg.pose.pose.position.y += self.random.gauss(0.0, noise)
        msg.pose.covariance = [0.0] * 36
        msg.pose.covariance[0] = noise ** 2
        msg.pose.covariance[7] = noise ** 2
        msg.pose.covariance[14] = 0.10
        msg.pose.covariance[21] = 0.10
        msg.pose.covariance[28] = 0.10
        msg.pose.covariance[35] = 0.02
        self.pose_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SimAprilTagLocalizer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
