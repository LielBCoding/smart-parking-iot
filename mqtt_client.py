"""Small wrapper around paho-mqtt shared by all the components.

It hides the connection details (client id, reconnect, callbacks) so the
emulators and the manager only deal with topics and JSON payloads.
"""
import json
import random
import time

import paho.mqtt.client as mqtt

import config


def now():
    """Timestamp string used in every message and DB row."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def parse(text):
    """Decode a JSON payload, return None if it is not valid JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return None


class MqttClient:
    def __init__(self, name, on_message=None, on_connection_change=None, will=None):
        self.name = name
        self.client_id = "%s-%04d" % (name, random.randint(0, 9999))
        self.connected = False
        self._on_message = on_message
        self._on_connection_change = on_connection_change
        self._subscriptions = []

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=self.client_id,
                                  clean_session=True)
        if config.USERNAME:
            self.client.username_pw_set(config.USERNAME, config.PASSWORD)

        # Last Will: the broker publishes this for us if we drop off the network
        if will is not None:
            topic, payload = will
            self.client.will_set(topic, json.dumps(payload), qos=1)

        self.client.on_connect = self._handle_connect
        self.client.on_disconnect = self._handle_disconnect
        self.client.on_message = self._handle_message

    # ------------------------------------------------------------ public API
    def connect(self):
        print("[%s] connecting to %s:%s as %s" % (self.name, config.BROKER_HOST,
                                                 config.BROKER_PORT, self.client_id))
        # connect_async + loop_start keeps the GUI responsive and reconnects by itself
        self.client.connect_async(config.BROKER_HOST, config.BROKER_PORT, keepalive=60)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def subscribe(self, topic):
        if topic not in self._subscriptions:
            self._subscriptions.append(topic)
        if self.connected:
            self.client.subscribe(topic)

    def publish(self, topic, payload, qos=0, retain=False):
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        if not self.connected:
            print("[%s] not connected, message to %s dropped" % (self.name, topic))
            return False
        self.client.publish(topic, payload, qos=qos, retain=retain)
        return True

    # ------------------------------------------------------------ paho callbacks
    def _handle_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print("[%s] connection failed: %s" % (self.name, reason_code))
            self.connected = False
        else:
            print("[%s] connected" % self.name)
            self.connected = True
            # (re)subscribe after every connect, also after an automatic reconnect
            for topic in self._subscriptions:
                client.subscribe(topic)
        if self._on_connection_change:
            self._on_connection_change(self.connected)

    def _handle_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        print("[%s] disconnected (%s)" % (self.name, reason_code))
        if self._on_connection_change:
            self._on_connection_change(False)

    def _handle_message(self, client, userdata, msg):
        text = msg.payload.decode("utf-8", "ignore")
        if self._on_message:
            self._on_message(msg.topic, text)
