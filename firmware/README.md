# Sticker Feeder Firmware

## Overview

This directory contains the Arduino firmware for the automated sticker feeder subsystem of the industrial pick-and-place vision system. The firmware controls a NEMA 17 stepper motor with integrated distance sensing to manage a magazine of adhesive stickers for automated component placement.

## Hardware Stack

### Microcontroller
- **Arduino Uno or Mega** (or compatible)
- 5V logic levels
- At least 6 digital pins + 1 analog input

### Motor System
- **NEMA 17 Stepper Motor**
  - 200 steps per revolution
  - Rated 12-24V DC
- **64:1 Planetary Gear Reduction**
  - Provides precise positioning with high holding torque
  - Effective resolution: 50 steps per millimeter
- **DRV8825 Stepper Driver**
  - Microstepping: 16x mode (factory wired on this system)
  - Maximum current: 2.2A per phase

### Positioning Sensor
- **Sharp GP2Y0A41SK0F Infrared Distance Sensor**
  - Range: 40-300mm
  - Analog output: 0.8-3.5V (inverse relationship to distance)
  - Purpose: Detect sticker edge position for verification

### Laser Positioning
- **5mW Red Laser Diode (650nm)**
  - Highlights the current sticker for vision system detection
  - Controlled via PWM pin for brightness adjustment

## Pin Connections

### Stepper Motor Control (DRV8825)
| Pin | Arduino Pin | Signal | Description |
|-----|-------------|--------|-------------|
| STEP | Digital 2 | Step pulse | Triggers one motor step on rising edge |
| DIR | Digital 3 | Direction | HIGH=forward, LOW=backward |
| ENA | Digital 8 | Enable | LOW=enabled, HIGH=disabled (active low) |
| GND | GND | Ground | Common reference |
| +5V | 5V | Logic power | Microcontroller power supply |

### Distance Sensor (Sharp IR)
| Pin | Arduino Pin | Signal | Description |
|-----|-------------|--------|-------------|
| OUT | Analog A6 | Analog output | Distance measurement (0.8-3.5V) |
| GND | GND | Ground | Common reference |
| +5V | 5V | Supply voltage | Sensor power (5V required) |

### Laser Control
| Pin | Arduino Pin | Signal | Description |
|-----|-------------|--------|-------------|
| +5V | Digital 10 (PWM) | Laser power | On/off control (can use PWM for brightness) |
| GND | GND | Ground | Common reference |

## Serial Protocol

### Communication Settings
- **Baud Rate:** 9600
- **Data Format:** 8 bits, 1 stop bit, no parity
- **Line Ending:** Newline character (\n)
- **Timeout:** 2 seconds

### Command Format
Commands are sent as ASCII strings consisting of numeric codes, followed by a newline character.

**Example:** `79\n` (move 2mm)

### Supported Commands

#### 97 - Zero-In (Home)
```
Command: 97
Response: success
Description: Move stepper motor backward to mechanical home position
Use Case: Initialize feeder position at system startup or after an error
```

#### 13 - Front Board
```
Command: 13
Response: Done (if successful) or error
Description: Position feeder for front board component sticker
Use Case: Before each front board pick operation
Actions: 
  - Activate positioning laser
  - Verify sticker edge distance matches front board lookup table
  - Deactivate laser
```

#### 31 - Back Board
```
Command: 31
Response: Done (if successful) or error
Description: Position feeder for back board component sticker
Use Case: Before each back board pick operation
Actions:
  - Activate positioning laser
  - Verify sticker edge distance matches back board lookup table
  - Deactivate laser
```

#### 37 - Reset
```
Command: 37
Response: success
Description: Reset feeder to safe state
Use Case: Emergency stop or system shutdown
Actions:
  - Disable motor
  - Turn off laser
  - Clear current position tracking
```

#### 79 - Move 2mm
```
Command: 79
Response: success
Description: Advance sticker magazine by 2mm (to next sticker position)
Use Case: After each successful component pick
Distance: 2mm (100 stepper steps)
```

### Response Codes

| Response | Meaning | Action |
|----------|---------|--------|
| `success` | Command executed successfully | Continue with next operation |
| `Done` | Operation completed with verification | Sticker positioned and verified |
| `error` | Command failed or invalid | Log error, retry or reset |

### Example Communication Sequence

```
Host Command:    97\n
Arduino Response: success
[Motor moves to home position]

Host Command:    79\n
Arduino Response: success
[Motor advances 2mm]

Host Command:    13\n
Arduino Response: Done
[Front board sticker position verified]

Host Command:    79\n
Arduino Response: success
[Advance to next sticker]
```

## Motor Control Details

### Stepping Mechanism
- **Microstepping:** 16x (DRV8825 configured)
- **Effective Steps per mm:** 50
- **Step Timing:** 1000µs per step (configurable for speed adjustment)
- **Direction Control:** DIR pin HIGH = forward, LOW = backward

### Movement Examples
- Move 1 sticker (2mm): 100 steps
- Move to home (32mm): 1600 steps
- Step speed adjustment: Modify `STEP_DELAY_US` in firmware (currently 1000µs)

