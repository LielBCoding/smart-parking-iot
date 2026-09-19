# Central configuration for the SmartPark system.
# Every component (emulators, data manager, dashboard) imports this file,
# so changing the broker or the thresholds is done in one place only.

# broker
BROKER_HOST = "broker.hivemq.com"   # public test broker, no account needed
BROKER_PORT = 1883
USERNAME = ""                       # leave empty for the public broker
PASSWORD = ""

# topics
LOT_ID = "lot1"
BASE_TOPIC = "smartpark/" + LOT_ID

TOPIC_SPOT_STATUS = BASE_TOPIC + "/spot/{spot_id}/status"   # spot sensor -> broker
TOPIC_SPOT_WILDCARD = BASE_TOPIC + "/spot/+/status"         # manager / dashboard subscribe
TOPIC_ENV = BASE_TOPIC + "/env"                             # temperature + CO sensor
TOPIC_GATE_EVENT = BASE_TOPIC + "/gate/event"               # entry / exit button panel
TOPIC_ACTUATOR_CMD = BASE_TOPIC + "/actuators/cmd"          # manager -> barrier / sign / fan
TOPIC_ACTUATOR_STATE = BASE_TOPIC + "/actuators/state"      # actuator panel acknowledges
TOPIC_ALERTS = BASE_TOPIC + "/alerts"                       # INFO / WARNING / ALARM messages
TOPIC_SUMMARY = BASE_TOPIC + "/summary"                     # manager -> dashboard, every cycle

# parking lot
SPOT_IDS = ["A1", "A2", "A3", "A4", "A5", "A6"]
CAPACITY = len(SPOT_IDS)

WARNING_OCCUPANCY = 0.8       # 80% occupied -> WARNING
SENSOR_TIMEOUT_SEC = 20       # no heartbeat for 20 s -> sensor considered offline

# air quality
CO_WARNING_PPM = 50
CO_ALARM_PPM = 100
TEMP_ALARM_C = 45

# timing
MANAGER_CYCLE_SEC = 5         # how often the manager re-evaluates the lot
DEFAULT_PUBLISH_INTERVAL = 5  # default emulator publish rate (seconds)

# storage
DB_PATH = "data/smartpark.db"
