# Pick-and-Place Sequence Files

## Overview

This directory contains CSV files that define the complete pick-and-place sequences for each PCB assembly configuration. Each row represents a single component pick operation with all required parameters: position, orientation, vacuum adapter, sticker index, and robot recipe ID.

## CSV Format Specification

### File Naming Convention
- `front_example.csv` - Example sequence for front board assembly
- `back_example.csv` - Example sequence for back board assembly
- `{board_type}_production.csv` - Production sequences (if applicable)

### Column Definitions

| Column | Data Type | Description | Example |
|--------|-----------|-------------|---------|
| **Index** | Integer | Sequence step number (0-based) | 0, 1, 2... |
| **ArduinoSignal** | String | Command sent to Arduino sticker feeder | "13", "31", "79" |
| **ArduinoDistance** | Integer | Expected sticker edge distance (mm) | 150, 155... |
| **StickerPickIndex** | Integer | Index in sticker magazine (0-based) | 0, 1, 2... |
| **StickerNumber** | String | Sticker ID or description | "Sticker_001", "Resistor_10k"... |
| **Section** | String | Board section/region | "Top", "Bottom", "Left"... |
| **IC** | String | Integrated circuit identifier (if applicable) | "U1", "U2", "NONE"... |
| **Block** | String | Logical block or functional group | "Power", "Control", "Sensor"... |
| **VacuumCup** | String | Vacuum adapter ID to use | "15B", "5C", "3D", "5RtA" |
| **Pick_X** | Float | X coordinate for pick position (mm) | 350.5 |
| **Pick_Y** | Float | Y coordinate for pick position (mm) | 280.3 |
| **Pick_Z** | Float | Z coordinate for pick position (mm) | 380.0 |
| **Pick_RX** | Float | Rotation around X axis at pick (degrees) | 180 |
| **Pick_RY** | Float | Rotation around Y axis at pick (degrees) | 0 |
| **Pick_RZ** | Float | Rotation around Z axis at pick (degrees) | -40 |
| **Place_X** | Float | X coordinate for place position (mm) | 365.2 |
| **Place_Y** | Float | Y coordinate for place position (mm) | 290.1 |
| **Place_Z** | Float | Z coordinate for place position (mm) | 400.0 |
| **Place_RX** | Float | Rotation around X axis at place (degrees) | 180 |
| **Place_RY** | Float | Rotation around Y axis at place (degrees) | 0 |
| **Place_RZ** | Float | Rotation around Z axis at place (degrees) | -40 |
| **PICK** | String | Robot recipe ID for pick operation | "recipe_front_pick" |
| **PLACE** | String | Robot recipe ID for place operation | "recipe_front_place" |

## Example Sequence Row Explanation

Here's a detailed breakdown of what happens in a single sequence row:

```csv
Index,ArduinoSignal,ArduinoDistance,StickerPickIndex,StickerNumber,Section,IC,Block,VacuumCup,Pick_X,Pick_Y,Pick_Z,Pick_RX,Pick_RY,Pick_RZ,Place_X,Place_Y,Place_Z,Place_RX,Place_RY,Place_RZ,PICK,PLACE

0,13,150,0,Sticker_001,Top,U1,Power,15B,350.5,280.3,380,180,0,-40,365.2,290.1,400,180,0,-40,recipe_front_pick,recipe_front_place
```

### Execution Flow for This Row

1. **Arduino Command (13)**: Signal front board sticker position
   - Expected distance: 150mm
   - Sticker magazine advances to position 0
   - Positioning laser activates and verifies sticker edge

2. **Pick Phase**:
   - Robot moves to position (350.5, 280.3, 380) with orientation (180, 0, -40)
   - Vacuum cup "15B" (15B adapter) is activated
   - Execute "recipe_front_pick" robot recipe
   - Sticker is pulled from magazine

3. **Place Phase**:
   - Robot moves to position (365.2, 290.1, 400) with orientation (180, 0, -40)
   - Sticker is placed at target position
   - Execute "recipe_front_place" robot recipe
   - Vacuum is released

4. **Advance Magazine**:
   - Command "79" sent to Arduino (advance 2mm)
   - Magazine moves to next sticker position
   - Sticker pick index increments for next operation

## Creating New Sequences

### Step 1: Define Board Layout
Sketch or photograph the PCB to identify:
- Component locations and required positions
- Board sections and functional blocks
- Required vacuum adapters for different component sizes

