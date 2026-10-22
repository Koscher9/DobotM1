"""Runtime settings for the Dobot M1 lab connection."""

DOBOT_URI = "ws://192.168.0.97:54321"

# Hold-to-jog starts conservatively. Raise in the UI if the arm feels too slow.
JOG_VELOCITY_RATIO = 25.0
JOG_ACCEL_RATIO = 25.0

POSE_POLL_MS = 250
CONNECT_TIMEOUT_S = 5.0
COMMAND_TIMEOUT_S = 1.5
LOG_DIR = "logs"
