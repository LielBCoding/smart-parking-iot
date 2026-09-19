"""Gate panel emulator (enter / exit buttons)."""
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QFormLayout, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

import config
from mqtt_client import now, parse
from qt_mqtt import QtMqttClient
from theme import apply_theme


class GatePanelWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.entered = 0
        self.exited = 0

        self.mqtt = QtMqttClient("gate-panel")
        self.mqtt.connection_changed.connect(self.on_connection_changed)
        self.mqtt.message_received.connect(self.on_message)
        # show the sign text too
        self.mqtt.subscribe(config.TOPIC_ACTUATOR_CMD)

        self.build_ui()
        self.mqtt.connect()

    def build_ui(self):
        self.setWindowTitle("Gate Panel")
        self.setFixedWidth(340)

        title = QLabel("Entry / Exit Gate")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.sign_label = QLabel("---")
        self.sign_label.setAlignment(Qt.AlignCenter)
        self.sign_label.setStyleSheet("background-color: #2c3e50; color: #f1c40f; "
                                      "font-size: 22px; font-weight: bold; padding: 10px;")

        self.enter_btn = QPushButton("CAR ENTERED")
        self.enter_btn.setMinimumHeight(60)
        self.enter_btn.setStyleSheet("background-color: #27ae60; color: white; font-size: 15px; font-weight: bold;")
        self.enter_btn.clicked.connect(lambda: self.send_event("enter"))

        self.exit_btn = QPushButton("CAR EXITED")
        self.exit_btn.setMinimumHeight(60)
        self.exit_btn.setStyleSheet("background-color: #2980b9; color: white; font-size: 15px; font-weight: bold;")
        self.exit_btn.clicked.connect(lambda: self.send_event("exit"))

        buttons = QHBoxLayout()
        buttons.addWidget(self.enter_btn)
        buttons.addWidget(self.exit_btn)

        self.entered_label = QLabel("0")
        self.exited_label = QLabel("0")
        self.last_label = QLabel("-")
        self.conn_label = QLabel("connecting...")
        self.conn_label.setStyleSheet("color: #95a5a6;")

        form = QFormLayout()
        form.addRow("Cars entered:", self.entered_label)
        form.addRow("Cars exited:", self.exited_label)
        form.addRow("Last event:", self.last_label)
        form.addRow("Broker:", self.conn_label)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.sign_label)
        layout.addLayout(buttons)
        layout.addLayout(form)

    def send_event(self, event):
        payload = {"event": event, "gate": "main", "ts": now()}
        if self.mqtt.publish(config.TOPIC_GATE_EVENT, payload, qos=1):
            if event == "enter":
                self.entered += 1
                self.entered_label.setText(str(self.entered))
            else:
                self.exited += 1
                self.exited_label.setText(str(self.exited))
            self.last_label.setText("%s at %s" % (event, payload["ts"]))

    def on_message(self, topic, text):
        data = parse(text)
        if data and isinstance(data.get("sign"), str):
            self.sign_label.setText(data["sign"])
            if data["sign"].startswith("FULL"):
                self.sign_label.setStyleSheet("background-color: #2c3e50; color: #e74c3c; "
                                              "font-size: 22px; font-weight: bold; padding: 10px;")
            else:
                self.sign_label.setStyleSheet("background-color: #2c3e50; color: #2ecc71; "
                                              "font-size: 22px; font-weight: bold; padding: 10px;")

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
    window = GatePanelWindow()
    window.show()
    sys.exit(app.exec_())
