# settings shared by all the scripts

# broker
BROKER_HOST = "broker.hivemq.com"   # public test broker, no account needed
BROKER_PORT = 1883
USERNAME = ""                       # leave empty for the public broker
PASSWORD = ""

# topics
LOT_ID = "lot1"
BASE_TOPIC = "smartpark/" + LOT_ID

TOPIC_SPOT_STATUS = BASE_TOPIC + "/spot/{spot_id}/status"  # spot sensor -> broker
TOPIC_SPOT_WILDCARD = BASE_TOPIC + "/spot/+/status"
TOPIC_ENV = BASE_TOPIC + "/env"  # temperature + CO
TOPIC_GATE_EVENT = BASE_TOPIC + "/gate/event"
TOPIC_ACTUATOR_CMD = BASE_TOPIC + "/actuators/cmd"  # manager -> barrier / sign / fan
TOPIC_ACTUATOR_STATE = BASE_TOPIC + "/actuators/state"
TOPIC_ALERTS = BASE_TOPIC + "/alerts"  # INFO / WARNING / ALARM
TOPIC_SUMMARY = BASE_TOPIC + "/summary"

# parking lot
SPOT_IDS = ["A1", "A2", "A3", "A4", "A5", "A6"]
CAPACITY = len(SPOT_IDS)

WARNING_OCCUPANCY = 0.8  # 80% -> WARNING
SENSOR_TIMEOUT_SEC = 20  # sec without a message -> offline

# air quality
CO_WARNING_PPM = 50
CO_ALARM_PPM = 100
TEMP_ALARM_C = 45

# timing
MANAGER_CYCLE_SEC = 5  # sec, manager loop
DEFAULT_PUBLISH_INTERVAL = 5  # sec

# storage
DB_PATH = "data/smartpark.db"
