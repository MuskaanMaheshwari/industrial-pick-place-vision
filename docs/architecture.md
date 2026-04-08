# Industrial Pick-and-Place Vision System - Architecture Document

## 1. System Overview

The Industrial Pick-and-Place Vision System is an automated robotic assembly platform that combines high-precision robotics, real-time computer vision, and Arduino-based hardware control to pick and place components on PCB assemblies. The system handles multiple board types (front/back), manages component stickers through an automated magazine, and uses camera-based verification for quality assurance.

### Core Capabilities
- Real-time board detection and alignment
- Multi-board type support (front, back, custom)
- Automated sticker magazine management
- Vacuum-based component handling with 4 different adapters
- Speed-optimized cycle times (~45 seconds per board)
- Full error recovery and retry logic

## 2. Hardware Stack

### 2.1 Robotic Arm
- **Type**: ABB Industrial Robot (6-axis collaborative)
- **IP Address**: 192.168.1.120
- **Control Interface**: TCP/IP socket communication
- **Motion Capabilities**:
  - XYZ positioning with millimeter precision
  - 6-axis orientation control (RX, RY, RZ)
  - Speed range: 0-1000 mm/min
  - Acceleration: configurable 0-500 mm/s²

### 2.2 Vision System
- **Primary Camera**: Cognex Industrial Vision System
- **IP Address**: 192.168.1.130
- **Streams**:
  - HTTP port 1880: Image streaming
  - Data port 5001: Vision processing API
- **Resolution**: 1280x960 pixels
- **Calibration**: Pixel-to-millimeter conversion factors per board type

### 2.3 Sticker Feeder Control
- **Microcontroller**: Arduino Uno/Mega
- **Serial Port**: COM3 @ 9600 baud
- **Motor**: NEMA 17 stepper with 64:1 reduction
- **Sensor**: Sharp IR distance sensor for edge detection
- **Laser**: 5mW red laser for position verification

### 2.4 Vacuum System
- **Vacuum Adapters**: 4 variants (15B, 5C, 3D, 5RtA)
- **Control**: Via robot recipes
- **Pressure Sensing**: Built into robot feedback

## 3. Software Architecture

### 3.1 Module Hierarchy

```
application/
├── main.py                    # Entry point, CLI interface
├── config/
│   ├── config_loader.py      # YAML parsing, validation
│   └── constants.py          # System constants
├── hardware/
│   ├── robot_controller.py   # ABB robot TCP communication
│   ├── vision_system.py      # Cognex camera interface
│   └── arduino_feeder.py     # Sticker feeder serial control
├── vision/
│   ├── board_detector.py     # Board detection and alignment
│   ├── image_processor.py    # Pixel conversion, calibration
│   └── edge_finder.py        # Component edge identification
├── execution/
│   ├── sequence_executor.py  # CSV-based sequence playback
│   ├── motion_planner.py     # Trajectory generation
│   └── cycle_manager.py      # Cycle timing and throughput
├── control/
│   ├── state_machine.py      # System state management
│   ├── error_handler.py      # Exception handling, recovery
│   └── logger.py             # Comprehensive logging
└── utils/
    ├── serial_utils.py       # Serial port management
    └── math_utils.py         # Coordinate transformations
```

### 3.2 Configuration System

The system uses YAML-based configuration with hierarchy:

1. **Default Configuration** (`config.yaml`)
   - Placeholder IP addresses and calibration values
   - All parameter names and structure defined
   - Must be copied and customized per installation

2. **Example Configuration** (`config.example.yaml`)
   - Real calibration values from original system
   - Reference for new setups
   - Never loaded by system

3. **Runtime Validation**
   - Type checking for all parameters
   - Range validation for coordinates and speeds
   - Connection verification on startup

### 3.3 Key Data Structures

#### Board Detection Result
```python
{
    "detected": True,
    "confidence": 0.92,
    "center_pixel_x": 640,
    "center_pixel_y": 480,
    "orientation": -2.5,           # degrees
    "board_type": "front",         # or "back"
    "timestamp": 1234567890.123
}
```

#### Sequence Step
```python
{
    "index": 5,
    "sticker_number": "Sticker_006",
    "arduino_signal": "13",         # "13" (front), "31" (back), "79" (advance)
    "vacuum_cup": "15B",
    "pick_pose": {"x": 350.5, "y": 280.3, "z": 380, "rx": 180, "ry": 0, "rz": -40},
    "place_pose": {"x": 365.2, "y": 290.1, "z": 400, "rx": 180, "ry": 0, "rz": -40},
    "robot_recipes": {"pick": "recipe_front_pick", "place": "recipe_front_place"}
}
```

## 4. Vision Pipeline

### 4.1 Image Acquisition Flow

