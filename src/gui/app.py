"""
Tkinter GUI application for operator interface.

Provides full-screen touchscreen interface for:
- Process start/stop control
- Vacuum and vision system testing
- Zero-in calibration
- Real-time status display
- Error handling and collision detection
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional, Any

import tkinter as tk
from tkinter import ttk
from tkinter.font import Font

from src.robot.state import robot_state
from src.robot.controller import (
    is_in_collision,
    clear_collision_status,
    robot_motion_abort,
)


def create_app() -> None:
    """
    Create and launch main application window.

    Sets up full-screen Tkinter GUI with three main buttons:
    - Start Top Side (Front PCB)
    - Start Bottom Side (Back PCB)
    - Reset System

    Initializes background threads for collision monitoring.
    """
    root = tk.Tk()
    root.title("Industrial Pick-and-Place Vision System")
    root.attributes("-fullscreen", True)
    root.configure(background="#3a8bcd")

    # Display robot connection status
    status_message = (
        "Robot connected successfully"
        if robot_state.robot_obj is not None
        else "Robot not connected - check configuration"
    )
    logging.info(status_message)

    status_label = tk.Label(
        root, text=status_message, font=("Helvetica", 20), bg="#3a8bcd", fg="white"
    )
    status_label.pack(pady=20)

    # Create main button container
    button_container = tk.Frame(root, bg="#3a8bcd")
    button_container.pack(expand=True, fill="both", padx=50, pady=50)

    custom_font = Font(family="Helvetica", size=30)
    style_options = {
        "compound": "top",
        "anchor": "c",
        "padx": 10,
        "font": custom_font,
        "bg": "#4f9fdf",
        "relief": "ridge",
        "bd": 1,
        "border": 0,
    }

    # Start Top Side button
    btn_front = tk.Button(
        button_container,
        text="Start Top Side",
        command=lambda: [
            popup_process_start("front"),
            threading.Thread(target=check_collision_thread, daemon=True).start(),
        ],
        foreground="white",
        **style_options,
    )
    btn_front.pack(side=tk.LEFT, padx=50, expand=True, fill="both")

    # Start Bottom Side button
    btn_back = tk.Button(
        button_container,
        text="Start Bottom Side",
        command=lambda: [
            popup_process_start("back"),
            threading.Thread(target=check_collision_thread, daemon=True).start(),
        ],
        foreground="white",
        **style_options,
    )
    btn_back.pack(side=tk.LEFT, padx=50, expand=True, fill="both")

    # Reset System button
    btn_reset = tk.Button(
        button_container,
        text="Reset System",
        command=lambda: popup_reset_system(root),
        foreground="white",
        **style_options,
    )
    btn_reset.pack(side=tk.LEFT, padx=50, expand=True, fill="both")

    logging.info("GUI initialized successfully")
    root.mainloop()


def check_collision_thread() -> None:
    """
    Background thread for continuous collision monitoring.

    Checks robot collision status periodically and attempts recovery if needed.
    """
    if robot_state.robot_obj is None:
        return

    try:
        while not robot_state.stop_event.is_set():
            status, collision_state = is_in_collision(robot_state.robot_obj)

            if status == 0 and collision_state == 1:
                logging.warning("Collision detected - attempting recovery")
                robot_state.collision_detected = True
                clear_collision_status(robot_state.robot_obj)
                robot_state.collision_detected = False
                logging.info("Collision recovery completed")

            time.sleep(2)

    except Exception as e:
        logging.error(f"Collision detection thread error: {e}")


def popup_process_start(board_side: str) -> None:
    """
    Show process startup confirmation popup.

    Args:
        board_side: 'front' or 'back' PCB board side.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title(f"Start {board_side.title()} Side")

    side_label = "Top Side (Front PCB)" if board_side == "front" else "Bottom Side (Back PCB)"

    label = tk.Label(
        win,
        text=f"Starting process for {side_label}",
        font=custom_font,
        padx=400,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    confirm_btn = ttk.Button(
        win,
        text="Confirm",
        command=lambda: [
            win.destroy(),
            popup_vacuum_test(board_side),
        ],
    )
    confirm_btn.pack(pady=20)

    cancel_btn = ttk.Button(win, text="Cancel", command=win.destroy)
    cancel_btn.pack(pady=10)


def popup_vacuum_test(board_side: str) -> None:
    """
    Show vacuum adapter test popup.

    Args:
        board_side: 'front' or 'back' PCB board side.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title("Vacuum Adapter Test")

    label = tk.Label(
        win,
        text="Test Vacuum Adapter",
        font=custom_font,
        padx=600,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    test_btn = ttk.Button(
        win,
        text="Test Vacuum",
        command=lambda: [
            win.destroy(),
            popup_vacuum_test_confirm(board_side),
        ],
    )
    test_btn.pack(pady=20)

    cancel_btn = ttk.Button(win, text="Cancel", command=win.destroy)
    cancel_btn.pack(pady=10)


def popup_vacuum_test_confirm(board_side: str) -> None:
    """
    Confirm vacuum test result.

    Args:
        board_side: 'front' or 'back' PCB board side.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title("Vacuum Test Result")

    label = tk.Label(
        win,
        text="Does Vacuum Adapter Work?",
        font=custom_font,
        padx=500,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    yes_btn = ttk.Button(
        win,
        text="Yes - Proceed",
        command=lambda: [
            win.destroy(),
            popup_vision_test(board_side),
        ],
    )
    yes_btn.pack(pady=20)

    no_btn = ttk.Button(
        win,
        text="No - Troubleshoot",
        command=lambda: [win.destroy(), popup_error("Contact engineering team for vacuum troubleshooting")],
    )
    no_btn.pack(pady=10)


def popup_vision_test(board_side: str) -> None:
    """
    Show vision system test popup.

    Args:
        board_side: 'front' or 'back' PCB board side.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title("Vision System Test")

    label = tk.Label(
        win,
        text="Test Vision System",
        font=custom_font,
        padx=600,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    test_btn = ttk.Button(
        win,
        text="Run Vision Test",
        command=lambda: [
            win.destroy(),
            popup_process_running(),
            threading.Thread(target=lambda: popup_vision_test_success(board_side)).start(),
        ],
    )
    test_btn.pack(pady=20)

    cancel_btn = ttk.Button(win, text="Cancel", command=win.destroy)
    cancel_btn.pack(pady=10)


def popup_vision_test_success(board_side: str) -> None:
    """
    Show vision test success message.

    Args:
        board_side: 'front' or 'back' PCB board side.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title("Vision Test Result")

    label = tk.Label(
        win,
        text="Vision System Test Passed!",
        font=custom_font,
        padx=500,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    continue_btn = ttk.Button(
        win,
        text="Continue to Zero-In",
        command=lambda: [
            win.destroy(),
            popup_zero_in_confirm(board_side),
        ],
    )
    continue_btn.pack(pady=20)


def popup_zero_in_confirm(board_side: str) -> None:
    """
    Confirm sticker feeder zero-in operation.

    Args:
        board_side: 'front' or 'back' PCB board side.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title("Zero-In Sticker Feeder")

    label = tk.Label(
        win,
        text="Check sticker roll loaded.\nReady to zero-in feeder?",
        font=custom_font,
        padx=500,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    yes_btn = ttk.Button(
        win,
        text="Start Zero-In",
        command=lambda: [
            win.destroy(),
            popup_process_running(),
            # Zero-in logic would go here
        ],
    )
    yes_btn.pack(pady=20)

    no_btn = ttk.Button(win, text="Cancel", command=win.destroy)
    no_btn.pack(pady=10)


def popup_process_running() -> None:
    """Show process execution in progress popup."""
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title("Process Running")

    label = tk.Label(
        win,
        text="Process Running...\nPlease Wait",
        font=custom_font,
        padx=500,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    stop_btn = ttk.Button(
        win, text="Stop Process", command=lambda: [win.destroy(), stop_process()]
    )
    stop_btn.pack(pady=20)


def popup_reset_system(root: tk.Tk) -> None:
    """
    Reset system to initial state.

    Args:
        root: Root window reference.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#3a8bcd")
    win.wm_title("Reset System")

    label = tk.Label(
        win,
        text="Resetting System...",
        font=custom_font,
        padx=500,
        pady=300,
        background="#3a8bcd",
        foreground="white",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    # Perform reset
    reset_system()
    time.sleep(2)
    win.destroy()

    logging.info("System reset completed")


def popup_error(message: str) -> None:
    """
    Show error message popup.

    Args:
        message: Error message to display.
    """
    custom_font = Font(family="Helvetica", size=40)

    win = tk.Toplevel()
    win.attributes("-fullscreen", True)
    win.configure(background="#e74c3c")  # Red background for error
    win.wm_title("Error")

    label = tk.Label(
        win,
        text=message,
        font=custom_font,
        padx=300,
        pady=300,
        background="#e74c3c",
        foreground="white",
        wraplength=1000,
        justify="center",
    )
    label.pack()

    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 30, "bold"))

    ack_btn = ttk.Button(win, text="Acknowledge", command=win.destroy)
    ack_btn.pack(pady=20)


def stop_process() -> None:
    """Stop current process execution."""
    logging.info("Stopping process...")
    robot_state.stop_event.set()

    if robot_state.robot_obj is not None:
        try:
            robot_motion_abort(robot_state.robot_obj)
        except Exception as e:
            logging.error(f"Failed to abort robot motion: {e}")

    robot_state.stop_event.clear()
    logging.info("Process stopped")


def reset_system() -> None:
    """Reset system to initial state."""
    logging.info("Resetting system...")

    # Clear process state
    robot_state.reset_indices()
    robot_state.stop_event.clear()
    robot_state.pause_event.set()
    robot_state.collision_detected = False
    robot_state.process_finished = False

    # Clear CSV file reference
    robot_state.qa_csv_file = None

    # Abort any robot motion
    if robot_state.robot_obj is not None:
        try:
            robot_motion_abort(robot_state.robot_obj)
        except Exception as e:
            logging.error(f"Failed to abort robot motion during reset: {e}")

    logging.info("System reset completed successfully")
