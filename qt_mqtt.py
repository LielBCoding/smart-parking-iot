"""MQTT client that emits Qt signals (paho callbacks run in another thread)."""
from PyQt5.QtCore import QObject, pyqtSignal

from mqtt_client import MqttClient


class QtMqttClient(QObject):
    message_received = pyqtSignal(str, str)   # topic, payload text
    connection_changed = pyqtSignal(bool)

    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.mqtt = MqttClient(name,
                               on_message=self._forward_message,
                               on_connection_change=self._forward_connection)

    def _forward_message(self, topic, text):
        self.message_received.emit(topic, text)

    def _forward_connection(self, is_connected):
        self.connection_changed.emit(is_connected)

    def connect(self):
        self.mqtt.connect()

    def disconnect(self):
        self.mqtt.disconnect()

    def subscribe(self, topic):
        self.mqtt.subscribe(topic)

    def publish(self, topic, payload, qos=0, retain=False):
        return self.mqtt.publish(topic, payload, qos=qos, retain=retain)

    @property
    def connected(self):
        return self.mqtt.connected
