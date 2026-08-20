from glob import glob
from setuptools import find_packages, setup

package_name = "bioshuttle_a4"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="BioShuttle Team",
    maintainer_email="team@example.com",
    description="BioShuttle A4 seven-state ROS 2 state machine.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "state_machine = bioshuttle_a4.state_machine_node:main",
            "scenario_test = bioshuttle_a4.scenario_test_node:main",
        ],
    },
)
