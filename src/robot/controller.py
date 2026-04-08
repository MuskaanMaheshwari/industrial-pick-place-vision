"""
Low-level Jaka robot control functions.

Provides direct control over robot motion, program execution, and I/O operations.
Includes collision detection, error handling, and coordinate transformation utilities.
"""
from __future__ import annotations

import logging
import time
from math import pi, degrees
from typing import List, Tuple, Optional, Any

import numpy as np
import pandas as pd

from src.robot.state import robot_state


def radians_to_degrees(rad: float) -> float:
    """Convert radians to degrees."""
    return degrees(rad)


def rad_to_deg_cart(cart_position: List[float]) -> List[float]:
    """
    Convert cartesian position from radians to degrees.

    Converts rotation components (Rx, Ry, Rz) from radians to degrees
    while preserving positional components (x, y, z).

    Args:
        cart_position: Cartesian pose [x, y, z, Rx_rad, Ry_rad, Rz_rad].

    Returns:
        Cartesian pose with rotations in degrees [x, y, z, Rx_deg, Ry_deg, Rz_deg].
    """
    return [
        cart_position[0],  # x
        cart_position[1],  # y
        cart_position[2],  # z
        radians_to_degrees(cart_position[3]),  # Rx: rad to deg
        radians_to_degrees(cart_position[4]),  # Ry: rad to deg
        radians_to_degrees(cart_position[5]),  # Rz: rad to deg
    ]


# ============================================================================
# MOTION CONTROL
# ============================================================================


def linear_move(
    robot_obj: Any,
    target_pose: List[float],
    speed: int = 250,
    acceleration: int = 150,
) -> None:
    """
    Perform linear (Cartesian) motion to target pose.

    Converts rotation from degrees to radians and performs linear motion.

    Args:
        robot_obj: Jaka robot object.
        target_pose: Target Cartesian pose [x, y, z, Rx_deg, Ry_deg, Rz_deg].
        speed: Motion speed. Default 250.
        acceleration: Acceleration rate. Default 150.
    """
    if robot_obj is None:
        logging.error("Cannot move: robot not connected")
        return

    # Convert degrees to radians
    pose_rad = [
        target_pose[0],
        target_pose[1],
        target_pose[2],
        target_pose[3] * (pi / 180),
        target_pose[4] * (pi / 180),
        target_pose[5] * (pi / 180),
    ]

    try:
        robot_obj.linear_move_extend(pose_rad, 0, True, speed, acceleration, 0.01)
        # Wait for motion to complete
        while robot_obj.get_robot_status()[1][1] == 0:
            pass
        logging.info(f"Linear move completed: {target_pose}")
    except Exception as e:
        logging.error(f"Linear move failed: {e}")


def linear_move_waypoint(
    robot_obj: Any,
    target_pose: List[float],
    speed: int = 300,
    acceleration: int = 150,
) -> None:
    """
    Linear motion to waypoint (non-blocking).

    Used for intermediate waypoints in complex motion sequences.

    Args:
        robot_obj: Jaka robot object.
        target_pose: Target Cartesian pose [x, y, z, Rx_deg, Ry_deg, Rz_deg].
        speed: Motion speed. Default 300.
        acceleration: Acceleration rate. Default 150.
    """
    if robot_obj is None:
        logging.error("Cannot move: robot not connected")
        return

    pose_rad = [
        target_pose[0],
        target_pose[1],
        target_pose[2],
        target_pose[3] * (pi / 180),
        target_pose[4] * (pi / 180),
        target_pose[5] * (pi / 180),
    ]

    try:
        robot_obj.linear_move_extend(pose_rad, 0, True, speed, acceleration, 0.01)
        logging.info(f"Linear move waypoint initiated: {target_pose}")
    except Exception as e:
        logging.error(f"Linear move waypoint failed: {e}")