### Step 2: Record Reference Positions
Using the robot teach pendant or software:
- Move robot to each component's pick position
- Record X, Y, Z, RX, RY, RZ coordinates
- Record optimal vacuum cup for that component
- Test approach angles to avoid collisions

### Step 3: Verify Sticker Alignment
- Load each unique sticker in the magazine
- Activate positioning laser
- Record distance reading for calibration
- Mark sticker position and index number

### Step 4: Build CSV File
- Use spreadsheet editor (Excel, Google Sheets, or text editor)
- Enter headers exactly as shown in "Column Definitions"
- Add one row per component
- Maintain sequential Index values (0, 1, 2, ...)
- Verify all coordinate values are accurate

### Step 5: Test Execution
- Load sequence into main software
- Perform dry-run (no stickers)
- Check for collisions and timing issues
- Adjust coordinates if needed
- Run with actual stickers

## CSV Example Files

### front_example.csv Content

```csv
Index,ArduinoSignal,ArduinoDistance,StickerPickIndex,StickerNumber,Section,IC,Block,VacuumCup,Pick_X,Pick_Y,Pick_Z,Pick_RX,Pick_RY,Pick_RZ,Place_X,Place_Y,Place_Z,Place_RX,Place_RY,Place_RZ,PICK,PLACE
0,13,150,0,Sticker_001,Top,U1,Power,15B,350.5,280.3,380,180,0,-40,365.2,290.1,400,180,0,-40,recipe_front_pick,recipe_front_place
1,13,150,1,Sticker_002,Top,U2,Control,5C,340.2,275.1,385,180,0,-40,355.8,285.3,400,180,0,-40,recipe_front_pick,recipe_front_place
2,13,150,2,Sticker_003,Middle,U3,Sensor,3D,330.0,280.0,390,180,0,-40,345.5,290.0,400,180,0,-40,recipe_front_pick,recipe_front_place
3,13,150,3,Sticker_004,Bottom,U4,Comm,5RtA,320.5,275.5,380,180,0,-40,335.2,285.1,400,180,0,-40,recipe_front_pick,recipe_front_place
```

### back_example.csv Content

```csv
Index,ArduinoSignal,ArduinoDistance,StickerPickIndex,StickerNumber,Section,IC,Block,VacuumCup,Pick_X,Pick_Y,Pick_Z,Pick_RX,Pick_RY,Pick_RZ,Place_X,Place_Y,Place_Z,Place_RX,Place_RY,Place_RZ,PICK,PLACE
0,31,155,0,BackSticker_001,Top,U5,Power,15B,320.0,270.0,380,180,0,-50,335.1,280.2,400,180,0,-50,recipe_back_pick,recipe_back_place
1,31,155,1,BackSticker_002,Middle,U6,Control,5C,310.5,265.5,385,180,0,-50,325.8,275.3,400,180,0,-50,recipe_back_pick,recipe_back_place
2,31,155,2,BackSticker_003,Bottom,U7,IO,3D,300.0,270.0,390,180,0,-50,315.5,280.0,400,180,0,-50,recipe_back_pick,recipe_back_place
```

## Important Notes

### Coordinate System
- **X, Y**: Horizontal plane (mm from robot origin)
- **Z**: Vertical axis (mm, 0 = working surface)
- **RX, RY, RZ**: Euler angles in degrees (tool orientation)

### Vacuum Adapter Selection
Choose based on component size and weight:
- **15B**: Standard/default for most components
- **5C**: Medium components (lighter than 15B)
- **3D**: Lightweight components
- **5RtA**: Rotating components or special alignment needs

### Arduino Signals
- **13**: Front board position (uses FRONT_EDGE_DISTANCES)
- **31**: Back board position (uses BACK_EDGE_DISTANCES)
- **79**: Advance magazine 2mm (done automatically between rows)

### Troubleshooting

**Sticker not picked:**
- Check VacuumCup selection for that row
- Verify ArduinoDistance matches actual sensor reading
- Confirm sticker magazine is loaded correctly

**Component placed incorrectly:**
- Verify Place_X, Place_Y, Place_Z coordinates
- Check Place_RX, Place_RY, Place_RZ orientations
- Confirm robot recipe ID exists

**Magazine advance fails:**
- Check ArduinoSignal is correct for board type
- Verify Arduino is responding to serial commands
- Check "79" command executes after each placement

## Version Control

- Keep production sequences in version control
- Document changes with comments in CSV headers
- Archive old sequences for reference
- Maintain backup of validated sequences
