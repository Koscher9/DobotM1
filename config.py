"""Runtime settings for the Dobot M1 lab connection."""

DOBOT_URI = "ws://192.168.50.150:54321"

# Keep the hold-to-jog speed low until all directions have been verified.
JOG_VELOCITY_RATIO = 10.0
JOG_ACCEL_RATIO = 10.0

POSE_POLL_MS = 250
CONNECT_TIMEOUT_S = 5.0
COMMAND_TIMEOUT_S = 1.5
LOG_DIR = "logs"