def joint_move(
    robot_obj: Any, target_pose: List[float], speed: int = 250
) -> None:
    """
    Perform joint-space motion to target pose.

    Converts joint angles from degrees to radians.

    Args:
        robot_obj: Jaka robot object.
        target_pose: Target joint angles in degrees [J1, J2, J3, J4, J5, J6].
        speed: Motion speed. Default 250.
    """
    if robot_obj is None:
        logging.error("Cannot move: robot not connected")
        return

    # Convert degrees to radians
    pose_rad = [angle * (pi / 180) for angle in target_pose]

    try:
        robot_obj.joint_move(pose_rad, 0, True, speed)
        # Wait for motion to complete
        while robot_obj.get_robot_status()[1][1] == 0:
            pass
        logging.info(f"Joint move completed: {target_pose}")
    except Exception as e:
        logging.error(f"Joint move failed: {e}")


def relative_move(
    robot_obj: Any,
    speed: int = 250,
    acceleration: int = 150,
    x: Optional[float] = None,
    y: Optional[float] = None,
    z: Optional[float] = None,
    rx: Optional[float] = None,
    ry: Optional[float] = None,
    rz: Optional[float] = None,
) -> None:
    """
    Perform relative motion from current position.

    Args:
        robot_obj: Jaka robot object.
        speed: Motion speed. Default 250.
        acceleration: Acceleration rate. Default 150.
        x, y, z: Linear offset in mm.
        rx, ry, rz: Rotational offset in degrees.
    """
    if robot_obj is None:
        logging.error("Cannot move: robot not connected")
        return

    try:
        current_pose = robot_obj.get_tcp_position()[1]
        target_pose = list(current_pose)

        if x is not None:
            target_pose[0] += x
        if y is not None:
            target_pose[1] += y
        if z is not None:
            target_pose[2] += z
        if rx is not None:
            target_pose[3] += rx * (pi / 180)
        if ry is not None:
            target_pose[4] += ry * (pi / 180)
        if rz is not None:
            target_pose[5] += rz * (pi / 180)

        robot_obj.linear_move_extend(target_pose, 0, True, speed, acceleration, 0.01)
        while robot_obj.get_robot_status()[1][1] == 0:
            pass
        logging.info(
            f"Relative move completed: dX={x}, dY={y}, dZ={z}, "
            f"dRx={rx}, dRy={ry}, dRz={rz}"
        )
    except Exception as e:
        logging.error(f"Relative move failed: {e}")


def relative_arc_move(
    robot_obj: Any,
    speed: int = 250,
    acceleration: int = 150,
    adapter: str = "3D",
    x: Optional[float] = None,
    y: Optional[float] = None,
    z: Optional[float] = None,
    rx: Optional[float] = None,
    ry: Optional[float] = None,
    rz: Optional[float] = None,
) -> None:
    """
    Perform arc-based relative motion (useful for approach/retreat sequences).

    Args:
        robot_obj: Jaka robot object.
        speed: Motion speed. Default 250.
        acceleration: Acceleration rate. Default 150.
        adapter: Vacuum adapter type ('3D', '5C', '15B'). Affects height adjustment.
        x, y, z: Linear offset in mm.
        rx, ry, rz: Rotational offset in degrees.
    """
    if robot_obj is None:
        logging.error("Cannot move: robot not connected")
        return

    try:
        current_pose = robot_obj.get_tcp_position()[1]
        target_pose = list(current_pose)

        if x is not None:
            target_pose[0] += x
        if y is not None:
            target_pose[1] += y
        if z is not None:
            target_pose[2] += z
        if rx is not None:
            target_pose[3] += rx * (pi / 180)
        if ry is not None:
            target_pose[4] += ry * (pi / 180)
        if rz is not None:
            target_pose[5] += rz * (pi / 180)

        # Apply adapter-specific height adjustment
        if adapter == "3D":
            target_pose[2] -= 7

        robot_obj.linear_move_extend(target_pose, 0, True, speed, acceleration, 0.01)
        while robot_obj.get_robot_status()[1][1] == 0:
            pass
        logging.info(f"Arc move completed with adapter={adapter}")
    except Exception as e:
        logging.error(f"Arc move failed: {e}")


# ============================================================================
# PROGRAM EXECUTION
# ============================================================================


