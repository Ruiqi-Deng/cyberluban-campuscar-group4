#!/usr/bin/env python3
"""Publish a deterministic NavSatFix derived from Gazebo world odometry."""

import math
import random

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import Bool


EARTH_RADIUS_M = 6378137.0


class SimGpsNode(Node):
    def __init__(self) -> None:
        super().__init__('bioshuttle_sim_gps')
        self.declare_parameter('origin_latitude', 22.999000)
        self.declare_parameter('origin_longitude', 113.668000)
        self.declare_parameter('origin_altitude', 20.0)
        self.declare_parameter('position_noise_stddev', 0.25)
        self.declare_parameter('publish_rate', 5.0)
        self.declare_parameter('weak_zone_enabled', True)
        self.declare_parameter('weak_zone_min_x', 2.75)
        self.declare_parameter('weak_zone_max_x', 5.25)
        self.declare_parameter('weak_zone_min_y', -2.0)
        self.declare_parameter('weak_zone_max_y', 2.0)

        self.origin_lat = float(self.get_parameter('origin_latitude').value)
        self.origin_lon = float(self.get_parameter('origin_longitude').value)
        self.origin_alt = float(self.get_parameter('origin_altitude').value)
        self.noise_std = float(self.get_parameter('position_noise_stddev').value)
        self.random = random.Random(42)
        self.latest_odom = None

        self.fix_pub = self.create_publisher(NavSatFix, '/gps/fix', qos_profile_sensor_data)
        self.available_pub = self.create_publisher(Bool, '/bioshuttle/gps_available', 10)
        self.create_subscription(Odometry, '/odom', self.odom_callback, qos_profile_sensor_data)

        rate = max(0.2, float(self.get_parameter('publish_rate').value))
        self.create_timer(1.0 / rate, self.publish_fix)
        self.get_logger().info(
            f'Simulated GPS ready: origin=({self.origin_lat:.6f}, {self.origin_lon:.6f})'
        )

    def odom_callback(self, msg: Odometry) -> None:
        self.latest_odom = msg

    def in_weak_zone(self, x: float, y: float) -> bool:
        if not bool(self.get_parameter('weak_zone_enabled').value):
            return False
        return (
            float(self.get_parameter('weak_zone_min_x').value) <= x
            <= float(self.get_parameter('weak_zone_max_x').value)
            and float(self.get_parameter('weak_zone_min_y').value) <= y
            <= float(self.get_parameter('weak_zone_max_y').value)
        )

    def publish_fix(self) -> None:
        if self.latest_odom is None:
            return

        x = self.latest_odom.pose.pose.position.x
        y = self.latest_odom.pose.pose.position.y
        z = self.latest_odom.pose.pose.position.z
        weak = self.in_weak_zone(x, y)

        fix = NavSatFix()
        fix.header.stamp = self.get_clock().now().to_msg()
        fix.header.frame_id = 'gps_link'
        fix.status.service = NavSatStatus.SERVICE_GPS

        if weak:
            # Publish an explicit invalid fix so fusion/state-machine code can switch sources.
            fix.status.status = NavSatStatus.STATUS_NO_FIX
            horizontal_variance = 100.0
            noise_east = 0.0
            noise_north = 0.0
        else:
            fix.status.status = NavSatStatus.STATUS_FIX
            horizontal_variance = self.noise_std ** 2
            noise_east = self.random.gauss(0.0, self.noise_std)
            noise_north = self.random.gauss(0.0, self.noise_std)

        north_m = y + noise_north
        east_m = x + noise_east
        fix.latitude = self.origin_lat + math.degrees(north_m / EARTH_RADIUS_M)
        cos_lat = max(1.0e-6, math.cos(math.radians(self.origin_lat)))
        fix.longitude = self.origin_lon + math.degrees(east_m / (EARTH_RADIUS_M * cos_lat))
        fix.altitude = self.origin_alt + z
        fix.position_covariance = [
            horizontal_variance, 0.0, 0.0,
            0.0, horizontal_variance, 0.0,
            0.0, 0.0, 1.0,
        ]
        fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
        self.fix_pub.publish(fix)
        self.available_pub.publish(Bool(data=not weak))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SimGpsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
