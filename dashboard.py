"""SmartPark control center - the main GUI of the operator.

Shows the live state of every parking spot, the lot summary, the actuators,
an occupancy history graph (loaded from the DB and updated live) and the
INFO / WARNING / ALARM messages window.

Run:  python dashboard.py
"""
import sys
import time

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QMainWindow, QProgressBar, QPushButton,
                             QTextEdit, QVBoxLayout, QWidget)

import config
import db
from mqtt_client import parse
from qt_mqtt import QtMqttClient

TILE_STYLE = ("border-radius: 6px; color: white; font-size: 15px; font-weight: bold; "
              "background-color: %s;")
COLOR_FREE = "#2ecc71"
COLOR_OCCUPIED = "#e74c3c"
COLOR_OFFLINE = "#7f8c8d"
COLOR_UNKNOWN = "#bdc3c7"

LEVEL_COLORS = {"INFO": "#2980b9", "WARNING": "#e67e22", "ALARM": "#c0392b"}


def to_epoch(ts):
    return time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tiles = {}
        self.counters = {"INFO": 0, "WARNING": 0, "ALARM": 0}
        self.history_x = []
        self.history_y = []

        self.mqtt = QtMqttClient("dashboard")
        self.mqtt.message_received.connect(self.on_message)
        self.mqtt.connection_changed.connect(self.on_connection_changed)
        for topic in (config.TOPIC_SPOT_WILDCARD, config.TOPIC_SUMMARY, config.TOPIC_ALERTS,
                      config.TOPIC_ACTUATOR_STATE, config.TOPIC_ACTUATOR_CMD,
                      config.TOPIC_ENV, config.TOPIC_GATE_EVENT):
            self.mqtt.subscribe(topic)

        self.build_ui()
        self.load_history()
        self.mqtt.connect()

    # ============================================================ UI
    def build_ui(self):
        self.setWindowTitle("SmartPark - Control Center (%s)" % config.LOT_ID)
        self.resize(1150, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---- header
        header = QHBoxLayout()
        title = QLabel("SmartPark Control Center - Parking %s" % config.LOT_ID.replace("lot", "Lot "))
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.conn_label = QLabel("connecting to %s ..." % config.BROKER_HOST)
        self.conn_label.setStyleSheet("color: gray;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.conn_label)
        root.addLayout(header)

        # ---- middle row: spots | status | graph
        middle = QHBoxLayout()
        middle.addWidget(self.build_spots_box(), 3)
        middle.addWidget(self.build_status_box(), 2)
        middle.addWidget(self.build_graph_box(), 4)
        root.addLayout(middle, 3)

        # ---- bottom: alerts
        root.addWidget(self.build_alerts_box(), 2)

    def build_spots_box(self):
        box = QGroupBox("Parking spots (live from sensors)")
        grid = QGridLayout(box)
        columns = 3
        for i, spot_id in enumerate(config.SPOT_IDS):
            tile = QLabel("%s\n?" % spot_id)
            tile.setAlignment(Qt.AlignCenter)
            tile.setMinimumSize(100, 80)
            tile.setStyleSheet(TILE_STYLE % COLOR_UNKNOWN)
            grid.addWidget(tile, i // columns, i % columns)
            self.tiles[spot_id] = tile
        legend = QLabel("green = free    red = occupied    gray = sensor offline")
        legend.setStyleSheet("color: gray; font-size: 11px;")
        grid.addWidget(legend, (len(config.SPOT_IDS) + columns - 1) // columns, 0, 1, columns)
        return box

    def build_status_box(self):
        box = QGroupBox("Lot status (from data manager)")
        layout = QGridLayout(box)

        self.free_label = QLabel("-")
        self.free_label.setAlignment(Qt.AlignCenter)
        self.free_label.setStyleSheet("font-size: 44px; font-weight: bold; color: #27ae60;")
        free_caption = QLabel("free spots")
        free_caption.setAlignment(Qt.AlignCenter)

        self.occupancy_bar = QProgressBar()
        self.occupancy_bar.setRange(0, 100)
        self.occupancy_bar.setFormat("occupancy %p%")

        self.barrier_label = QLabel("-")
        self.sign_label = QLabel("-")
        self.fan_label = QLabel("-")
        self.temp_label = QLabel("-")
        self.co_label = QLabel("-")
        self.gate_label = QLabel("in: 0   out: 0")
        self.gate_in = 0
        self.gate_out = 0

        layout.addWidget(self.free_label, 0, 0, 1, 2)
        layout.addWidget(free_caption, 1, 0, 1, 2)
        layout.addWidget(self.occupancy_bar, 2, 0, 1, 2)
        rows = [("Barrier:", self.barrier_label), ("LED sign:", self.sign_label),
                ("Ventilation fan:", self.fan_label), ("Temperature:", self.temp_label),
                ("CO level:", self.co_label), ("Gate events:", self.gate_label)]
        for r, (caption, widget) in enumerate(rows, start=3):
            layout.addWidget(QLabel(caption), r, 0)
            widget.setStyleSheet("font-weight: bold;")
            layout.addWidget(widget, r, 1)
        return box

    def build_graph_box(self):
        box = QGroupBox("Occupancy history (from DB + live)")
        layout = QVBoxLayout(box)
        self.plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setYRange(0, 100)
        self.plot.setLabel("left", "occupied %")
        self.plot.addLine(y=config.WARNING_OCCUPANCY * 100,
                          pen=pg.mkPen("#e67e22", style=Qt.DashLine))
        self.curve = self.plot.plot([], [], pen=pg.mkPen("#2980b9", width=2),
                                    symbol="o", symbolSize=4, symbolBrush="#2980b9")
        layout.addWidget(self.plot)
        return box

    def build_alerts_box(self):
        box = QGroupBox("Messages: Info / Warning / Alarm")
        layout = QVBoxLayout(box)

        top = QHBoxLayout()
        self.counter_labels = {}
        for level in ("INFO", "WARNING", "ALARM"):
            label = QLabel("%s: 0" % level)
            label.setStyleSheet("font-weight: bold; color: %s;" % LEVEL_COLORS[level])
            self.counter_labels[level] = label
            top.addWidget(label)
        top.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_alerts)
        top.addWidget(clear_btn)
        layout.addLayout(top)

        self.alerts_view = QTextEdit()
        self.alerts_view.setReadOnly(True)
        self.alerts_view.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(self.alerts_view)
        return box

    # ============================================================ data
    def load_history(self):
        db.init_db()
        for ts, percent in db.occupancy_history():
            self.history_x.append(to_epoch(ts))
            self.history_y.append(percent)
        self.curve.setData(self.history_x, self.history_y)
        for ts, level, message in db.recent_alerts(15):
            self.append_alert(level, message, ts, from_history=True)

    def on_message(self, topic, text):
        data = parse(text)
        if data is None:
            return
        if topic.startswith(config.BASE_TOPIC + "/spot/"):
            spot_id = data.get("spot") or topic.split("/")[-2]
            self.set_tile(spot_id, "occupied" if data.get("occupied") else "free")
        elif topic == config.TOPIC_SUMMARY:
            self.apply_summary(data)
        elif topic == config.TOPIC_ALERTS:
            self.counters[data.get("level", "INFO")] = self.counters.get(data.get("level", "INFO"), 0) + 1
            self.append_alert(data.get("level", "INFO"), data.get("message", text), data.get("ts", ""))
        elif topic in (config.TOPIC_ACTUATOR_STATE, config.TOPIC_ACTUATOR_CMD):
            self.apply_actuators(data)
        elif topic == config.TOPIC_ENV:
            self.apply_env(data.get("temperature"), data.get("co_ppm"))
        elif topic == config.TOPIC_GATE_EVENT:
            if data.get("event") == "enter":
                self.gate_in += 1
            elif data.get("event") == "exit":
                self.gate_out += 1
            self.gate_label.setText("in: %d   out: %d" % (self.gate_in, self.gate_out))

    def set_tile(self, spot_id, state):
        tile = self.tiles.get(spot_id)
        if tile is None:
            return
        color = {"free": COLOR_FREE, "occupied": COLOR_OCCUPIED, "offline": COLOR_OFFLINE}.get(state, COLOR_UNKNOWN)
        tile.setText("%s\n%s" % (spot_id, state.upper()))
        tile.setStyleSheet(TILE_STYLE % color)

    def apply_summary(self, data):
        free = data.get("free", 0)
        self.free_label.setText(str(free))
        self.free_label.setStyleSheet("font-size: 44px; font-weight: bold; color: %s;"
                                      % ("#c0392b" if free == 0 else "#27ae60"))
        self.occupancy_bar.setValue(int(data.get("percent", 0)))
        for spot_id, state in data.get("spots", {}).items():
            self.set_tile(spot_id, state)
        self.apply_actuators(data)
        self.apply_env(data.get("temperature"), data.get("co_ppm"))
        if "ts" in data:
            self.history_x.append(to_epoch(data["ts"]))
            self.history_y.append(data.get("percent", 0))
            self.history_x = self.history_x[-300:]
            self.history_y = self.history_y[-300:]
            self.curve.setData(self.history_x, self.history_y)

    def apply_actuators(self, data):
        if "barrier" in data:
            self.barrier_label.setText(data["barrier"].upper())
            self.barrier_label.setStyleSheet("font-weight: bold; color: %s;"
                                             % ("#27ae60" if data["barrier"] == "open" else "#c0392b"))
        if "sign" in data:
            self.sign_label.setText(data["sign"])
        if "fan" in data:
            self.fan_label.setText(data["fan"].upper())
            self.fan_label.setStyleSheet("font-weight: bold; color: %s;"
                                         % ("#2980b9" if data["fan"] == "on" else "gray"))

    def apply_env(self, temp, co):
        if temp is not None:
            self.temp_label.setText("%s C" % temp)
            self.temp_label.setStyleSheet("font-weight: bold; color: %s;"
                                          % ("#c0392b" if temp >= config.TEMP_ALARM_C else "black"))
        if co is not None:
            if co >= config.CO_ALARM_PPM:
                color = "#c0392b"
            elif co >= config.CO_WARNING_PPM:
                color = "#e67e22"
            else:
                color = "black"
            self.co_label.setText("%s ppm" % co)
            self.co_label.setStyleSheet("font-weight: bold; color: %s;" % color)

    def append_alert(self, level, message, ts, from_history=False):
        color = LEVEL_COLORS.get(level, "black")
        weight = "bold" if level == "ALARM" else "normal"
        prefix = "(history) " if from_history else ""
        self.alerts_view.append('<span style="color:%s; font-weight:%s;">%s %s%-8s %s</span>'
                                % (color, weight, ts, prefix, level, message))
        if not from_history:
            self.counter_labels[level].setText("%s: %d" % (level, self.counters[level]))

    def clear_alerts(self):
        self.alerts_view.clear()

    def on_connection_changed(self, is_connected):
        if is_connected:
            self.conn_label.setText("connected to %s" % config.BROKER_HOST)
            self.conn_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.conn_label.setText("disconnected")
            self.conn_label.setStyleSheet("color: red; font-weight: bold;")

    def closeEvent(self, event):
        self.mqtt.disconnect()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec_())
