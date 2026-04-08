/*
 * Industrial Pick-and-Place Vision System - Sticker Feeder Firmware
 *
 * Purpose: Control NEMA 17 stepper motor for automated sticker feeding with
 *          laser-based distance measurement for precise sticker positioning
 *
 * Hardware:
 *   - Arduino Uno/Mega microcontroller
 *   - NEMA 17 stepper motor with 64:1 gear reduction (DRV8825 driver)
 *   - Sharp GP2Y0A41SK0F infrared distance sensor
 *   - Positioning laser (LED)
 *
 * Serial Protocol: Commands are single/double digit codes followed by newline
 * Baud Rate: 9600
 */

// ============================================================================
// PIN DEFINITIONS
// ============================================================================

// Stepper Motor Control Pins (DRV8825 driver)
const int STEPPER_STEP_PIN = 2;      // Step signal (active HIGH)
const int STEPPER_DIR_PIN = 3;       // Direction control (HIGH=forward, LOW=backward)
const int STEPPER_ENABLE_PIN = 8;    // Motor enable (LOW=enabled, HIGH=disabled)

// Laser Sensor Pin
const int LASER_SENSOR_PIN = A6;     // Analog input for Sharp IR distance sensor

// Laser Positioning Pin
const int LASER_POSITIONING_PIN = 10; // Digital output for positioning laser (PWM capable)

// ============================================================================
// MOTOR CONFIGURATION
// ============================================================================

// Stepper motor specs: NEMA 17 with 200 steps/revolution
// Gear reduction: 64:1
// Microstepping: 16x (configured on DRV8825 driver)
// Therefore: 200 * 16 / 64 = 50 steps per mm of movement

const int STEPS_PER_MM = 50;         // 16x microstepping with 64:1 reduction
const int GEAR_RATIO = 64;           // Gear reduction ratio
const int MICROSTEPPING = 16;        // DRV8825 microstepping mode

// Motor movement parameters
const int MOVE_2MM_STEPS = 2 * STEPS_PER_MM;  // Command "79" moves 2mm

// ============================================================================
// LASER DISTANCE SENSOR CONFIGURATION
// ============================================================================

// Sharp GP2Y0A41SK0F analog distance sensor
// Output: 0.8V at 30cm, 2.3V at 8cm
// We measure distance for sticker edge detection

const int SENSOR_READ_COUNT = 10;    // Average over this many readings
const int SENSOR_DELAY_MS = 10;      // Milliseconds between readings

// Distance calibration values (in mm) for sticker edge detection
// These are EXAMPLE values - calibrate for your specific sticker magazine
// Measure actual distance at each sticker position with a ruler

// Front board sticker positions - edge distances in mm
const int FRONT_EDGE_DISTANCES[] = {
  150, 148, 152, 149, 151, 147, 153, 150,  // Positions 0-7
  149, 151, 148, 152, 150, 149, 151, 150   // Positions 8-15
};
const int FRONT_EDGE_COUNT = sizeof(FRONT_EDGE_DISTANCES) / sizeof(FRONT_EDGE_DISTANCES[0]);

// Back board sticker positions - edge distances in mm
const int BACK_EDGE_DISTANCES[] = {
  155, 153, 157, 154, 156, 152, 158, 155,  // Positions 0-7
  154, 156, 153, 157, 155, 154, 156, 155   // Positions 8-15
};
const int BACK_EDGE_COUNT = sizeof(BACK_EDGE_DISTANCES) / sizeof(BACK_EDGE_DISTANCES[0]);

// Current sticker position tracking
int current_sticker_index = 0;
int current_board_type = 0;  // 0=unknown, 1=front, 2=back

// ============================================================================
// SERIAL COMMAND DEFINITIONS
// ============================================================================

// Commands are sent as ASCII numeric strings, e.g., "97\n"
#define CMD_ZERO_IN "97"              // Home/zero-in command - move to mechanical zero
#define CMD_FRONT_BOARD "13"          // Select front board position
#define CMD_BACK_BOARD "31"           // Select back board position
#define CMD_RESET "37"                // Reset stepper to safe state
#define CMD_MOVE_2MM "79"             // Move 2mm forward (advance sticker)

// Response strings
#define RESPONSE_SUCCESS "success"    // Command executed successfully
#define RESPONSE_DONE "Done"          // Operation completed
#define RESPONSE_ERROR "error"        // Error occurred

// ============================================================================
// GLOBAL STATE VARIABLES
// ============================================================================

boolean motor_enabled = false;        // Track if motor is currently enabled
boolean laser_active = false;         // Track if positioning laser is on
int last_error = 0;                   // Store last error code for debugging

// Stepper motor speed control
const int STEP_DELAY_US = 1000;       // Microseconds between steps
                                      // Adjust for desired speed (lower = faster)

// ============================================================================
// SETUP - RUN ONCE AT STARTUP
// ============================================================================

