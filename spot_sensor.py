"""Emulator of a parking spot occupancy sensor (data producer).

Each running instance represents one physical sensor (ultrasonic / magnetic)
installed in a parking spot. It publishes its state every few seconds even if
nothing changed - this "heartbeat" lets the manager detect a dead sensor.

Usage:  python spot_sensor.py A1 [interval_seconds]
"""
import random
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFormLayout, QLabel,
                             QPushButton, QSpinBox, QVBoxLayout, QWidget)

import config
from mqtt_client import now
from qt_mqtt import QtMqttClient
from theme import apply_theme

CHANGE_PROBABILITY = 0.3   # chance that a car arrives / leaves on every tick

STYLE_FREE = "background-color: #2ecc71; color: white; font-size: 26px; font-weight: bold; padding: 18px;"
STYLE_OCCUPIED = "background-color: #e74c3c; color: white; font-size: 26px; font-weight: bold; padding: 18px;"


class SpotSensorWindow(QWidget):
    def __init__(self, spot_id, interval):
        super().__init__()
        self.spot_id = spot_id
        self.topic = config.TOPIC_SPOT_STATUS.format(spot_id=spot_id)
        self.occupied = random.random() < 0.5
        self.sent = 0

        self.mqtt = QtMqttClient("spot-" + spot_id)
        self.mqtt.connection_changed.connect(self.on_connection_changed)

        self.build_ui(interval)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(interval * 1000)

        self.mqtt.connect()

    def build_ui(self, interval):
        self.setWindowTitle("Spot Sensor " + self.spot_id)
        self.setFixedWidth(280)

        title = QLabel("Parking Spot " + self.spot_id)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)

        self.auto_check = QCheckBox("Simulate cars automatically")
        self.auto_check.setChecked(True)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(interval)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.valueChanged.connect(lambda v: self.timer.setInterval(v * 1000))

        self.toggle_btn = QPushButton("Toggle car (manual)")
        self.toggle_btn.clicked.connect(self.toggle)

        self.conn_label = QLabel("connecting...")
        self.conn_label.setStyleSheet("color: #95a5a6;")
        self.sent_label = QLabel("0")
        self.topic_label = QLabel(self.topic)
        self.topic_label.setStyleSheet("color: #95a5a6; font-size: 10px;")

        form = QFormLayout()
        form.addRow("Broker:", self.conn_label)
        form.addRow("Publish every:", self.interval_spin)
        form.addRow("Messages sent:", self.sent_label)
        form.addRow("Topic:", self.topic_label)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.auto_check)
        layout.addWidget(self.toggle_btn)
        layout.addLayout(form)

        self.refresh_status()

    # ------------------------------------------------------------ logic
    def refresh_status(self):
        if self.occupied:
            self.status_label.setText("OCCUPIED")
            self.status_label.setStyleSheet(STYLE_OCCUPIED)
        else:
            self.status_label.setText("FREE")
            self.status_label.setStyleSheet(STYLE_FREE)

    def tick(self):
        if self.auto_check.isChecked() and random.random() < CHANGE_PROBABILITY:
            self.occupied = not self.occupied
            self.refresh_status()
        self.publish()

    def toggle(self):
        self.occupied = not self.occupied
        self.refresh_status()
        self.publish()

    def publish(self):
        payload = {"spot": self.spot_id, "occupied": self.occupied, "ts": now()}
        if self.mqtt.publish(self.topic, payload):
            self.sent += 1
            self.sent_label.setText(str(self.sent))

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
    spot_id = sys.argv[1] if len(sys.argv) > 1 else "A1"
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else config.DEFAULT_PUBLISH_INTERVAL

    app = QApplication(sys.argv)
    apply_theme(app)
    window = SpotSensorWindow(spot_id, interval)
    window.show()
    sys.exit(app.exec_())
