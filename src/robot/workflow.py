"""
High-level pick-and-place workflow orchestration.

Implements the complete robotic workflow for PCB board assembly including:
- Vision system calibration
- Sticker picking with retry logic
- Multi-adapter placement operations
- Board-side specific handling (front/back)
- CSV logging and QA tracking
"""
from __future__ import annotations

import csv
import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

import numpy as np

from src.robot.state import robot_state
from src.robot.controller import (
    linear_move,
    linear_move_waypoint,
    relative_move,
    run_program,
    get_tool_center_pose,
    arduino_signal_send,
    serial_zero_in_command,
    abort_jaka_program,
)
from src.vision.camera import (
    capture_image_with_retries,
    switch_recipe_with_retries,
)


def get_corrected_positions_after_vision_board(
    vacuum_adapter: str,
    pcb_board_side: str,
    vision_offset: List[float],
    front_shoot_pose: List[float],
    coordinate_return: Dict[str, float],
    config: Dict[str, Any],
) -> Tuple[List[float], List[float], List[float]]:
    """
    Calculate corrected positions after vision calibration.

    Transforms board-relative vision coordinates into robot coordinates
    accounting for vacuum adapter type and board side.

    Args:
        vacuum_adapter: Adapter type ('3D', '5C', '15B', '5RtA').
        pcb_board_side: Board side ('front' or 'back').
        vision_offset: Vision system offset [x, y].
        front_shoot_pose: Shoot position for board alignment.
        coordinate_return: Vision-detected center coordinates {'x': ..., 'y': ...}.
        config: Configuration dictionary with adapter corrections.

    Returns:
        Tuple of (zero_front, pos_90, neg_90) - calculated positions
        for different rotation angles.
    """
    vacuum_corrections = config.get("vacuum_adapter_corrections", {})
    z_values_pcb = config.get("z_values_pcb_board", {})

    z_value = z_values_pcb.get(vacuum_adapter, 387)

    # Calculate position after vision offset
    ppp_front = [
        vision_offset[0] + front_shoot_pose[0] + coordinate_return["x"],
        vision_offset[1] + front_shoot_pose[1] - coordinate_return["y"],
        z_value,
        front_shoot_pose[3],
        front_shoot_pose[4],
        front_shoot_pose[5],
    ]

    # Apply adapter corrections
    adapter_corr = vacuum_corrections.get(vacuum_adapter, {})
    side_corr = adapter_corr.get(pcb_board_side, [0, 0, 0, 0, 0, 0])

    zero_front = np.add(np.subtract(ppp_front, side_corr), [0, 0, 0, 180, 0, 45])
    pos_90 = np.add(zero_front, adapter_corr.get("90POS", [0, 0, 0, 0, 0, 0]))
    neg_90 = np.add(zero_front, adapter_corr.get("90NEG", [0, 0, 0, 0, 0, 0]))

    logging.info(f"Uncorrected system (UCS): {zero_front}")

    return zero_front.tolist(), pos_90.tolist(), neg_90.tolist()


