# SmartPark - IoT Smart Parking Lot Management

Final project for the course **Software Development for IoT in Smart City environment** (65348),
Holon Institute of Technology.

Author: **Liel Babayn**

## The problem and the idea

Drivers in the city waste time and fuel circling around looking for a parking spot, and the
municipality has no real-time picture of how full its parking lots are. SmartPark puts a cheap
occupancy sensor in every parking spot, an air quality sensor in the underground level and a few
actuators at the gate. All of them talk to each other only through an **MQTT broker**. A data
manager collects everything into a database, decides when to raise Info / Warning / Alarm
messages and controls the barrier, the LED sign and the ventilation fan. An operator follows
the lot from a live dashboard.

## System architecture

```
   +-----------------------+                                   +---------------------+
   | spot_sensor.py  (x6)  | --- spot/<id>/status -----+       |  data_manager.py    |
   | occupancy sensors     |                           |       |  - stores to SQLite |
   +-----------------------+                           |       |  - alert rules      |
   +-----------------------+                           v       |  - actuator control |
   | env_sensor.py         | --- env ------------> +--------+  +----------+----------+
   | temperature / CO      |                       |  MQTT  |<----------->|  alerts, summary,
   +-----------------------+                       | broker |             |  actuators/cmd
   +-----------------------+                       +--------+  +----------v----------+
   | gate_panel.py         | --- gate/event ---------^  |  ^    |  dashboard.py       |
   | enter / exit buttons  |                            |  |    |  operator GUI       |
   +-----------------------+                            |  |    +---------------------+
   +-----------------------+                            |  |
   | actuator_panel.py     | <-- actuators/cmd ---------+  |         +-----------------+
   | barrier / sign / fan  | --- actuators/state ---------+         | data/smartpark.db|
   +-----------------------+                                        +-----------------+
```

No component knows the address of another component. Everything is publish / subscribe through
the broker (`broker.hivemq.com`, public, port 1883), which is the classic IoT pattern taught in
the course.

## Components

| File | Kind | What it does |
|------|------|--------------|
| `spot_sensor.py` | emulator - data producer | One parking spot sensor. Publishes `occupied: true/false` every few seconds (heartbeat). Cars arrive / leave randomly or by a manual button. Run one instance per spot. |
| `env_sensor.py` | emulator - data producer with knobs | Temperature and CO level of the underground level. Two sliders act like knobs to push the values over the thresholds. |
| `gate_panel.py` | emulator - button | "Car entered" / "Car exited" buttons at the gate. Also shows the LED sign text. |
| `actuator_panel.py` | emulator - relay | Entry barrier, LED sign and ventilation fan. Only reacts to commands and acknowledges its state. |
| `data_manager.py` | data manager (no GUI) | Subscribes to all devices, writes everything to SQLite, keeps the state of the lot, publishes Info / Warning / Alarm messages, drives the actuators and publishes a summary every 5 s. |
| `dashboard.py` | main GUI | Live spot map, free spots counter, occupancy bar, actuator state, air quality, occupancy history graph (from the DB + live) and the messages window. |
| `db.py` | local DB | SQLite schema and helpers. `python db.py` prints a report of the stored data. |
| `mqtt_client.py` / `qt_mqtt.py` | infrastructure | Thin wrapper around paho-mqtt, and a Qt version that turns the network callbacks into Qt signals. |
| `theme.py` | infrastructure | Shared dark Qt stylesheet applied to every window. |
| `config.py` | configuration | Broker, topics, thresholds, DB path - one place for everything. |

## MQTT topics

All topics live under `smartpark/lot1/`.

| Topic | Publisher -> Subscriber | Payload example |
|-------|-------------------------|-----------------|
| `spot/<id>/status` | spot sensor -> manager, dashboard | `{"spot": "A3", "occupied": true, "ts": "..."}` |
| `env` | env sensor -> manager, dashboard | `{"sensor": "ENV1", "temperature": 24, "co_ppm": 12, "ts": "..."}` |
| `gate/event` | gate panel -> manager, dashboard | `{"event": "enter", "gate": "main", "ts": "..."}` |
| `actuators/cmd` | manager -> actuator panel, gate panel, dashboard | `{"barrier": "closed", "sign": "FULL", "fan": "on", "ts": "..."}` |
| `actuators/state` | actuator panel -> manager, dashboard | same fields as the command (acknowledgement) |
| `alerts` | manager -> dashboard | `{"level": "ALARM", "source": "manager", "message": "Parking lot is FULL (6/6) - barrier closed", "ts": "..."}` |
| `summary` | manager -> dashboard | `{"free": 2, "occupied": 4, "percent": 66.7, "spots": {"A1": "occupied", ...}, "barrier": "open", ...}` |