def run_program(robot_obj: Any, program_name: str) -> Optional[Any]:
    """
    Load and run a program on the robot.

    Args:
        robot_obj: Jaka robot object.
        program_name: Name of the program file to execute.

    Returns:
        Robot object if successful, None otherwise.
    """
    if robot_obj is None:
        logging.error("Cannot run program: robot not connected")
        return None

    try:
        robot_obj.program_load(program_name)
        logging.info(f"Program loaded: {program_name}")

        robot_obj.program_run()
        # Wait for program completion
        while robot_obj.get_program_state()[1] != 0:
            pass

        logging.info(f"Program execution completed: {program_name}")
        return robot_obj
    except Exception as e:
        logging.error(f"Program execution failed: {e}")
        return None


def run_vision_program(robot_obj: Any, program_name: str) -> Optional[List[float]]:
    """
    Run a vision program and return final tool center pose.

    Executes a program and reads the resulting TCP position, converting
    rotations from radians to degrees.

    Args:
        robot_obj: Jaka robot object.
        program_name: Name of the vision program to execute.

    Returns:
        Cartesian pose in degrees [x, y, z, Rx_deg, Ry_deg, Rz_deg],
        or None if execution failed.
    """
    if robot_obj is None:
        logging.error("Cannot run vision program: robot not connected")
        return None

    try:
        run_program(robot_obj, program_name)
        time.sleep(2)

        cart_position = robot_obj.get_robot_status()[1][18]
        pose_degrees = rad_to_deg_cart(cart_position)

        logging.info(f"Vision program result: {pose_degrees}")
        return pose_degrees
    except Exception as e:
        logging.error(f"Vision program failed: {e}")
        return None


# ============================================================================
# POSE QUERIES
# ============================================================================


def get_tool_center_pose(robot_obj: Any) -> Optional[List[float]]:
    """
    Get current tool center point (TCP) position.

    Returns:
        Cartesian pose in degrees [x, y, z, Rx_deg, Ry_deg, Rz_deg],
        or None if query failed.
    """
    if robot_obj is None:
        logging.error("Cannot get pose: robot not connected")
        return None

    try:
        pose = robot_obj.get_tcp_position()[1]
        pose_deg = rad_to_deg_cart(pose)
        return pose_deg
    except Exception as e:
        logging.error(f"Failed to get TCP position: {e}")
        return None


def get_chip_pose(
    zero_pose: List[float], chip_pose: List[float]
) -> Optional[List[float]]:
    """
    Calculate chip placement pose from zero position and offset.

    Args:
        zero_pose: Reference zero coordinate position.
        chip_pose: Offset from zero position.

    Returns:
        Calculated chip pose as numpy array, or None if calculation failed.
    """
    try:
        result = np.add(
            zero_pose, np.add(chip_pose, [0, 0, 0, 180, 0, 45])
        ).tolist()
        return result
    except Exception as e:
        logging.error(f"Failed to calculate chip pose: {e}")
        return None


# ============================================================================
# CSV AND DATA PROCESSING
# ============================================================================


