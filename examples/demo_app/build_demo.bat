@echo off
REM examples/demo_app/build_demo.bat
REM
REM Windows batch script to build the Acme Corp demo application using PyShield.
REM Run this script from the repository root directory.
REM
REM Usage:
REM   examples\demo_app\build_demo.bat
REM
REM What this script does:
REM   Step 1: Obfuscates the demo app source with PyArmor.
REM   Step 2: Packages the obfuscated code into a single EXE with PyInstaller.
REM   Step 3: Prints the path to the finished binary and instructions for testing.
REM
REM Requirements:
REM   - Python 3.11 or later in your PATH.
REM   - PyArmor installed: pip install pyarmor
REM   - PyInstaller installed: pip install pyinstaller
REM   - PyShield installed from the repository root: pip install -r requirements.txt
REM
REM The finished binary will be at: dist\demo\main.exe

echo.
echo PyShield demo build starting.
echo Source directory: examples\demo_app
echo Output directory: dist\demo
echo.

REM Run the PyShield build command.
REM --source   : the directory containing the demo app source files.
REM --entry    : the entry-point script within the source directory.
REM --output   : where to place the finished binary.
REM --name     : the base name of the output binary (will get .exe extension).
python pyshield.py build ^
  --source examples\demo_app ^
  --entry main.py ^
  --output dist\demo ^
  --name main

REM Check if the build succeeded (ERRORLEVEL 0 means success).
if %ERRORLEVEL% neq 0 (
    echo.
    echo Build failed. Check the output above for error details.
    exit /b 1
)

echo.
echo Build complete.
echo.
echo To run the demo without a license:
echo   dist\demo\main.exe process examples\demo_app\sample_input.csv C:\Temp\out.csv
echo.
echo To generate a license and run with validation:
echo   python pyshield.py license generate --output demo.lic --machine-lock --days 365
echo   dist\demo\main.exe process examples\demo_app\sample_input.csv C:\Temp\out.csv --license demo.lic
echo.
echo To run all end-to-end tests (real PyArmor + PyInstaller required):
echo   pytest -m e2e -v
echo.
