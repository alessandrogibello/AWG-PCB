@echo off
"C:\Program Files\KiCad\10.0\bin\python.exe" "%~dp0awg_testbench.py"
if %errorlevel% equ 0 (
    start "" "%~dp0awg_sim_results.png"
)