def get_pick_place_list(filename: str) -> List[List[Any]]:
    """
    Parse CSV file and extract pick-place coordinates and parameters.

    CSV columns expected:
    Index, ArduinoSignal, ArduinoDistance, StickerPickIndex, StickerNumber,
    IC, Vacuum Cup - Placement, Pick_X, Pick_Y, Pick_Z, Pick_RX, Pick_RY,
    Pick_RZ, Place_X, Place_Y, Place_Z, Place_RX, Place_RY, Place_RZ, PLACE

    Args:
        filename: Path to the CSV file.

    Returns:
        List of pick-place entries: [index, pick_pose, place_pose, vacuum_adapter,
        place_turn, arduino_signal, sticker_number, ic, arduino_distance,
        sticker_pick_index]
    """
    try:
        csv_file = pd.read_csv(filename)
        pick_place_data = []

        for index, row in csv_file.iterrows():
            try:
                entry = [
                    row["Index"],
                    [
                        row["Pick_X"],
                        row["Pick_Y"],
                        row["Pick_Z"],
                        row["Pick_RX"],
                        row["Pick_RY"],
                        row["Pick_RZ"],
                    ],
                    [
                        int(row["Place_X"]),
                        int(row["Place_Y"]),
                        int(row["Place_Z"]),
                        int(row["Place_RX"]),
                        int(row["Place_RY"]),
                        int(row["Place_RZ"]),
                    ],
                    str(row["Vacuum Cup - Placement"]),
                    row["PLACE"],
                    int(row["ArduinoSignal"]),
                    int(row["StickerNumber"]),
                    row["IC"],
                    row["ArduinoDistance"],
                    int(row["StickerPickIndex"]),
                ]
                pick_place_data.append(entry)
            except KeyError as e:
                logging.error(f"Missing column in row {index}: {e}")
            except Exception as e:
                logging.error(f"Error processing row {index}: {e}")

        logging.info(f"Loaded {len(pick_place_data)} pick-place entries from {filename}")
        return pick_place_data
    except Exception as e:
        logging.error(f"Failed to parse CSV file {filename}: {e}")
        return []


# ============================================================================
# ARDUINO COMMUNICATION
# ============================================================================


def arduino_signal_send(robot_obj: Any, dispense_pause: float = 1.0) -> None:
    """
    Send signal to Arduino to dispense sticker from feeder.

    Toggles digital output, waits for sticker dispensing, then reads
    acknowledgment from Arduino.

    Args:
        robot_obj: Jaka robot object.
        dispense_pause: Time to wait after toggling output in seconds.
    """
    if robot_obj is None:
        logging.error("Cannot send Arduino signal: robot not connected")
        return

    robot_state.pause_event.wait()

    try:
        io_cabinet = 0
        do_pin = 6

        # Wait briefly before signaling
        time.sleep(0.1)

        # Send high signal
        robot_obj.set_digital_output(io_cabinet, do_pin, 1)
        time.sleep(2)

        # Send low signal
        robot_obj.set_digital_output(io_cabinet, do_pin, 0)
        logging.info("Sticker dispensed")

        time.sleep(dispense_pause)

        # Read acknowledgment from Arduino
        if robot_state.arduino is not None:
            data = robot_state.arduino.readline().decode()
            logging.info(f"Arduino response: {data}")
    except Exception as e:
        logging.error(f"Failed to send Arduino signal: {e}")


def arduino_signal_off(robot_obj: Any, dispense_pause: float = 1.0) -> None:
    """
    Turn off Arduino signal (set digital pin low).

    Args:
        robot_obj: Jaka robot object.
        dispense_pause: Time to wait after toggling output in seconds.
    """
    if robot_obj is None:
        logging.error("Cannot turn off Arduino signal: robot not connected")
        return

    try:
        io_cabinet = 0
        do_pin = 6
        robot_obj.set_digital_output(io_cabinet, do_pin, 0)
        logging.info("Arduino digital pin turned OFF")
        time.sleep(dispense_pause)
    except Exception as e:
        logging.error(f"Failed to turn off Arduino signal: {e}")


def serial_zero_in_command(arduino: Any, action: str) -> bool:
    """
    Send serial command to Arduino for feeder positioning.

    Supported actions:
    - "ZeroIN": Initialize feeder position
    - "FrontBoard": Position for front PCB board
    - "BackBoard": Position for back PCB board
    - "ResetBoard": Reset feeder
    - "Move2mm": Move 2mm forward

    Args:
        arduino: Serial connection object.
        action: Action command string.

    Returns:
        True if successful (received "success"), False otherwise.
    """
    if arduino is None:
        logging.error("Cannot send serial command: Arduino not connected")
        return False

    time.sleep(2)
    robot_state.pause_event.wait()

    action_codes = {
        "ZeroIN": "97",
        "FrontBoard": "13",
        "BackBoard": "31",
        "ResetBoard": "37",
        "Move2mm": "79",
    }

    code = action_codes.get(action)
    if code is None:
        logging.error(f"Unknown Arduino action: {action}")
        return False

    try:
        logging.info(f"Sending Arduino command: {action}")
        arduino.write(bytes(code, "utf-8"))

        # Wait for success response
        data = ""
        while "success" not in data:
            time.sleep(0.05)
            data = arduino.readline().decode()
            logging.debug(f"Arduino response: {data}")

            if "Done" in data:
                logging.info(f"Arduino command completed: {action}")
                return False

        logging.info(f"Arduino command successful: {action}")
        return True
    except Exception as e:
        logging.error(f"Failed to send serial command {action}: {e}")
        return False


