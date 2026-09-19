@echo off
REM Starts the complete SmartPark demo on one machine (Windows).
REM The MQTT broker is remote (see config.py), nothing to install locally.
REM The data manager keeps its console (that is the log), the GUI windows
REM are started with pythonw so they do not open extra consoles.

cd /d %~dp0

start "SmartPark - Data Manager" cmd /k python data_manager.py
timeout /t 3 >nul

start "" pythonw actuator_panel.py
start "" pythonw gate_panel.py
start "" pythonw env_sensor.py

for %%s in (A1 A2 A3 A4 A5 A6) do (
    start "" pythonw spot_sensor.py %%s
)

timeout /t 2 >nul
start "" pythonw dashboard.py
