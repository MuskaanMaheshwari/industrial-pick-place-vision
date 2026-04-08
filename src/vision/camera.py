"""
Overview AI vision camera integration.

Handles image capture, recipe switching, and blob detection for:
- Sticker feeder positioning
- PCB board alignment
- Quality assurance tracking
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import List, Dict, Optional, Any

import requests

from src.robot.state import robot_state


def filter_sticker_blobs(
    data: str, roi_name: str, config: Dict[str, Any]
) -> Optional[List[Dict[str, float]]]:
    """
    Filter and process sticker blobs from vision API response.

    Applies pixel count threshold (>2100) and size constraints to identify
    valid stickers in the feeder. Returns largest blobs by area.

    Args:
        data: JSON response from vision API.
        roi_name: Region of interest name ('StickersNewTrigger', etc.).
        config: Configuration dictionary with pixel_factor.

    Returns:
        List of filtered blobs with properties {x, y, a, b, angle, area},
        or None if parsing fails.
    """
    try:
        parsed_data = json.loads(data)
        blobs = parsed_data.get("segmentation", {}).get("blobs", [])

        pixel_factors = config.get("pixel_factors", {"StickersNewTrigger": 0.0659})
        factor = pixel_factors.get(roi_name, 0.0659)

        filtered_blobs = []

        for blob in blobs:
            pixel_count = blob.get("pixel_count", 0)
            center_y = blob.get("center_y_global", 0)

            # Apply filtering thresholds
            if pixel_count > 2100:
                # Size-dependent y-axis constraint
                if (pixel_count < 20000 and center_y < 400) or pixel_count >= 20000:
                    major_axis = blob.get("major_axis_length", 0)
                    minor_axis = blob.get("minor_axis_length", 0)

                    a = major_axis * factor
                    b = minor_axis * factor
                    area = a * b

                    filtered_blobs.append(
                        {
                            "x": blob.get("center_x_global", 0) * factor,
                            "y": blob.get("center_y_global", 0) * factor,
                            "a": a,
                            "b": b,
                            "angle": blob.get("angle_global", 0),
                            "area": area,
                        }
                    )

        # Sort by area and return top 4
        filtered_blobs.sort(key=lambda b: b["area"], reverse=True)
        return filtered_blobs[:4]

    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error in sticker blob filtering: {e}")
        return None
    except Exception as e:
        logging.error(f"Error filtering sticker blobs: {e}")
        return None


def filter_board_blobs(
    data: str, roi_name: str, config: Dict[str, Any]
) -> Optional[Dict[str, float]]:
    """
    Extract board alignment data from vision API response.

    Returns center location from alignment data for board positioning.

    Args:
        data: JSON response from vision API.
        roi_name: Region of interest name ('FrontBoard', 'BackBoard', etc.).
        config: Configuration dictionary with pixel_factor.

    Returns:
        Dictionary with board center {x, y}, or None if extraction fails.
    """
    try:
        parsed_data = json.loads(data)
        alignment = parsed_data.get("alignment", {})

        if not alignment:
            logging.warning("No alignment data in vision response")
            return None

        pixel_factors = config.get("pixel_factors", {"FrontBoard": 0.0486})
        factor = pixel_factors.get(roi_name, 0.0486)

        x_aligned = alignment.get("center_location_x", 0) * factor
        y_aligned = alignment.get("center_location_y", 0) * factor

        return {"x": x_aligned, "y": y_aligned}

    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error in board blob filtering: {e}")
        return None
    except Exception as e:
        logging.error(f"Error filtering board blobs: {e}")
        return None


def switch_recipe(stage: str, config: Dict[str, Any]) -> bool:
    """
    Switch vision recipe/pipeline to specified stage.

    Args:
        stage: Pipeline stage ('front', 'back', 'stickerfeeder', etc.).
        config: Configuration dictionary with recipe IDs and API URL.

    Returns:
        True if recipe activated successfully, False otherwise.
    """
    recipe_ids = config.get("recipe_ids", {})
    recipe_id = recipe_ids.get(stage)

    if recipe_id is None:
        logging.error(f"No recipe ID configured for stage '{stage}'")
        return False

    camera_url = config.get("camera_pipeline_url", "http://192.168.1.130:5001/pipeline/activate")

    try:
        payload = {"id": recipe_id}
        headers = {"Content-Type": "application/json"}

        response = requests.post(camera_url, json=payload, headers=headers)

        if response.status_code == 200:
            logging.info(f"Recipe {recipe_id} activated for stage '{stage}'")
            time.sleep(4)  # Wait for pipeline to stabilize
            return True
        else:
            logging.error(
                f"Failed to switch recipe for '{stage}': "
                f"HTTP {response.status_code} - {response.text}"
            )
            return False

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error while switching recipe for '{stage}': {e}")
        return False


def switch_recipe_with_retries(
    stage: str, config: Dict[str, Any], max_retries: int = 3, retry_delay: float = 1.0
) -> bool:
    """
    Switch recipe with automatic retry on failure.

    Args:
        stage: Pipeline stage.
        config: Configuration dictionary.
        max_retries: Maximum retry attempts. Default 3.
        retry_delay: Delay between retries in seconds. Default 1.0.

    Returns:
        True if successful, False if all retries exhausted.
    """
    for attempt in range(max_retries):
        if switch_recipe(stage, config):
            return True

        if attempt < max_retries - 1:
            logging.info(f"Retrying recipe switch for '{stage}' ({attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

    logging.error(f"Failed to switch recipe for '{stage}' after {max_retries} attempts")
    return False


def capture_image(
    roi_name: str, take_one: bool, config: Dict[str, Any]
) -> Optional[List[Dict[str, float]] | Dict[str, float]]:
    """
    Capture and process single image from Overview AI camera.

    Triggers image capture, validates response, and applies appropriate blob filtering
    based on ROI type (stickers vs. board alignment).

    Args:
        roi_name: Region of interest ('StickersNewTrigger', 'FrontBoard', etc.).
        take_one: Whether this is second+ capture attempt (affects retry behavior).
        config: Configuration dictionary.

    Returns:
        Filtered blob data (list for stickers, dict for board) or None on failure.
    """
    camera_url = config.get("camera_trigger_url", "http://192.168.1.130:1880/api/trigger")
    image_url_file = config.get("image_url_file", "last_image_url.txt")

    try:
        response = requests.get(camera_url)

        if response.status_code != 200:
            logging.error(f"Camera API returned HTTP {response.status_code}")
            time.sleep(1)
            return None

        # Handle empty response
        if not response.content.strip():
            if take_one:
                logging.info("Empty response in second round - assuming pick successful")
                return None
            else:
                logging.info("Empty response - retrying...")
                return None

        # Parse JSON response
        try:
            data = json.loads(response.content)
            image_url = data.get("image_url", "")
            image_number = get_image_number(image_url)

        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            time.sleep(1)
            return None

        # Check if image is new
        if not is_new_image(image_number, image_url_file):
            logging.info(f"Image {image_number} is same as last - retrying...")
            time.sleep(1)
            return None

        # Extract ROI info
        roi_list = data.get("roi", {}).get("rois", [])
        current_roi_name = roi_list[0].get("name", "") if roi_list else ""

        if not current_roi_name:
            logging.warning("ROI name empty in response")
            time.sleep(1)
            return None

        if not data.get("roi", {}):
            logging.warning("Invalid data structure in response")
            time.sleep(1)
            return None

        # Match ROI and filter blobs
        if current_roi_name == roi_name:
            logging.info(f"Processing ROI: {current_roi_name}")

            if roi_name == "StickersNewTrigger":
                filtered_data = filter_sticker_blobs(response.content, roi_name, config)
            else:
                filtered_data = filter_board_blobs(response.content, roi_name, config)

            if not filtered_data:
                logging.warning("No blobs detected - retrying...")
                time.sleep(1)
                return None

            # Save image number for next iteration
            save_image_number(image_number, image_url_file)
            return filtered_data

        else:
            logging.warning(f"ROI mismatch: expected {roi_name}, got {current_roi_name}")
            time.sleep(1)
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
        time.sleep(1)
        return None


def capture_image_with_retries(
    roi_name: str,
    take_one: bool,
    max_retries: int = 5,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[List[Dict[str, float]] | Dict[str, float]]:
    """
    Capture image with automatic retries on failure.

    Args:
        roi_name: Region of interest name.
        take_one: Whether this is second+ attempt.
        max_retries: Maximum retry attempts. Default 5.
        config: Configuration dictionary.

    Returns:
        Filtered blob data or None if all retries exhausted.
    """
    if config is None:
        config = {}

    retry_delay = config.get("retry_delay_capture_image", 0.5)

    for attempt in range(max_retries):
        robot_state.pause_event.wait()

        logging.info(f"Capturing image: {roi_name} (attempt {attempt + 1}/{max_retries})")
        result = capture_image(roi_name, take_one, config)

        if result is not None:
            return result

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    if not take_one:
        logging.error(f"Failed to capture image for '{roi_name}' after {max_retries} attempts")

    return None


def get_image_number(image_url: str) -> str:
    """
    Extract image sequence number from image URL.

    Extracts the numeric filename from the URL path.

    Args:
        image_url: Full image URL from vision API.

    Returns:
        Image sequence number as string.
    """
    try:
        # Format: ".../path/12345.jpg" -> "12345"
        return image_url.split("/")[-1].split(".")[0]
    except (IndexError, AttributeError):
        logging.warning(f"Could not extract image number from URL: {image_url}")
        return ""


def is_new_image(current_image_number: str, image_url_file: str) -> bool:
    """
    Check if current image is different from last captured image.

    Prevents processing duplicate images from vision pipeline.

    Args:
        current_image_number: Image number from current capture.
        image_url_file: Path to file storing last image number.

    Returns:
        True if current image is new, False if duplicate.
    """
    if not os.path.exists(image_url_file):
        return True  # No history yet

    try:
        with open(image_url_file, "r") as f:
            last_image_number = f.read().strip()
            return last_image_number != current_image_number
    except Exception as e:
        logging.warning(f"Error reading image history file: {e}")
        return True  # Assume new if can't read


def save_image_number(image_number: str, image_url_file: str) -> None:
    """
    Save image sequence number to file for duplicate detection.

    Args:
        image_number: Image number to save.
        image_url_file: Path to file for storing image number.
    """
    try:
        with open(image_url_file, "w") as f:
            f.write(image_number)
        logging.debug(f"Saved image number: {image_number}")
    except Exception as e:
        logging.error(f"Error saving image number: {e}")
