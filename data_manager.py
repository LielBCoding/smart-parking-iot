"""Data manager: collects everything from the broker into SQLite, checks the
rules, sends INFO / WARNING / ALARM and drives the actuators. No GUI."""
import threading
import time

import config
import db
from mqtt_client import MqttClient, now, parse

WARMUP_SEC = 20   # grace period at startup while the emulators connect

LAST_WILL =(config.TOPIC_ALERTS,
             {"level": "ALARM", "source": "broker",
              "message": "Data manager went offline unexpectedly (last will)"})


class ParkingManager:
    def __init__(self):
        self.mqtt = MqttClient("manager", on_message=self.on_message, will=LAST_WILL)
        self.lock = threading.Lock()

        self.spots = {}
        for spot_id in config.SPOT_IDS:
            self.spots[spot_id] = {"occupied": None, "last_seen": None, "online": False}

        self.env = {"temperature": None, "co_ppm": None}
        self.env_level = "normal"          # normal / warning / alarm
        self.temp_alarm = False

        self.lot_full = False
        self.warning_active = False
        self.last_free = None
        self.started_at = time.time()

        self.actuators = {"barrier": "open", "sign": "FREE: %d" % config.CAPACITY, "fan": "off"}

    # --- start / main loop
    def start(self):
        db.init_db()
        for spot_id in config.SPOT_IDS:
            db.upsert_device(spot_id, "spot_sensor", now(), "unknown")

        self.mqtt.subscribe(config.TOPIC_SPOT_WILDCARD)
        self.mqtt.subscribe(config.TOPIC_ENV)
        self.mqtt.subscribe(config.TOPIC_GATE_EVENT)
        self.mqtt.subscribe(config.TOPIC_ACTUATOR_STATE)
        self.mqtt.connect()

        # wait for the connection before the first command goes out
        for _ in range(50):
            if self.mqtt.connected:
                break
            time.sleep(0.2)
        self.send_actuator_cmd()
        self.send_alert("INFO", "Data manager started, monitoring %d spots (warm-up %d s)"
                        % (config.CAPACITY, WARMUP_SEC))

        try:
            while True:
                time.sleep(config.MANAGER_CYCLE_SEC)
                with self.lock:
                    self.cycle()
        except KeyboardInterrupt:
            print("stopping...")
        finally:
            self.mqtt.disconnect()

    # --- incoming messages (paho network thread)
    def on_message(self, topic, text):
        data = parse(text)
        if data is None:
            print("ignoring non JSON message on %s: %s" % (topic, text))
            return
        try:
            with self.lock:
                if topic.startswith(config.BASE_TOPIC + "/spot/"):
                    self.handle_spot(topic, data)
                elif topic == config.TOPIC_ENV:
                    self.handle_env(data)
                elif topic == config.TOPIC_GATE_EVENT:
                    self.handle_gate(data)
                elif topic == config.TOPIC_ACTUATOR_STATE:
                    db.add_event(now(), "actuators", text)
                    print("actuators acknowledged: %s" % text)
        except Exception as err:
            # a bad message must not kill the paho network thread
            print("error handling message on %s: %s (%s)" % (topic, text, err))

    def handle_spot(self, topic, data):
        spot_id = data.get("spot") or topic.split("/")[-2]
        if spot_id not in self.spots:
            # a sensor we did not configure - add it on the fly
            self.spots[spot_id] = {"occupied": None, "last_seen": None, "online": False}
            self.send_alert("INFO", "New spot sensor discovered: %s" % spot_id)

        spot = self.spots[spot_id]
        occupied = bool(data.get("occupied"))
        ts = now()

        db.add_reading(ts, spot_id, "occupied", int(occupied))
        db.upsert_device(spot_id, "spot_sensor", ts, "occupied" if occupied else "free")

        if not spot["online"] and spot["last_seen"] is not None:
            self.send_alert("INFO", "Sensor %s is back online" % spot_id)
        if spot["occupied"] is not None and spot["occupied"] != occupied:
            self.send_alert("INFO", "Spot %s is now %s" % (spot_id, "OCCUPIED" if occupied else "FREE"))

        spot["occupied"] = occupied
        spot["last_seen"] = time.time()
        spot["online"] = True

        self.evaluate_occupancy()

    def handle_env(self, data):
        ts = now()
        temp = data.get("temperature")
        co = data.get("co_ppm")
        sensor = data.get("sensor", "ENV")
        # a missing or non numeric value is treated as "no reading"
        if not isinstance(temp, (int, float)):
            temp = None
        if not isinstance(co, (int, float)):
            co = None
        self.env["temperature"] = temp
        self.env["co_ppm"] = co
        if temp is not None:
            db.add_reading(ts, sensor, "temperature", temp)
        if co is not None:
            db.add_reading(ts, sensor, "co_ppm", co)
        db.upsert_device(sensor, "env_sensor", ts, "ok")
        self.evaluate_env()

    def handle_gate(self, data):
        event = data.get("event", "?")
        db.add_event(now(), "gate", event)
        if event == "enter":
            if self.lot_full:
                self.send_alert("ALARM", "A car entered while the lot is FULL - check the barrier!")
            else:
                self.send_alert("INFO", "Car entered through the main gate")
        elif event == "exit":
            self.send_alert("INFO", "Car left through the main gate")

    # periodic check
    def cycle(self):
        """Runs every MANAGER_CYCLE_SEC: sensor health check + summary."""
        deadline = time.time() - config.SENSOR_TIMEOUT_SEC
        for spot_id, spot in self.spots.items():
            if spot["online"] and spot["last_seen"] < deadline:
                spot["online"] = False
                db.upsert_device(spot_id, "spot_sensor", now(), "offline")
                self.send_alert("ALARM", "Sensor %s is not responding (no data for %d s)"
                                % (spot_id, config.SENSOR_TIMEOUT_SEC))

        if self.ready():
            self.evaluate_occupancy()
            self.publish_summary()

    # --- rules
    def counts(self):
        free = 0
        occupied = 0
        for spot in self.spots.values():
            if not spot["online"]:
                continue            # unknown state, counted as not free
            if spot["occupied"]:
                occupied += 1
            else:
                free += 1
        capacity = len(self.spots)
        percent = 100.0 * (capacity - free) / capacity if capacity else 0.0
        return free, occupied, capacity, percent

    def ready(self):
        """Rules start only after every sensor reported once (or after a warm-up
        period), otherwise the lot looks "full" while the sensors are still connecting."""
        reported = all(s["last_seen"] is not None for s in self.spots.values())
        return reported or time.time() - self.started_at > WARMUP_SEC

    def evaluate_occupancy(self):
        if not self.ready():
            return
        free, occupied, capacity, percent = self.counts()

        if free == 0 and occupied > 0 and not self.lot_full:
            self.lot_full = True
            self.warning_active = False
            self.actuators["barrier"] = "closed"
            self.actuators["sign"] = "FULL"
            self.send_alert("ALARM", "Parking lot is FULL (%d/%d) - barrier closed" % (occupied, capacity))
            self.send_actuator_cmd()

        elif free > 0 and self.lot_full:
            self.lot_full = False
            self.actuators["barrier"] = "open"
            self.actuators["sign"] = "FREE: %d" % free
            self.send_alert("INFO", "Free spots available again (%d) - barrier opened" % free)
            self.send_actuator_cmd()

        elif not self.lot_full:
            if percent >= config.WARNING_OCCUPANCY * 100 and not self.warning_active:
                self.warning_active = True
                self.send_alert("WARNING", "Lot almost full: %d/%d occupied (%.0f%%)"
                                % (occupied, capacity, percent))
            elif percent < config.WARNING_OCCUPANCY * 100 and self.warning_active:
                self.warning_active = False
                self.send_alert("INFO", "Occupancy back to normal (%.0f%%)" % percent)

            if free != self.last_free:
                self.actuators["sign"] = "FREE: %d" % free
                self.send_actuator_cmd()

        self.last_free = free

    def evaluate_env(self):
        co = self.env["co_ppm"]
        temp = self.env["temperature"]

        if co is not None:
            if co >= config.CO_ALARM_PPM:
                level = "alarm"
            elif co >= config.CO_WARNING_PPM:
                level = "warning"
            else:
                level = "normal"

            if level != self.env_level:
                if level == "alarm":
                    self.actuators["fan"] = "on"
                    self.send_alert("ALARM", "CO level critical: %d ppm - ventilation fan ON" % co)
                    self.send_actuator_cmd()
                elif level == "warning":
                    self.send_alert("WARNING", "CO level high: %d ppm" % co)
                else:
                    msg = "Air quality back to normal (%d ppm)" % co
                    if self.actuators["fan"] == "on":
                        self.actuators["fan"] = "off"
                        self.send_actuator_cmd()
                        msg += " - fan OFF"
                    self.send_alert("INFO", msg)
                self.env_level = level

        if temp is not None:
            if temp >= config.TEMP_ALARM_C and not self.temp_alarm:
                self.temp_alarm = True
                self.send_alert("ALARM", "High temperature: %d C - possible fire, check level -1" % temp)
            elif temp < config.TEMP_ALARM_C and self.temp_alarm:
                self.temp_alarm = False
                self.send_alert("INFO", "Temperature back to normal (%d C)" % temp)

    # outgoing
    def send_alert(self, level, message):
        ts = now()
        payload = {"level": level, "source": "manager", "message": message, "ts": ts}
        print("%s  %-8s %s" % (ts, level, message))
        db.add_alert(ts, level, message)
        # qos 1, alarms should not get lost
        self.mqtt.publish(config.TOPIC_ALERTS, payload, qos=1)

    def send_actuator_cmd(self):
        payload = dict(self.actuators)
        payload["ts"] = now()
        # retained so a panel that starts late still gets the last command
        self.mqtt.publish(config.TOPIC_ACTUATOR_CMD, payload, qos=1, retain=True)

    def publish_summary(self):
        free, occupied, capacity, percent = self.counts()
        ts = now()
        spots = {}
        for spot_id, spot in self.spots.items():
            if not spot["online"]:
                spots[spot_id] = "offline"
            else:
                spots[spot_id] = "occupied" if spot["occupied"] else "free"
        payload = {"ts": ts, "free": free, "occupied": occupied, "capacity": capacity,
                   "percent": round(percent, 1), "spots": spots,
                   "barrier": self.actuators["barrier"], "sign": self.actuators["sign"],
                   "fan": self.actuators["fan"],
                   "temperature": self.env["temperature"], "co_ppm": self.env["co_ppm"]}
        self.mqtt.publish(config.TOPIC_SUMMARY, payload)
        db.add_occupancy(ts, occupied, free, capacity, round(percent, 1))
        print("%s  summary  free=%d occupied=%d (%.0f%%) barrier=%s fan=%s"
              % (ts, free, occupied, percent, self.actuators["barrier"], self.actuators["fan"]))


if __name__ == "__main__":
    ParkingManager().start()
