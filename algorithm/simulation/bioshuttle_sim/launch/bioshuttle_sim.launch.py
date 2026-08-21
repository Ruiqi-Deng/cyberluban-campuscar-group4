#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = FindPackageShare('bioshuttle_sim')
    default_world = PathJoinSubstitution([package_share, 'worlds', 'bioshuttle_campus.world'])
    xacro_file = PathJoinSubstitution([package_share, 'urdf', 'bioshuttle_sim.urdf.xacro'])
    rviz_config = PathJoinSubstitution([package_share, 'config', 'bioshuttle.rviz'])
    localization_config = PathJoinSubstitution([package_share, 'config', 'localization.yaml'])

    gui = LaunchConfiguration('gui')
    rviz = LaunchConfiguration('rviz')
    world = LaunchConfiguration('world')
    use_sim_time = LaunchConfiguration('use_sim_time')
    state_machine = LaunchConfiguration('state_machine')
    synthetic_localization = LaunchConfiguration('synthetic_localization')
    localization_fusion = LaunchConfiguration('localization_fusion')

    robot_description = ParameterValue(
        Command(['xacro', ' ', xacro_file]),
        value_type=str,
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('gazebo_ros'), 'launch', 'gazebo.launch.py'])
        ),
        launch_arguments={
            'world': world,
            'gui': gui,
            'verbose': 'false',
        }.items(),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            {'robot_description': robot_description},
            {'use_sim_time': use_sim_time},
        ],
    )

    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_bioshuttle',
        output='screen',
        arguments=[
            '-entity', 'bioshuttle',
            '-topic', 'robot_description',
            '-x', LaunchConfiguration('spawn_x'),
            '-y', LaunchConfiguration('spawn_y'),
            '-z', LaunchConfiguration('spawn_z'),
            '-Y', LaunchConfiguration('spawn_yaw'),
        ],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(rviz),
    )

    sim_gps = Node(
        package='bioshuttle_sim',
        executable='sim_gps_node.py',
        name='bioshuttle_sim_gps',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(synthetic_localization),
    )
    sim_apriltag = Node(
        package='bioshuttle_sim',
        executable='sim_apriltag_localizer.py',
        name='bioshuttle_sim_apriltag_localizer',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(synthetic_localization),
    )
    mission_state_machine = Node(
        package='bioshuttle_sim',
        executable='bioshuttle_state_machine.py',
        name='bioshuttle_state_machine',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(state_machine),
    )

    ekf_local = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_local_filter',
        output='screen',
        parameters=[localization_config, {'use_sim_time': use_sim_time}],
        remappings=[('odometry/filtered', '/odometry/filtered')],
        condition=IfCondition(localization_fusion),
    )
    map_to_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='sim_map_to_odom',
        output='screen',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
        condition=IfCondition(localization_fusion),
    )
    navsat = Node(
        package='robot_localization',
        executable='navsat_transform_node',
        name='navsat_transform',
        output='screen',
        parameters=[localization_config, {'use_sim_time': use_sim_time}],
        remappings=[
            ('imu/data', '/imu/data'),
            ('gps/fix', '/gps/fix'),
            ('odometry/filtered', '/odometry/filtered'),
            ('odometry/gps', '/odometry/gps'),
        ],
        condition=IfCondition(localization_fusion),
    )
    ekf_global = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_global_filter',
        output='screen',
        parameters=[localization_config, {'use_sim_time': use_sim_time}],
        remappings=[('odometry/filtered', '/odometry/global')],
        condition=IfCondition(localization_fusion),
    )

    return LaunchDescription([
        DeclareLaunchArgument('world', default_value=default_world),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('state_machine', default_value='true'),
        DeclareLaunchArgument('synthetic_localization', default_value='true'),
        DeclareLaunchArgument('localization_fusion', default_value='false'),
        DeclareLaunchArgument('spawn_x', default_value='-7.0'),
        DeclareLaunchArgument('spawn_y', default_value='-3.6'),
        DeclareLaunchArgument('spawn_z', default_value='0.0'),
        DeclareLaunchArgument('spawn_yaw', default_value='0.0'),
        gazebo,
        robot_state_publisher,
        spawn_robot,
        sim_gps,
        sim_apriltag,
        mission_state_machine,
        map_to_odom,
        ekf_local,
        navsat,
        ekf_global,
        rviz_node,
    ])