```
Camera captures image
    ↓
HTTP request to Cognex (port 1880)
    ↓
Raw image received (1280x960)
    ↓
Store in memory / disk
    ↓
Process for board detection
```

**Timing**: 
- Acquisition: ~200ms
- Network latency: ~50ms
- Total: ~250ms per image

### 4.2 Board Detection Algorithm

1. **Preprocessing**
   - Convert to grayscale
   - Apply edge detection (Canny: threshold=50)
   - Dilate/erode for noise reduction

2. **Contour Detection**
   - Find all contours with area > 5000 pixels
   - Filter by shape (rectangular)
   - Calculate centroid and orientation

3. **Calibration Matching**
   - Compare detected center pixel with known board center
   - Calculate offset in pixels
   - Convert to millimeters using calibration factor
   - Report as adjustment vector to robot

4. **Quality Metrics**
   - Confidence score based on contour fit
   - Variance in edge detection
   - Timestamp for synchronization

### 4.3 Pixel-to-Millimeter Conversion

Each board type has a unique calibration factor:

```
front_board:    0.0486 mm/pixel
back_board:     0.04827 mm/pixel
sticker_feeder: 0.0659 mm/pixel
```

Conversion formula:
```
distance_mm = (pixel_offset_x) × calibration_factor
```

**Calibration Process**:
1. Move robot known distance (e.g., 50mm)
2. Capture images at start and end
3. Measure pixel shift in images
4. Calculate: factor = distance_mm / pixel_shift
5. Repeat for verification at multiple positions

## 5. Pick-Place Cycle Timing

### 5.1 Complete Cycle Breakdown (45 second target)

| Phase | Action | Typical Time | Notes |
|-------|--------|--------------|-------|
| Vision | Capture board image | 0.5s | Parallel with robot movement |
| Board Detection | Find corners, alignment | 1.0s | Confidence threshold check |
| Arduino Prep | Send board signal (13/31) | 0.2s | Verify distance sensor |
| Motion 1 | Move to pick position | 3.0s | Includes acceleration/deceleration |
| Pick | Vacuum engage + recipe | 2.0s | Recipe execution time |
| Motion 2 | Move to place position | 3.0s | Different path than pick |
| Place | Vacuum release + recipe | 2.0s | Recipe execution time |
| Arduino Advance | Move magazine 2mm | 1.0s | Prepare for next sticker |
| Idle/Buffer | Synchronization gaps | 30.3s | Parallel processing reduces |
| **Total** | | **~45s** | Highly parallelizable |

### 5.2 Parallelization Opportunities

```
Timeline:

T=0s    [Robot] Move to home
        [Vision] Capture image
        [Arduino] Initialize position

T=1s    [Vision] Process board detection ◄────────────┐
        [Robot] Move to pick position                  │
                                                       │ Parallel
T=4s    [Vision] Finished, waiting ────────────────────┘
        [Robot] Engage vacuum, pick

T=6s    [Robot] Move to place position
        [Vision] Start next image capture

T=9s    [Robot] Place component, release vacuum
        [Vision] Image ready for next board

T=10s   [Arduino] Advance magazine
        [Robot] Return to home
```

## 6. Thread Synchronization Model

### 6.1 Threading Architecture

The system uses 3 concurrent threads for optimal throughput:

```python
Main Thread (Cycle Coordinator):
├── State machine
├── Sequence loading
├── Error handling
├── Logging

Robot Thread:
├── TCP communication with ABB robot
├── Motion command queuing
├── Feedback reading
└── Timeout detection

Vision Thread:
├── HTTP requests to Cognex
├── Image processing (board detection)
├── Calibration calculations
└── Result caching

Arduino Thread:
├── Serial port communication
├── Command buffering
├── Response parsing
└── Retry logic
```

### 6.2 Synchronization Primitives

**Event Objects**: Used for phase synchronization
```python
vision_ready = threading.Event()      # Set when image processed
motion_ready = threading.Event()      # Set when robot positioned
arduino_ready = threading.Event()     # Set when feeder confirmed
```

**Queues**: For command/response passing
```python
robot_command_queue = queue.Queue()   # Commands to robot
arduino_response_queue = queue.Queue() # Arduino responses
```

**Locks**: For shared resource access
```python
config_lock = threading.RLock()       # Protect config reads
log_lock = threading.Lock()           # Serialize log writes
```

### 6.3 Cycle Synchronization Example

```
Cycle N start (vision still processing board N-1)

1. Main waits for vision_ready (board N-1 result)
2. Queue motion command to robot (based on board N-1)
3. Queue arduino command to feeder
4. Set vision event to process board N
5. Main thread waits for motion_ready and arduino_ready

Meanwhile (parallel):
- Vision thread processes board N
- Robot thread executes motion
- Arduino thread advances magazine

When all ready:
- Pick component
- Place component
- Advance magazine
- Start next cycle
```

