"""
Entry point for the Industrial Pick-and-Place Vision System.

Initializes system components, loads configuration, sets up logging,
and launches the Tkinter GUI application.
"""
from __future__ import annotations

import logging
import serial
import time
import yaml
from pathlib import Path
from typing import Dict, Any

from src.utils.logging import setup_daily_logging
from src.robot.state import initialize_robot_state, robot_state
from src.gui.app import create_app


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dictionary containing configuration parameters.

    Raises:
        FileNotFoundError: If config file does not exist.
        yaml.YAMLError: If config file is malformed.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    if config is None:
        config = {}

    return config


def initialize_arduino(port: str, baudrate: int = 9600, timeout: int = 5) -> serial.Serial:
    """
    Initialize Arduino serial connection.

    Args:
        port: Serial port name (e.g., 'COM3', '/dev/ttyUSB0').
        baudrate: Serial communication speed. Default 9600.
        timeout: Read timeout in seconds. Default 5.

    Returns:
        Initialized serial.Serial object.

    Raises:
        serial.SerialException: If port cannot be opened.
    """
    try:
        arduino = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        logging.info(f"Arduino connected on {port} at {baudrate} baud")
        return arduino
    except serial.SerialException as e:
        logging.error(f"Failed to connect to Arduino on {port}: {e}")
        raise


def main():
    """
    Main entry point. Initializes and starts the application.
    """
    # Setup logging
    setup_daily_logging()
    logging.info("=== Industrial Pick-and-Place Vision System Starting ===")

    # Load configuration
    try:
        config = load_config("config/config.yaml")
        logging.info("Configuration loaded successfully")
    except FileNotFoundError as e:
        logging.error(f"Configuration error: {e}")
        logging.warning("Using default configuration values")
        config = {
            "robot": {"ip": "192.168.1.120"},
            "arduino": {"port": "COM3", "baudrate": 9600},
        }

    # Release any existing lock (from previous interrupted session)
    if robot_state.lock.locked():
        logging.info("Releasing lock from previous session")
        robot_state.lock.release()

    # Set initial state
    robot_state.pause_event.set()
    logging.info("Pause event set - system ready for commands")

    # Initialize robot
    robot_ip = config.get("robot", {}).get("ip", "192.168.1.120")
    try:
        logging.info(f"Initializing Jaka robot at {robot_ip}...")
        robot_state.robot_obj = initialize_robot_state(robot_ip)
        if robot_state.robot_obj is None:
            logging.error("Failed to initialize robot - continuing without robot connection")
        else:
            logging.info("Robot initialized successfully")
    except Exception as e:
        logging.error(f"Robot initialization failed: {e}")
        robot_state.robot_obj = None

    # Initialize Arduino
    arduino_port = config.get("arduino", {}).get("port", "COM3")
    try:
        robot_state.arduino = initialize_arduino(arduino_port)
        time.sleep(4)  # Wait for Arduino to initialize
        logging.info("Arduino initialized successfully")
    except serial.SerialException as e:
        logging.error(f"Arduino initialization failed: {e}")
        robot_state.arduino = None

    # Launch GUI
    try:
        logging.info("Launching GUI application...")
        create_app()
    except Exception as e:
        logging.error(f"GUI initialization failed: {e}")
        raise


if __name__ == "__main__":
    main()
