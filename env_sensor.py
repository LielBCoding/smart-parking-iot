"""Emulator of the environment sensor of an underground parking lot.

Publishes temperature and carbon monoxide (CO) level. The two sliders work
like knobs, so during a demo the values can be pushed above the thresholds
to trigger a WARNING / ALARM and the ventilation fan.

Usage:  python env_sensor.py [interval_seconds]
"""
import random
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFormLayout, QLabel,
                             QSlider, QVBoxLayout, QWidget)

import config
from mqtt_client import now
from qt_mqtt import QtMqttClient
from theme import apply_theme

SENSOR_ID = "ENV1"


class EnvSensorWindow(QWidget):
    def __init__(self, interval):
        super().__init__()
        self.sent = 0

        self.mqtt = QtMqttClient("env-sensor")
        self.mqtt.connection_changed.connect(self.on_connection_changed)

        self.build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(interval * 1000)

        self.mqtt.connect()

    def build_ui(self):
        self.setWindowTitle("Environment Sensor " + SENSOR_ID)
        self.setFixedWidth(320)

        title = QLabel("Air Quality Sensor - Level -1")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 60)
        self.temp_slider.setValue(24)
        self.temp_value = QLabel()
        self.temp_slider.valueChanged.connect(self.refresh_values)

        self.co_slider = QSlider(Qt.Horizontal)
        self.co_slider.setRange(0, 300)
        self.co_slider.setValue(10)
        self.co_value = QLabel()
        self.co_slider.valueChanged.connect(self.refresh_values)

        self.drift_check = QCheckBox("Random drift on every tick")
        self.drift_check.setChecked(True)

        self.conn_label = QLabel("connecting...")
        self.conn_label.setStyleSheet("color: #95a5a6;")
        self.sent_label = QLabel("0")

        form = QFormLayout()
        form.addRow("Temperature:", self.temp_value)
        form.addRow("", self.temp_slider)
        form.addRow("CO level:", self.co_value)
        form.addRow("", self.co_slider)
        form.addRow("Broker:", self.conn_label)
        form.addRow("Messages sent:", self.sent_label)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(self.drift_check)

        self.refresh_values()

    def refresh_values(self):
        temp = self.temp_slider.value()
        co = self.co_slider.value()
        self.temp_value.setText("%d C" % temp)
        self.co_value.setText("%d ppm" % co)
        # colour the CO label according to the thresholds the manager uses
        if co >= config.CO_ALARM_PPM:
            self.co_value.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        elif co >= config.CO_WARNING_PPM:
            self.co_value.setStyleSheet("color: #f5b041; font-weight: bold;")
        else:
            self.co_value.setStyleSheet("color: #2ecc71;")
        if temp >= config.TEMP_ALARM_C:
            self.temp_value.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        else:
            self.temp_value.setStyleSheet("color: #2ecc71;")

    def tick(self):
        if self.drift_check.isChecked():
            self.temp_slider.setValue(self.temp_slider.value() + random.randint(-1, 1))
            self.co_slider.setValue(self.co_slider.value() + random.randint(-3, 3))
        self.publish()

    def publish(self):
        payload = {"sensor": SENSOR_ID,
                   "temperature": self.temp_slider.value(),
                   "co_ppm": self.co_slider.value(),
                   "ts": now()}
        if self.mqtt.publish(config.TOPIC_ENV, payload):
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
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else config.DEFAULT_PUBLISH_INTERVAL

    app = QApplication(sys.argv)
    apply_theme(app)
    window = EnvSensorWindow(interval)
    window.show()
    sys.exit(app.exec_())
