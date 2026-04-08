"""
Industrial Pick-and-Place Vision System.

This package provides a complete robotic pick-and-place system for automated PCB masking
using a Jaka Zu 7 cobot, Overview AI vision camera, OnRobot VGP30 vacuum gripper,
and custom Arduino sticker feeder with laser positioning.

Key Components:
- robot: Jaka cobot control and state management
- vision: Overview AI camera integration for blob detection and calibration
- gui: Tkinter-based operator interface with process control
- utils: Logging and utility functions

The system performs automated PCB masking by picking stickers from a feeder and placing
them on circuit boards at precise locations determined by vision calibration.
"""