# ============================================================================
# COLLISION AND ERROR HANDLING
# ============================================================================


def is_in_collision(robot_obj: Any) -> Tuple[int, int]:
    """
    Check if robot is in collision protection mode.

    Returns:
        Tuple (status_code, collision_state) where:
        - status_code: 0 if successful query
        - collision_state: 1 if collision active, 0 if no collision
    """
    if robot_obj is None:
        logging.error("Cannot check collision: robot not connected")
        return (-1, -1)

    try:
        return robot_obj.is_in_collision()
    except Exception as e:
        logging.error(f"Failed to check collision status: {e}")
        return (-1, -1)


def clear_collision_status(robot_obj: Any) -> None:
    """
    Clear collision state and recover robot motion.

    Repeatedly calls collision_recover until robot exits collision mode.

    Args:
        robot_obj: Jaka robot object.
    """
    if robot_obj is None:
        logging.error("Cannot clear collision: robot not connected")
        return

    try:
        while robot_obj.is_in_collision()[1] == 1:
            time.sleep(1)
            robot_obj.collision_recover()
        logging.info("Collision cleared - robot recovered")
    except Exception as e:
        logging.error(f"Failed to clear collision: {e}")


def robot_motion_abort(robot_obj: Any) -> None:
    """Abort current robot motion."""
    if robot_obj is None:
        logging.error("Cannot abort: robot not connected")
        return

    try:
        ret = robot_obj.motion_abort()
        if ret[0] == 0:
            logging.info("Motion aborted")
    except Exception as e:
        logging.error(f"Failed to abort motion: {e}")


def get_last_error_code(robot_obj: Any) -> Optional[Any]:
    """Get last error code from robot."""
    if robot_obj is None:
        logging.error("Cannot get error: robot not connected")
        return None

    try:
        return robot_obj.get_last_error()
    except Exception as e:
        logging.error(f"Failed to get error code: {e}")
        return None


def clear_error_code(robot_obj: Any) -> bool:
    """
    Clear error code from robot.

    Returns:
        True if cleared successfully.
    """
    if robot_obj is None:
        logging.error("Cannot clear error: robot not connected")
        return False

    try:
        robot_obj.clear_error()
        if robot_obj.get_last_error()[1] is None:
            logging.info("Error cleared")
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to clear error: {e}")
        return False


# ============================================================================
# PROGRAM STATE MANAGEMENT
# ============================================================================


def pause_jaka_program(robot_obj: Any) -> None:
    """Pause current program execution."""
    if robot_obj is None:
        logging.error("Cannot pause: robot not connected")
        return

    try:
        ret = robot_obj.program_pause()
        if ret[0] == 0:
            logging.info("Program paused")
    except Exception as e:
        logging.error(f"Failed to pause program: {e}")


def resume_jaka_program(robot_obj: Any) -> None:
    """Resume paused program execution."""
    if robot_obj is None:
        logging.error("Cannot resume: robot not connected")
        return

    try:
        ret = robot_obj.program_resume()
        if ret[0] == 0:
            logging.info("Program resumed")
    except Exception as e:
        logging.error(f"Failed to resume program: {e}")


def abort_jaka_program(robot_obj: Any) -> None:
    """Abort current program execution."""
    if robot_obj is None:
        logging.error("Cannot abort: robot not connected")
        return

    try:
        ret = robot_obj.program_abort()
        if ret[0] == 0:
            logging.info("Program aborted")
    except Exception as e:
        logging.error(f"Failed to abort program: {e}")