void setup() {
  // Initialize serial communication
  Serial.begin(9600);

  // Configure stepper control pins as outputs
  pinMode(STEPPER_STEP_PIN, OUTPUT);
  pinMode(STEPPER_DIR_PIN, OUTPUT);
  pinMode(STEPPER_ENABLE_PIN, OUTPUT);

  // Configure laser pins
  pinMode(LASER_SENSOR_PIN, INPUT);
  pinMode(LASER_POSITIONING_PIN, OUTPUT);

  // Initial state: motor disabled, laser off
  digitalWrite(STEPPER_ENABLE_PIN, HIGH);  // Disable motor (active LOW)
  digitalWrite(LASER_POSITIONING_PIN, LOW); // Laser off

  motor_enabled = false;
  laser_active = false;
  current_sticker_index = 0;
  current_board_type = 0;

  Serial.println("Sticker feeder initialized");
}

// ============================================================================
// MAIN LOOP - PROCESS SERIAL COMMANDS
// ============================================================================

void loop() {
  // Check if data is available on serial port
  if (Serial.available() > 0) {
    // Read the command string (numeric code followed by newline)
    String command = Serial.readStringUntil('\n');
    command.trim();  // Remove any whitespace

    // Process the command
    processCommand(command);
  }
}

// ============================================================================
// COMMAND PROCESSING
// ============================================================================

void processCommand(String cmd) {
  if (cmd == "97") {
    // Zero-in command: home the stepper motor
    commandZeroIn();

  } else if (cmd == "13") {
    // Front board command: select front board sticker position
    commandFrontBoard();

  } else if (cmd == "31") {
    // Back board command: select back board sticker position
    commandBackBoard();

  } else if (cmd == "37") {
    // Reset command: move to safe state
    commandReset();

  } else if (cmd == "79") {
    // Move 2mm command: advance sticker feed
    commandMove2mm();

  } else {
    // Unknown command
    Serial.println(RESPONSE_ERROR);
    last_error = 1;
  }
}

// ============================================================================
// COMMAND IMPLEMENTATIONS
// ============================================================================

/*
 * Zero-in command (97)
 * Moves stepper to mechanical home position (position 0)
 * This is typically a hard-stop or mechanical limit position
 */
void commandZeroIn() {
  enableMotor();

  // Move backward (toward home) for a fixed distance to hit mechanical stop
  // Assuming magazine has ~16 positions, move enough to guarantee we hit zero
  moveMotor(STEPPER_BACKWARD, 1600);  // 1600 steps = about 32mm

  // Wait for movement to complete
  delay(500);

  disableMotor();
  current_sticker_index = 0;
  current_board_type = 0;

  Serial.println(RESPONSE_SUCCESS);
}

/*
 * Front board command (13)
 * Prepares the feeder for front board sticker picks
 * Reads and logs the sticker edge distance for the front board position
 */
void commandFrontBoard() {
  if (current_sticker_index >= FRONT_EDGE_COUNT) {
    // Out of stickers on front board
    Serial.println(RESPONSE_ERROR);
    last_error = 2;
    return;
  }

  current_board_type = 1;  // Mark as front board

  // Activate positioning laser to highlight the sticker
  activateLaser();

  // Read the distance to the sticker edge
  int distance = readSensorDistance();

  // Verify we're at the correct position (within tolerance)
  int expected_distance = FRONT_EDGE_DISTANCES[current_sticker_index];
  int tolerance = 5;  // mm tolerance

  if (abs(distance - expected_distance) > tolerance) {
    // Distance doesn't match expected - possible positioning error
    deactivateLaser();
    Serial.println(RESPONSE_ERROR);
    last_error = 3;
    return;
  }

  // Successfully positioned for front board pick
  deactivateLaser();
  Serial.println(RESPONSE_DONE);
}

/*
 * Back board command (31)
 * Prepares the feeder for back board sticker picks
 * Reads and logs the sticker edge distance for the back board position
 */
void commandBackBoard() {
  if (current_sticker_index >= BACK_EDGE_COUNT) {
    // Out of stickers on back board
    Serial.println(RESPONSE_ERROR);
    last_error = 4;
    return;
  }

  current_board_type = 2;  // Mark as back board

  // Activate positioning laser to highlight the sticker
  activateLaser();

  // Read the distance to the sticker edge
  int distance = readSensorDistance();

  // Verify we're at the correct position (within tolerance)
  int expected_distance = BACK_EDGE_DISTANCES[current_sticker_index];
  int tolerance = 5;  // mm tolerance

  if (abs(distance - expected_distance) > tolerance) {
    // Distance doesn't match expected - possible positioning error
    deactivateLaser();
    Serial.println(RESPONSE_ERROR);
    last_error = 5;
    return;
  }

  // Successfully positioned for back board pick
  deactivateLaser();
  Serial.println(RESPONSE_DONE);
}

/*
 * Reset command (37)
 * Returns feeder to a safe state
 * Disables motor and turns off laser
 */
void commandReset() {
  disableMotor();
  deactivateLaser();
  current_sticker_index = 0;
  current_board_type = 0;

  Serial.println(RESPONSE_SUCCESS);
}