## 7. Configuration System

### 7.1 Configuration Hierarchy

```yaml
robot:
  ip_address: String (required)
  command_port: Integer
  speeds: {default, waypoint}
  accelerations: {default, waypoint}
  home_pose: {x, y, z, rx, ry, rz}
  pick_place_pose: {...}

vision:
  camera_ip: String (required)
  http_port, data_port: Integer
  calibration:
    pixel_factors: {front, back, sticker}
    camera_offsets: {board_center_x, board_center_y, z_offset}

arduino:
  port: String (e.g., "COM3")
  baudrate: Integer
  motor: {pins, microstepping, gear_ratio}
  laser_sensor: {pin, calibration}
  sticker_edges: {front_distances, back_distances}

recipes:
  front_board, back_board, sticker_feeder: {id, description, time}

vacuum_adapters:
  adapter_15B, 5C, 3D, 5RtA: {z_correction, grip_force}

logging:
  level: String (DEBUG/INFO/WARNING/ERROR)
  files: {system, motion, vision}
  rotation: {max_size, backup_count}
```

### 7.2 Validation Rules

- Robot IP must be reachable (ping before startup)
- Vision camera must respond on HTTP port
- Arduino port must exist and open at correct baud rate
- Pixel factors must be > 0
- Poses must have valid XYZ ranges
- Speed/accel must be within robot limits

## 8. Error Handling and Retry Logic

### 8.1 Error Categories

| Error Type | Example | Recovery |
|-----------|---------|----------|
| **Network** | Robot timeout | Retry 3x with 1s delay, escalate |
| **Hardware** | Arduino port closed | Reconnect, sync state |
| **Vision** | Board not detected | Re-acquire image, check lighting |
| **Motion** | Out of range coordinate | Validate pose, use home fallback |
| **Sticker** | Magazine empty | Prompt user, pause cycle |

### 8.2 Retry Strategy

```python
for attempt in range(retry_attempts):
    try:
        execute_operation()
        return success
    except TemporaryError as e:
        wait(retry_delay)
        continue
    except PermanentError as e:
        log_error(e)
        trigger_manual_recovery()
        break
```

### 8.3 Recovery Modes

1. **Automatic Recovery** (transparent to operator)
   - Retry network operations
   - Re-acquire vision data
   - Resend serial commands

2. **Semi-Automatic Recovery** (pause and notify)
   - Sticker magazine empty → load new magazine
   - Gripper jam → reset vacuum system
   - Lighting issue → adjust camera

3. **Manual Recovery** (operator intervention required)
   - Collision detected → move arm manually
   - Gripper broken → replace adapter
   - System calibration drift → recalibrate

## 9. Logging System

### 9.1 Log Levels and Destinations

```
system.log:
- Application state changes
- Cycle start/completion
- Configuration loaded
- Errors and exceptions
- Performance metrics

motion.log:
- Robot command sent
- Robot response received
- Actual pose achieved
- Timing information

vision.log:
- Image acquired timestamp
- Board detection results
- Pixel offset calculations
- Confidence scores
```

### 9.2 Log Retention

- Max file size: 10 MB per log
- Backup count: 5 previous files
- Archive old logs for analysis
- Rotation: Automatic when size limit hit

## 10. Performance Metrics

### 10.1 Throughput Target

- **Cycle time**: 45 seconds per board
- **Throughput**: ~80 boards/hour (single operator)
- **Uptime target**: 95% (excluding manual setup)

### 10.2 Key Metrics Tracked

```
Per-cycle metrics:
- Total cycle time
- Vision acquisition time
- Robot motion time
- Arduino communication time
- Idle/sync time

Aggregate metrics:
- Cycles completed per hour
- Errors encountered
- Retry attempts needed
- Vision accuracy (detection rate)
```

## 11. Deployment Checklist

- [ ] Network connectivity verified (robot, camera, Arduino)
- [ ] IPs configured in config.yaml
- [ ] Calibration factors validated
- [ ] Robot recipes created and tested
- [ ] Arduino firmware uploaded
- [ ] Vision system trained on board types
- [ ] Sequence files created for each assembly
- [ ] Dry run completed (no stickers)
- [ ] Operator training completed
- [ ] Emergency stop tested
- [ ] Logging verified
- [ ] Performance benchmarked

## 12. References and Standards

- **Robot**: ABB FlexPendant TCP/IP Protocol
- **Vision**: Cognex IS7010 Vision System API
- **Arduino**: Standard AVR C++ libraries
- **Communication**: IEEE 802.3 Ethernet, RS-232 Serial
- **Coordinate System**: ISO 10791-1 (machine tool coordinates)
