FROM osrf/ros:humble-desktop-full-jammy

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-colcon-common-extensions \
      ros-humble-gazebo-plugins \
      ros-humble-gazebo-ros-pkgs \
      ros-humble-navigation2 \
      ros-humble-nav2-bringup \
      ros-humble-robot-localization \
      ros-humble-slam-toolbox \
      ros-humble-teleop-twist-keyboard \
      ros-humble-xacro \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bioshuttle_ws
COPY simulation/bioshuttle_sim /bioshuttle_ws/src/bioshuttle_sim
RUN source /opt/ros/humble/setup.bash \
    && colcon build --symlink-install --packages-select bioshuttle_sim

COPY simulation/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "bioshuttle_sim", "bioshuttle_sim.launch.py", "gui:=false", "rviz:=false"]