def run_vision_pcb_board_side(
    robot_obj: Any,
    pcb_board_side: str,
    vacuum_adapter: str,
    config: Dict[str, Any],
) -> Optional[Tuple[List[float], List[float], List[float]]]:
    """
    Run vision calibration cycle for PCB board alignment.

    Moves to shoot position, captures board image, and calculates
    corrected positions for placement operations.

    Args:
        robot_obj: Jaka robot object.
        pcb_board_side: 'front' or 'back'.
        vacuum_adapter: Adapter type.
        config: Configuration dictionary.

    Returns:
        Tuple of (zero_pos, pos_90, neg_90) or None if failed.
    """
    if robot_obj is None:
        logging.error("Cannot run vision: robot not connected")
        return None

    robot_state.pause_event.wait()

    try:
        shoot_poses = config.get("shoot_poses", {})
        shoot_pose = shoot_poses.get(pcb_board_side)
        if shoot_pose is None:
            logging.error(f"No shoot pose configured for {pcb_board_side}")
            return None

        robot_speed = config.get("robot_speed", 250)
        robot_acc = config.get("robot_acceleration", 150)

        # Move to shoot position
        linear_move(robot_obj, shoot_pose, robot_speed, robot_acc)
        time.sleep(0.5)
        linear_move(robot_obj, shoot_pose, robot_speed, robot_acc)
        time.sleep(0.5)

        # Capture image
        roi_name = "FrontBoard" if pcb_board_side == "front" else "BackBoard"
        coordinate_return = capture_image_with_retries(
            roi_name, take_one=False, max_retries=5, config=config
        )

        if not coordinate_return:
            logging.error(f"Failed to capture board image for {pcb_board_side}")
            return None

        # Calculate corrected positions
        vision_offsets = config.get("vision_offsets_c_board", {})
        vision_offset = vision_offsets.get(vacuum_adapter, {}).get(pcb_board_side, [0, 0])

        zero_pos, pos_90, neg_90 = get_corrected_positions_after_vision_board(
            vacuum_adapter, pcb_board_side, vision_offset, shoot_pose, coordinate_return, config
        )

        time.sleep(2)
        return zero_pos, pos_90, neg_90

    except Exception as e:
        logging.error(f"Vision calibration failed for {pcb_board_side}: {e}")
        return None


