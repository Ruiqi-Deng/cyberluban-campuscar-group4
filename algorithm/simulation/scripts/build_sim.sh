#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
workspace="${BIOSHUTTLE_SIM_WS:-$HOME/bioshuttle_sim_ws}"
package_dir="$repo_root/simulation/bioshuttle_sim"

if [ ! -r /opt/ros/humble/setup.bash ]; then
  echo "ROS 2 Humble was not found. Run simulation/scripts/install_wsl_humble.sh first." >&2
  exit 1
fi

source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
mkdir -p "$workspace/src"
ln -sfn "$package_dir" "$workspace/src/bioshuttle_sim"

rosdep install --from-paths "$workspace/src" --ignore-src -r -y --rosdistro humble
cd "$workspace"
colcon build --symlink-install --packages-select bioshuttle_sim --event-handlers console_direct+

echo
echo "Build complete: $workspace"
echo "Run: $repo_root/simulation/scripts/run_sim.sh"