### Motor Enable/Disable
- **Enable:** Set ENA pin LOW (supplies current to motor coils)
- **Disable:** Set ENA pin HIGH (removes current, no holding force)
- Strategy: Enable during movement, disable when idle to save power

## Distance Sensor Calibration

### Background
The Sharp GP2Y0A41SK0F sensor provides analog output inversely proportional to distance. The firmware converts ADC readings to millimeter distances using a calibration formula.

### Calibration Steps

1. **Measure Reference Distances**
   - Place reference object at known distances (e.g., 50mm, 100mm, 200mm, 300mm)
   - Record the analog ADC value for each distance

2. **Create Calibration Table**
   - Plot ADC values vs. measured distances
   - Determine linear approximation: `distance = a * ADC + b`

3. **Update Firmware**
   - Modify the distance conversion formula in `readSensorDistance()`:
   ```cpp
   float distance = YOUR_COEFFICIENT_A * average + YOUR_COEFFICIENT_B;
   ```

4. **Verify**
   - Use the `debugSensorReading()` function to print raw sensor values
   - Compare calculated distances with actual measurements

### Sticker Edge Distance Tables

The firmware includes lookup tables for sticker edge distances:

- **FRONT_EDGE_DISTANCES[]** - Expected distances for each front board sticker position
- **BACK_EDGE_DISTANCES[]** - Expected distances for each back board sticker position

**Calibration Process:**
1. Move sticker magazine to each position
2. Record the actual distance measured by the sensor
3. Update the corresponding array in firmware
4. Tolerance: ±5mm is acceptable for verification

## Firmware Upload

### Prerequisites
- Arduino IDE (version 1.8.x or later)
- USB cable for Arduino
- Correct board selected in IDE (Tools > Board)

### Upload Steps

1. **Open the IDE**
   ```
   Arduino IDE > Open > sticker_feeder.ino
   ```

2. **Configure Board**
   - Tools > Board > Arduino Uno (or Mega, as applicable)
   - Tools > Port > Select correct COM port

3. **Verify Compilation**
   - Sketch > Verify/Compile
   - Check for errors in console

4. **Upload to Arduino**
   - Sketch > Upload
   - Wait for "Done uploading" message

5. **Verify Operation**
   - Tools > Serial Monitor (baud: 9600)
   - Send test command: `97` (zero-in)
   - Should see: `success` response

## Testing Checklist

### Pre-Deployment Tests

- [ ] Motor moves forward on "79" command
- [ ] Motor moves backward on "97" command  
- [ ] Motor disables after movement completes
- [ ] Laser activates on "13" and "31" commands
- [ ] Laser deactivates after positioning
- [ ] Distance sensor reads stable values
- [ ] Commands timeout correctly if motor stalls
- [ ] Reset command returns to safe state

### System Integration Tests

- [ ] Firmware responds to all 5 command types
- [ ] Response strings match main software expectations
- [ ] Motor speed is appropriate for cycle time
- [ ] No jitter or vibration in final position
- [ ] Serial communication is reliable at 9600 baud
- [ ] Emergency reset works (Arduino reset button)

## Troubleshooting

### Motor Not Moving
- Check power supply to DRV8825 (should be 12-24V)
- Verify ENA pin is connected and set LOW
- Check motor connector orientation
- Test with simpler code to eliminate software issues

### Distance Sensor Readings Unstable
- Check sensor supply voltage (should be steady 5V)
- Move sensor away from other IR sources
- Verify analog pin is A6
- Increase `SENSOR_READ_COUNT` in firmware for averaging

### Commands Not Received
- Verify baud rate (should be 9600)
- Check USB cable connection
- Ensure line endings are LF only, not CRLF
- Test with Arduino Serial Monitor

### Sticker Positioning Errors
- Re-calibrate distance sensor (see calibration section)
- Update `FRONT_EDGE_DISTANCES[]` and `BACK_EDGE_DISTANCES[]` arrays
- Check mechanical alignment of sticker magazine
- Increase tolerance value in comparison logic

## Safety Considerations

- **Motor Torque:** The 64:1 reduction provides significant holding force - keep fingers clear
- **Stepper Heat:** Monitor for excessive heating; reduce step rate if needed
- **Laser Safety:** Red laser is Class 3R - avoid direct eye exposure
- **Supply Voltage:** Ensure proper 12V supply to DRV8825 to avoid underperformance
- **Emergency Stop:** Reset Arduino button provides immediate power disconnect

## Future Enhancements

- [ ] Add homing sensor (limit switch) for more reliable zero-in
- [ ] Implement velocity ramp-up/ramp-down for smoother motion
- [ ] Add accelerometer for mechanical vibration detection
- [ ] Implement temperature monitoring for thermal management
- [ ] Add watchdog timer for automatic error recovery

## References

- NEMA 17 Stepper: [TechSpecs](https://www.nema.org/Standards/Pages/Stepper-Motors.aspx)
- DRV8825 Driver: [TI Datasheet](https://www.ti.com/product/DRV8825)
- Sharp GP2Y0A41SK0F: [Sharp Datasheet](https://www.sharpsensor.com)
- Arduino PWM: [Arduino Reference](https://www.arduino.cc/reference/en/language/functions/analog-io/analogwrite/)
