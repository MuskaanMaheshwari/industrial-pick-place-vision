"""
Robot state management and initialization.

Centralizes shared robot state, threading synchronization primitives,
and robot initialization logic for the Jaka cobot.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Any

try:
    import jkrc  # type: ignore
except ImportError:
    jkrc = None


@dataclass
class RobotState:
    """
    Centralized robot state management.

    Contains:
    - Robot object and hardware connections (Arduino, etc.)
    - Threading synchronization primitives (lock, events)
    - Process state indicators (indices, CSV file, images)
    - Collision detection flag
    """

    # Hardware objects
    robot_obj: Optional[Any] = None
    arduino: Optional[Any] = None

    # Process state
    qa_csv_file: Optional[str] = None
    highlighted_image: Optional[Any] = None
    index_front: int = 0
    index_back: int = 0
    process_finished: bool = False

    # Threading synchronization
    lock: threading.Lock = field(default_factory=threading.Lock)
    stop_event: threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)
    collision_detected: bool = False

    def reset_indices(self) -> None:
        """Reset front and back board process indices."""
        with self.lock:
            self.index_front = 0
            self.index_back = 0
            self.process_finished = False

    def set_index_front(self, index: int) -> None:
        """Set front board processing index."""
        with self.lock:
            self.index_front = index

    def set_index_back(self, index: int) -> None:
        """Set back board processing index."""
        with self.lock:
            self.index_back = index


# Global robot state singleton
robot_state = RobotState()


def initialize_robot_state(ip: str) -> Optional[Any]:
    """
    Initialize Jaka cobot connection with connectivity checks.

    Performs:
    1. Ping check to verify network connectivity
    2. Robot object instantiation
    3. Login authentication
    4. Power on and enable sequence

    Args:
        ip: IP address of the Jaka cobot (e.g., "192.168.1.120").

    Returns:
        Initialized Jaka robot object if successful, None otherwise.

    Raises:
        ImportError: If jkrc module is not available.
    """
    if jkrc is None:
        logging.error("jkrc module not available - cannot initialize robot")
        return None

    # Ping check
    ping_cmd = (
        f"ping -c 1 {ip} > /dev/null 2>&1"
        if os.name != "nt"
        else f"ping -n 1 {ip} >nul"
    )
    response = os.system(ping_cmd)

    if response != 0:
        logging.warning(f"Ping to robot IP {ip} failed - robot may be unreachable")
    else:
        logging.info(f"Ping to robot IP {ip} succeeded")

    try:
        # Create robot object
        robot_obj = jkrc.RC(ip)  # type: ignore
        logging.info(f"Robot object created for IP {ip}")

        # Login
        robot_obj.login()
        logging.info("Robot login successful")

        # Power on
        robot_obj.power_on()
        logging.info("Robot powered on")
        time.sleep(15)  # Wait for power-on sequence

        # Enable robot
        enable_result = robot_obj.enable_robot()
        if enable_result[0] == 0:
            logging.info("Robot enabled successfully")
            return robot_obj
        else:
            logging.error(f"Robot enable failed with code {enable_result[0]}")
            return None

    except Exception as e:
        logging.error(f"Robot initialization failed: {e}")
        return None


def is_robot_connected() -> bool:
    """Check if robot is currently connected."""
    return robot_state.robot_obj is not None


def is_arduino_connected() -> bool:
    """Check if Arduino is currently connected."""
    return robot_state.arduino is not None
