from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    run_scenario = LaunchConfiguration("run_scenario")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "run_scenario",
                default_value="false",
                description="Run the automatic A4 test scenario.",
            ),
            Node(
                package="bioshuttle_a4",
                executable="state_machine",
                name="bioshuttle_state_machine",
                output="screen",
                parameters=[
                    {
                        "obstacle_clear_seconds": 1.0,
                        "evaluation_hz": 20.0,
                        "state_publish_hz": 2.0,
                    }
                ],
            ),
            Node(
                package="bioshuttle_a4",
                executable="scenario_test",
                name="bioshuttle_a4_scenario_test",
                output="screen",
                condition=IfCondition(run_scenario),
            ),
        ]
    )