/*
 * Move 2mm command (79)
 * Advances the sticker magazine by 2mm to the next position
 * This is called after a successful pick to prepare for the next one
 */
void commandMove2mm() {
  enableMotor();

  // Move forward 2mm = 2 * STEPS_PER_MM steps
  moveMotor(STEPPER_FORWARD, MOVE_2MM_STEPS);

  // Wait for movement to settle
  delay(200);

  disableMotor();
  current_sticker_index++;  // Increment position counter

  Serial.println(RESPONSE_SUCCESS);
}

// ============================================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================================

#define STEPPER_FORWARD HIGH   // Direction for advancing sticker
#define STEPPER_BACKWARD LOW   // Direction for rewinding

/*
 * Enable the stepper motor (allow it to hold position and move)
 * The DRV8825 driver uses active-LOW enable
 */
void enableMotor() {
  digitalWrite(STEPPER_ENABLE_PIN, LOW);   // Enable (active LOW)
  motor_enabled = true;
  delayMicroseconds(100);  // Brief settling time
}

/*
 * Disable the stepper motor (remove holding torque, save power)
 */
void disableMotor() {
  digitalWrite(STEPPER_ENABLE_PIN, HIGH);  // Disable (inactive HIGH)
  motor_enabled = false;
}

/*
 * Move the stepper motor a specified number of steps
 * direction: STEPPER_FORWARD or STEPPER_BACKWARD
 * steps: number of steps to move
 */
void moveMotor(int direction, int steps) {
  // Set direction pin
  digitalWrite(STEPPER_DIR_PIN, direction);
  delayMicroseconds(5);  // Brief settling time for direction change

  // Generate step pulses
  for (int i = 0; i < steps; i++) {
    digitalWrite(STEPPER_STEP_PIN, HIGH);
    delayMicroseconds(STEP_DELAY_US / 2);
    digitalWrite(STEPPER_STEP_PIN, LOW);
    delayMicroseconds(STEP_DELAY_US / 2);
  }
}

// ============================================================================
// LASER CONTROL FUNCTIONS
// ============================================================================

/*
 * Activate the positioning laser
 * This highlights the current sticker for the vision system to detect
 */
void activateLaser() {
  digitalWrite(LASER_POSITIONING_PIN, HIGH);
  laser_active = true;
  delay(50);  // Brief settling time
}

/*
 * Deactivate the positioning laser
 */
void deactivateLaser() {
  digitalWrite(LASER_POSITIONING_PIN, LOW);
  laser_active = false;
}

// ============================================================================
// DISTANCE SENSOR FUNCTIONS
// ============================================================================

/*
 * Read the distance from the infrared distance sensor
 * Returns distance in millimeters (approximate)
 *
 * Sharp GP2Y0A41SK0F characteristic:
 *   Analog output voltage is inversely proportional to distance
 *   This function converts the voltage to distance
 */
int readSensorDistance() {
  int sum = 0;

  // Take multiple readings and average them for noise reduction
  for (int i = 0; i < SENSOR_READ_COUNT; i++) {
    int raw_value = analogRead(LASER_SENSOR_PIN);
    sum += raw_value;
    delayMicroseconds(SENSOR_DELAY_MS * 1000);
  }

  int average = sum / SENSOR_READ_COUNT;

  // Convert analog value to distance in mm
  // This formula depends on your specific sensor calibration
  // Example calibration points:
  //   ADC ~920 (3.5V) = ~80mm
  //   ADC ~400 (1.6V) = ~300mm
  // Linear approximation: distance = a * ADC + b

  // Calibration coefficients (adjust for your sensor)
  float distance = 405.0 - (average / 2.5);  // Simplified formula

  // Constrain to sensor operating range (40-300mm)
  if (distance < 40) distance = 40;
  if (distance > 300) distance = 300;

  return (int)distance;
}

/*
 * Debug function: Print raw sensor readings to serial
 * Useful for calibration and troubleshooting
 */
void debugSensorReading() {
  int distance = readSensorDistance();
  int raw = analogRead(LASER_SENSOR_PIN);

  Serial.print("Sensor Raw: ");
  Serial.print(raw);
  Serial.print(" | Distance: ");
  Serial.print(distance);
  Serial.println(" mm");
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/*
 * Get the number of stickers available for the current board type
 */
int getMaxStickerIndex() {
  if (current_board_type == 1) {
    return FRONT_EDGE_COUNT;
  } else if (current_board_type == 2) {
    return BACK_EDGE_COUNT;
  }
  return 0;
}

/*
 * Report system status (for debugging)
 */
void reportStatus() {
  Serial.print("Motor: ");
  Serial.println(motor_enabled ? "ON" : "OFF");
  Serial.print("Laser: ");
  Serial.println(laser_active ? "ON" : "OFF");
  Serial.print("Board Type: ");
  Serial.println(current_board_type);
  Serial.print("Sticker Index: ");
  Serial.println(current_sticker_index);
  Serial.print("Last Error: ");
  Serial.println(last_error);
}
