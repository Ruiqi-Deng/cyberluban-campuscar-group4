#!/usr/bin/env bash
set -euo pipefail

if [ ! -r /etc/os-release ]; then
  echo "This script must run inside Ubuntu 22.04 (WSL2 or native Linux)." >&2
  exit 1
fi

. /etc/os-release
if [ "${ID:-}" != "ubuntu" ] || [ "${VERSION_ID:-}" != "22.04" ]; then
  echo "Expected Ubuntu 22.04 for ROS 2 Humble; found ${PRETTY_NAME:-unknown}." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y locales software-properties-common curl ca-certificates
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository -y universe

if ! dpkg-query -W -f='${Status}' ros2-apt-source 2>/dev/null | grep -q "install ok installed"; then
  ros_apt_source_version="$({
    curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest |
      sed -n 's/.*"tag_name": "\([^"]*\)".*/\1/p'
  } | head -n 1)"
  if [ -z "$ros_apt_source_version" ]; then
    echo "Could not determine the current ros2-apt-source release." >&2
    exit 1
  fi
  curl -fL -o /tmp/ros2-apt-source.deb \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ros_apt_source_version}/ros2-apt-source_${ros_apt_source_version}.jammy_all.deb"
  sudo dpkg -i /tmp/ros2-apt-source.deb
fi

sudo apt-get update
sudo apt-get install -y \
  python3-colcon-common-extensions \
  python3-rosdep \
  ros-dev-tools \
  ros-humble-desktop \
  ros-humble-gazebo-plugins \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-robot-localization \
  ros-humble-rviz2 \
  ros-humble-slam-toolbox \
  ros-humble-teleop-twist-keyboard \
  ros-humble-twist-mux \
  ros-humble-xacro

if apt-cache show ros-humble-apriltag-ros >/dev/null 2>&1; then
  sudo apt-get install -y ros-humble-apriltag-ros
fi

if [ ! -e /etc/ros/rosdep/sources.list.d/20-default.list ]; then
  sudo rosdep init
fi
rosdep update

echo
echo "ROS 2 Humble simulation dependencies are installed."
echo "Next: run ./simulation/scripts/build_sim.sh from the repository."