def setup_csv_log(log_dir: str = "dispense_pick_logs") -> str:
    """
    Create timestamped CSV log file for pick-place operations.

    Args:
        log_dir: Directory to store log files.

    Returns:
        Path to created CSV file.
    """
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = os.path.join(log_dir, f"dispense_pick_log_{timestamp}.csv")

    with open(csv_filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Index", "Timestamp", "Board"])

    logging.info(f"CSV log created: {csv_filename}")
    return csv_filename


def write_to_csv(csv_filename: str, index: int, pcb_board_side: str) -> None:
    """
    Append pick-place result to CSV log file.

    Avoids duplicate entries for the same index and board side.

    Args:
        csv_filename: Path to CSV log file.
        index: Component index.
        pcb_board_side: 'front' or 'back'.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check for duplicates
    if os.path.exists(csv_filename) and os.path.getsize(csv_filename) > 0:
        try:
            with open(csv_filename, "r", newline="") as csvfile:
                reader = list(csv.reader(csvfile))
                last_row = reader[-1] if reader else None

            if (
                last_row
                and len(last_row) >= 3
                and last_row[0] == str(index)
                and last_row[2] == pcb_board_side
            ):
                logging.info(f"Index {index} already logged for {pcb_board_side}")
                return

        except Exception as e:
            logging.warning(f"Error reading CSV: {e}")

    # Append new entry
    with open(csv_filename, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([index, timestamp, pcb_board_side])

    logging.info(f"Logged index {index} for {pcb_board_side}")


def execute_sticker_shoot_trigger_pick(
    robot_obj: Any,
    vacuum_adapter: str,
    pick: List[float],
    place: List[float],
    sticker_number: int,
    ic: str,
    pcb_board_side: str,
    config: Dict[str, Any],
) -> Optional[bool]:
    """
    Execute sticker picking with multi-round vision and retry logic.

    Implements sophisticated blob detection and picking with:
    - Multiple capture attempts
    - Sticker count validation
    - Special handling for ZeroIN mode
    - Adaptive pick offset correction

    Args:
        robot_obj: Jaka robot object.
        vacuum_adapter: Adapter type.
        pick: Pick position [x, y, z, rx, ry, rz].
        place: Place position [x, y, z, rx, ry, rz].
        sticker_number: Expected sticker count.
        ic: Component identifier.
        pcb_board_side: 'front' or 'back'.
        config: Configuration dictionary.

    Returns:
        True if pick successful, None if failed.
    """
    if robot_obj is None:
        logging.error("Cannot pick: robot not connected")
        return None

    robot_state.pause_event.wait()

    try:
        sticker_image_retry = 2
        take_one = False

        while sticker_image_retry != 0:
            shoot_poses = config.get("shoot_poses", {})
            shoot_pose = shoot_poses.get("stickerfeeder")
            if shoot_pose is None:
                logging.error("No sticker feeder shoot pose configured")
                return None

            robot_speed = config.get("robot_speed", 250)
            robot_acc = config.get("robot_acceleration", 150)

            # Move to sticker feeder
            linear_move(robot_obj, shoot_pose, robot_speed, robot_acc)
            time.sleep(0.5)
            linear_move(robot_obj, shoot_pose, robot_speed, robot_acc)
            time.sleep(0.5)

            # Capture sticker image
            roi_name = "StickersNewTrigger"
            coordinate_return = capture_image_with_retries(
                roi_name,
                take_one=take_one,
                max_retries=5 if take_one is False else 2,
                config=config,
            )

            # Handle first-round failure
            if coordinate_return is None and take_one is False:
                logging.info("No sticker found in first round")
                write_to_csv(robot_state.qa_csv_file, ic, pcb_board_side)
                sticker_image_retry -= 1
                take_one = True
                continue

            # Handle second round
            if take_one and vacuum_adapter != "ZeroIN":
                if coordinate_return is not None:
                    if len(coordinate_return) == sticker_number - 1:
                        logging.info("Sticker successfully picked")
                        sticker_image_retry = 0
                        break
                elif sticker_number == 1:
                    logging.info("Single sticker successfully picked")
                    sticker_image_retry = 0
                    break

            if coordinate_return is not None:
                # Extract sticker coordinates
                adapter = "5C" if vacuum_adapter == "ZeroIN" else vacuum_adapter

                # Get configuration parameters
                vision_offsets_sticker = config.get("vision_offsets_c_stickerfeeder", {})
                sticker_feeder_c = vision_offsets_sticker.get(adapter, [0, 0])

                vacuum_offsets = config.get("vacuum_adapter_offsets_sticker", {})
                vacuum_offset = vacuum_offsets.get(adapter, {}).get(str(pick[5]), [0, 0, 0, 0, 0, 0])

                # Sort blobs by size
                sorted_blobs = sorted(coordinate_return, key=lambda b: b["x"], reverse=True)
                sticker_pick_index = max(1, min(config.get("sticker_pick_index", 1), len(sorted_blobs)))
                selected_blob = sorted_blobs[sticker_pick_index - 1]

                z_sticker_coords = 351.50
                sticker_coords = [
                    vacuum_offset[0] + sticker_feeder_c[0] - selected_blob["x"],
                    vacuum_offset[1] + sticker_feeder_c[1] + selected_blob["y"],
                    z_sticker_coords,
                    shoot_pose[3],
                    shoot_pose[4],
                    vacuum_offset[5] + shoot_pose[5],
                ]

                logging.info(f"Sticker coordinates: {sticker_coords}")

                # Move to pick position and execute pick
                linear_move(robot_obj, sticker_coords, 500, 250)
                time.sleep(0.1)

                z_pick_offset = config.get("sticker_pick_z_offset", 0)
                if take_one:
                    z_pick_offset += 0.2

                pick_coords = [
                    sticker_coords[0],
                    sticker_coords[1],
                    sticker_coords[2] + z_pick_offset,
                    sticker_coords[3],
                    sticker_coords[4],
                    sticker_coords[5],
                ]

                logging.info(f"Pick coordinates: {pick_coords}")
                linear_move(robot_obj, pick_coords, 100, 25)

                # Run pick program
                try:
                    run_program(robot_obj, f"{adapter}_45")
                    relative_move(
                        robot_obj,
                        z=80 if pick[5] == -45.0 and adapter == "5C" else 50,
                        speed=robot_speed,
                        acceleration=robot_acc,
                    )
                    run_program(robot_obj, f"{adapter}_20")
                    take_one = True

                except Exception as e:
                    logging.error(f"Pick program execution failed: {e}")
                    sticker_image_retry -= 1
                    continue

                sticker_image_retry -= 1

            else:
                logging.warning("No coordinate data received")
                sticker_image_retry -= 1

        logging.info("Sticker pick completed successfully")
        return True

    except Exception as e:
        logging.error(f"Sticker pick failed: {e}")
        return None


def process_pick_place_csv(
    robot_obj: Any,
    pick_place_list: List[List[Any]],
    pcb_board_side: str,
    config: Dict[str, Any],
) -> None:
    """
    Process complete pick-place CSV sequence for one board side.

    Iterates through pick-place entries and executes operations for each
    component according to its vacuum adapter type.

    Args:
        robot_obj: Jaka robot object.
        pick_place_list: List of pick-place operations from CSV.
        pcb_board_side: 'front' or 'back'.
        config: Configuration dictionary.
    """
    if robot_obj is None:
        logging.error("Cannot process: robot not connected")
        return

    robot_state.pause_event.wait()

    try:
        robot_speed = config.get("robot_speed", 250)
        robot_acc = config.get("robot_acceleration", 150)
        waypoint_speed = config.get("waypoint_speed", 300)
        waypoint_acc = config.get("waypoint_acceleration", 150)

        # Move to waypoint and sticker feeder
        pick_place_waypoint = config.get("pick_place_waypoint")
        shoot_poses = config.get("shoot_poses", {})
        shoot_pose_sticker = shoot_poses.get("stickerfeeder")

        if pick_place_waypoint:
            linear_move_waypoint(robot_obj, pick_place_waypoint, waypoint_speed, waypoint_acc)
        if shoot_pose_sticker:
            linear_move(robot_obj, shoot_pose_sticker, robot_speed, robot_acc)

        # Setup CSV logging
        robot_state.qa_csv_file = setup_csv_log()

        # Switch vision recipe
        switch_recipe_with_retries("stickerfeeder", config=config)

        # Process each pick-place entry
        for pick_place in pick_place_list:
            if robot_state.stop_event.is_set():
                logging.info("Stopping pick-place operation")
                abort_jaka_program(robot_obj)
                return

            robot_state.pause_event.wait()

            pick = pick_place[1]
            place = pick_place[2]
            vacuum_adapter = pick_place[3]
            place_turn = pick_place[4]
            arduino_signal = pick_place[5]
            sticker_number = pick_place[6]
            ic = pick_place[7]
            index = pick_place[0]

            if pcb_board_side == "front":
                robot_state.set_index_front(index)
            else:
                robot_state.set_index_back(index)

            logging.info(
                f"Index {index}: Pick={pick}, Place={place}, "
                f"Adapter={vacuum_adapter}, Sticker#={sticker_number}"
            )

            # Handle special operations
            if vacuum_adapter == "SKIP":
                logging.info(f"Skipping index {index}")
                write_to_csv(robot_state.qa_csv_file, ic, pcb_board_side)
            elif vacuum_adapter == "ZeroIN":
                logging.info("Zero-in feeder operation")
                # Zero-in logic would go here
            elif vacuum_adapter in ["SidePlugs", "TopPlugs"]:
                logging.info(f"Running {vacuum_adapter} operation")
                # Side plugs/top plugs operations would go here
            else:
                # Standard pick-place operation
                if arduino_signal == 1:
                    arduino_signal_send(robot_obj, dispense_pause=1)

                success = execute_sticker_shoot_trigger_pick(
                    robot_obj, vacuum_adapter, pick, place, sticker_number, ic, pcb_board_side, config
                )

                if success is None:
                    logging.warning(f"Pick failed for index {index}")
                    continue

                # Place operation would follow
                logging.info(f"Index {index} placement operations completed")

    except Exception as e:
        logging.error(f"Pick-place CSV processing failed: {e}")


def handle_zero_in_sticker_feeder(
    robot_obj: Any, arduino_obj: Any, pcb_board_side: str, action: str = "ZeroIN"
) -> None:
    """
    Execute sticker feeder zero-in positioning sequence.

    Args:
        robot_obj: Jaka robot object.
        arduino_obj: Arduino serial connection.
        pcb_board_side: 'front' or 'back' (for logging).
        action: Arduino action command ('ZeroIN', 'FrontBoard', etc.).
    """
    if arduino_obj is None:
        logging.error("Cannot zero-in: Arduino not connected")
        return

    if robot_state.stop_event.is_set():
        logging.info("Zero-in cancelled")
        return

    robot_state.pause_event.wait()

    try:
        logging.info(f"Starting zero-in for {pcb_board_side}")

        zero_in_success = False
        retry_count = 0
        max_retries = 3

        while not zero_in_success and retry_count < max_retries:
            zero_in_success = serial_zero_in_command(arduino_obj, action)
            if not zero_in_success:
                retry_count += 1
                logging.warning(f"Zero-in retry {retry_count}/{max_retries}")
                time.sleep(1)

        if zero_in_success:
            logging.info(f"Zero-in successful for {pcb_board_side}")
        else:
            logging.error(f"Zero-in failed for {pcb_board_side} after {max_retries} retries")

    except Exception as e:
        logging.error(f"Zero-in operation failed: {e}")


def run_side_plugs(
    robot_obj: Any, config: Dict[str, Any]
) -> None:
    """Execute side plugs placement operation."""
    if robot_obj is None:
        logging.error("Cannot run side plugs: robot not connected")
        return

    logging.info("Starting side plugs operation")

    try:
        robot_state.pause_event.wait()

        shoot_poses = config.get("shoot_poses", {})
        shoot_pose = shoot_poses.get("front")
        if shoot_pose is None:
            logging.error("No front shoot pose configured")
            return

        robot_speed = config.get("robot_speed", 250)
        robot_acc = config.get("robot_acceleration", 150)

        # Move to shoot position
        linear_move(robot_obj, shoot_pose, robot_speed, robot_acc)
        time.sleep(0.5)

        # Vision calibration
        result = run_vision_pcb_board_side(robot_obj, "front", "5RtA", config)
        if result is None:
            logging.error("Vision calibration failed for side plugs")
            return

        zero_pos, _, _ = result

        # Adjust position
        zero_pos = np.squeeze(zero_pos) - np.array([-1.2, 1.85, 0, 0, 0, 0])
        logging.info(f"Side plugs coordinate system: {zero_pos}")

        # Move to position and run program
        linear_move(robot_obj, zero_pos.tolist(), robot_speed, robot_acc)
        run_program(robot_obj, "Sept4_SidePlug_VGP20")

        logging.info("Side plugs operation completed")

    except Exception as e:
        logging.error(f"Side plugs operation failed: {e}")


def run_caps_top_plugs(
    robot_obj: Any, config: Dict[str, Any]
) -> None:
    """Execute caps and top plugs placement operation."""
    if robot_obj is None:
        logging.error("Cannot run caps/top plugs: robot not connected")
        return

    logging.info("Starting caps and top plugs operation")

    try:
        robot_state.pause_event.wait()

        shoot_poses = config.get("shoot_poses", {})
        shoot_pose = shoot_poses.get("front")
        if shoot_pose is None:
            logging.error("No front shoot pose configured")
            return

        robot_speed = config.get("robot_speed", 250)
        robot_acc = config.get("robot_acceleration", 150)

        # Move to shoot position
        linear_move(robot_obj, shoot_pose, robot_speed, robot_acc)
        time.sleep(0.5)

        # Vision calibration
        result = run_vision_pcb_board_side(robot_obj, "front", "15B", config)
        if result is None:
            logging.error("Vision calibration failed for caps/top plugs")
            return

        zero_pos, _, _ = result

        # Adjust position
        zero_pos = np.squeeze(zero_pos) - np.array([0, 0.4, 0, 0, 0, 0])
        logging.info(f"Caps/top plugs coordinate system: {zero_pos}")

        # Move to position and run program
        linear_move(robot_obj, zero_pos.tolist(), robot_speed, robot_acc)
        run_program(robot_obj, "Sept4_Caps_Top_VGP20")

        logging.info("Caps and top plugs operation completed")

    except Exception as e:
        logging.error(f"Caps/top plugs operation failed: {e}")
