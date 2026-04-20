"""Constants for Show Control integration."""

DOMAIN = "showcontrol"

PLATFORMS = ["number", "switch", "button", "select"]

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_PROFILE = "profile"
CONF_PROFILE_NAME = "profile_name"
CONF_PROFILE_CONTENT = "profile_content"
CONF_SOURCE_PORT = "source_port"
CONF_FEEDBACK_PORT = "feedback_port"

# Coordinator
COORDINATOR = "coordinator"
PROFILE_DATA = "profile_data"

# Transport types
TRANSPORT_OSC_UDP = "osc_udp"

# Default values
DEFAULT_PORT = 7700
DEFAULT_SOURCE_PORT = 0  # 0 = OS assigns
DEFAULT_FEEDBACK_PORT = 9000
DEFAULT_KEEPALIVE_INTERVAL = 8  # seconds

# Profile folder name (relative to integration directory)
PROFILES_DIR = "profiles"

# Workaround keys
WORKAROUND_IGNORE_FEEDBACK = "ignore_feedback"
WORKAROUND_NO_KEEPALIVE_CHECK = "no_keepalive_check"
