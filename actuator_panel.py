"""Actuator panel emulator: barrier, LED sign and ventilation fan (relays).
It only applies the commands it gets and reports its state back."""
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QFormLayout, QLabel, QVBoxLayout,
                             QWidget)

import config
from mqtt_client import now, parse
from qt_mqtt import QtMqttClient
from theme import apply_theme

BIG = "font-size: 20px; font-weight: bold; padding: 8px; color: white; background-color: %s;"


class ActuatorPanelWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.state = {"barrier": "open", "sign": "FREE", "fan": "off"}
        self.received = 0

        self.mqtt = QtMqttClient("actuators")
        self.mqtt.connection_changed.connect(self.on_connection_changed)
        self.mqtt.message_received.connect(self.on_message)
        self.mqtt.subscribe(config.TOPIC_ACTUATOR_CMD)

        self.build_ui()
        self.mqtt.connect()

    def build_ui(self):
        self.setWindowTitle("Actuator Panel")
        self.setFixedWidth(340)

        title = QLabel("Barrier / Sign / Ventilation")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.barrier_label = QLabel()
        self.barrier_label.setAlignment(Qt.AlignCenter)
        self.sign_label = QLabel()
        self.sign_label.setAlignment(Qt.AlignCenter)
        self.fan_label = QLabel()
        self.fan_label.setAlignment(Qt.AlignCenter)

        self.conn_label = QLabel("connecting...")
        self.conn_label.setStyleSheet("color: #95a5a6;")
        self.received_label = QLabel("0")
        self.last_cmd_label = QLabel("-")
        self.last_cmd_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Entry barrier:", self.barrier_label)
        form.addRow("LED sign:", self.sign_label)
        form.addRow("Ventilation fan:", self.fan_label)
        form.addRow("Broker:", self.conn_label)
        form.addRow("Commands received:", self.received_label)
        form.addRow("Last command:", self.last_cmd_label)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)

        self.refresh()

    def refresh(self):
        if self.state["barrier"] == "open":
            self.barrier_label.setText("OPEN")
            self.barrier_label.setStyleSheet(BIG % "#27ae60")
        else:
            self.barrier_label.setText("CLOSED")
            self.barrier_label.setStyleSheet(BIG % "#c0392b")

        self.sign_label.setText(self.state["sign"])
        if self.state["sign"].startswith("FULL"):
            self.sign_label.setStyleSheet(BIG % "#c0392b")
        else:
            self.sign_label.setStyleSheet(BIG % "#2c3e50")

        if self.state["fan"] == "on":
            self.fan_label.setText("ON")
            self.fan_label.setStyleSheet(BIG % "#2980b9")
        else:
            self.fan_label.setText("OFF")
            self.fan_label.setStyleSheet(BIG % "#7f8c8d")

    def on_message(self, topic, text):
        data = parse(text)
        if not data:
            return
        changed = False
        for key in ("barrier", "sign", "fan"):
            if isinstance(data.get(key), str) and data[key] != self.state[key]:
                self.state[key] = data[key]
                changed = True
        self.received += 1
        self.received_label.setText(str(self.received))
        self.last_cmd_label.setText("%s  (barrier=%s, sign=%s, fan=%s)"
                                    % (data.get("ts", ""), self.state["barrier"],
                                       self.state["sign"], self.state["fan"]))
        self.refresh()
        if changed:
            # acknowledge the new physical state back to the system
            ack = dict(self.state)
            ack["ts"] = now()
            self.mqtt.publish(config.TOPIC_ACTUATOR_STATE, ack)

    def on_connection_changed(self, is_connected):
        if is_connected:
            self.conn_label.setText("connected")
            self.conn_label.setStyleSheet("color: #2ecc71;")
        else:
            self.conn_label.setText("disconnected")
            self.conn_label.setStyleSheet("color: #ff6b6b;")

    def closeEvent(self, event):
        self.mqtt.disconnect()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app)
    window = ActuatorPanelWindow()
    window.show()
    sys.exit(app.exec_())