The manager and the dashboard subscribe with the wildcard `spot/+/status`. The manager picks up a
new sensor automatically (it is added to the lot on its first message); to give it a tile on the
dashboard add its id to `SPOT_IDS` in `config.py`.

## Alert rules (data manager)

| Condition | Level | Action |
|-----------|-------|--------|
| A spot changes state, a car passes the gate, sensor back online | INFO | message only |
| 80% or more of the spots are occupied | WARNING | message |
| No free spot left (every online sensor reports occupied) | ALARM | barrier closed, LED sign shows FULL |
| Free spot appears after the lot was full | INFO | barrier opened, sign shows FREE: n |
| A car enters while the lot is full | ALARM | message (barrier failure) |
| A sensor sent nothing for 20 s | ALARM | spot marked offline (gray) on the dashboard |
| CO >= 50 ppm | WARNING | message |
| CO >= 100 ppm | ALARM | ventilation fan ON |
| CO back to normal | INFO | fan OFF (if it was on) |
| Temperature >= 45 C | ALARM | message (possible fire) |

Messages are sent only when a state changes, so the log is not flooded. A spot whose sensor is
offline is counted as "not free" (safe side): the FREE sign never promises a spot the system
cannot see. The rules start only after a 20 s warm-up (or once every sensor reported), so the lot
does not look full while the emulators are still connecting.

## MQTT features used

* publish / subscribe with hierarchical topics and the `+` wildcard
* JSON payloads with a timestamp in every message the components publish (the Last Will is prepared at connect time, so it carries no timestamp)
* **QoS 1** for alerts, gate events and actuator commands (must not get lost), QoS 0 for the periodic sensor data
* **retained message** on `actuators/cmd` - a panel that starts late immediately receives the current state
* **Last Will and Testament** - if the data manager drops off the network without a DISCONNECT packet (crash, power, Wi-Fi), the broker itself publishes an ALARM to the dashboard. Ctrl+C in the manager console is a clean disconnect, so the will is not sent - which is the correct MQTT behaviour
* keep-alive and automatic reconnect handled by paho-mqtt

## How to run

Requirements: Python 3.10+ and an internet connection (the broker is public).

```
pip install -r requirements.txt
run_all.bat
```

`run_all.bat` (Windows) opens the data manager, the actuator panel, the gate panel, the environment
sensor, six spot sensors and the dashboard. On other systems, or to run components by hand:

```
python data_manager.py
python spot_sensor.py A1        (repeat for A2 ... A6, optional second argument = interval in seconds)
python env_sensor.py            (optional argument = interval in seconds)
python gate_panel.py
python actuator_panel.py
python dashboard.py
python db.py                    (report of what is stored in the database)
```

## Demo scenario

1. Start everything. The spots turn green / red on the dashboard, the graph starts to fill.
2. Toggle cars manually until 5 of 6 spots are occupied - a WARNING appears.
3. Occupy the last spot - ALARM, the barrier closes and the sign shows FULL.
4. Press "CAR ENTERED" on the gate panel while the lot is full - ALARM (barrier failure).
5. Push the CO slider above 100 ppm - ALARM and the ventilation fan turns ON.
6. Free a spot and lower the CO - INFO messages, barrier opens, fan OFF.
7. Close one spot sensor window - after 20 s an ALARM "sensor not responding" and the spot turns gray.
8. Close the data manager console window (not Ctrl+C, that is a clean disconnect) - the broker
   publishes the Last Will ALARM on the dashboard.

## Database

`data/smartpark.db` (SQLite, created automatically):

* `devices` - every device seen, its type, last seen time and status
* `readings` - every sensor value (spot occupancy, temperature, CO)
* `events` - gate events and actuator acknowledgements
* `alerts` - every Info / Warning / Alarm message
* `occupancy` - one row per manager cycle, used for the history graph

## Project structure

```
smart-parking-iot/
  config.py            configuration
  mqtt_client.py       paho-mqtt wrapper
  qt_mqtt.py           Qt signals bridge
  theme.py             shared Qt stylesheet (dark theme)
  db.py                SQLite layer
  spot_sensor.py       emulator - occupancy sensor
  env_sensor.py        emulator - temperature / CO sensor
  gate_panel.py        emulator - entry / exit buttons
  actuator_panel.py    emulator - barrier / sign / fan relays
  data_manager.py      data manager
  dashboard.py         main GUI
  run_all.bat          starts the whole demo
  requirements.txt
  docs/screenshots/    screenshots used in the presentation
```
