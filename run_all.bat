@echo off
REM Starts the complete SmartPark demo on one machine.
REM The MQTT broker is remote (see config.py), nothing to install locally.

cd /d %~dp0

start "SmartPark - Data Manager" cmd /k python data_manager.py
timeout /t 3 >nul

start "Actuators" python actuator_panel.py
start "Gate" python gate_panel.py
start "Env sensor" python env_sensor.py

for %%s in (A1 A2 A3 A4 A5 A6) do (
    start "Spot %%s" python spot_sensor.py %%s
)

timeout /t 2 >nul
start "Dashboard" python dashboard.py
