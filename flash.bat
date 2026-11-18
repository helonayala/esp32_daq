@echo off
rem Builds and flashes the firmware (arduino-cli + esp32:esp32 core 3.x). Usage:  flash.bat COM5
rem Alternative: open firmware\esp32_daq\esp32_daq.ino in the Arduino IDE (board "ESP32 Dev Module") and click Upload.
if "%1"=="" (echo give the port, e.g.: flash.bat COM5 & exit /b 1)
set FQBN=esp32:esp32:esp32
set SK=%~dp0firmware\esp32_daq
arduino-cli compile --fqbn %FQBN% "%SK%" || exit /b 1
arduino-cli upload --fqbn %FQBN% -p %1 "%SK%"
