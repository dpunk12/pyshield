#!/bin/sh
# examples/demo_app/build_demo.sh
#
# POSIX shell script to build the Acme Corp demo application using PyShield.
# Run this script from the repository root directory.
#
# Usage:
#   chmod +x examples/demo_app/build_demo.sh
#   ./examples/demo_app/build_demo.sh
#
# What this script does:
#   Step 1: Obfuscates the demo app source with PyArmor.
#   Step 2: Packages the obfuscated code into a single binary with PyInstaller.
#   Step 3: Prints the path to the finished binary and instructions for testing.
#
# Requirements:
#   - Python 3.11 or later in your PATH.
#   - PyArmor installed: pip install pyarmor
#   - PyInstaller installed: pip install pyinstaller
#   - PyShield installed from the repository root (pip install -r requirements.txt).
#
# The finished binary will be at: dist/demo/main (Linux/macOS) or
# dist/demo/main.exe (Windows).

# Stop immediately if any command fails.
set -e

# Print a blank line before each section for readability in screen readers.
echo ""
echo "PyShield demo build starting."
echo "Source directory: examples/demo_app"
echo "Output directory: dist/demo"
echo ""

# Run the PyShield build command.
# --source   : the directory containing the demo app source files.
# --entry    : the entry-point script within the source directory.
# --output   : where to place the finished binary.
# --name     : the base name of the output binary.
python pyshield.py build \
  --source examples/demo_app \
  --entry main.py \
  --output dist/demo \
  --name main

echo ""
echo "Build complete."
echo ""
echo "To run the demo without a license (no validation enforced):"
echo "  ./dist/demo/main process examples/demo_app/sample_input.csv /tmp/out.csv"
echo ""
echo "To generate a license and run with validation:"
echo "  python pyshield.py license generate --output demo.lic --machine-lock --days 365"
echo "  ./dist/demo/main process examples/demo_app/sample_input.csv /tmp/out.csv --license demo.lic"
echo ""
echo "To verify the output matches the expected result:"
echo "  diff /tmp/out.csv examples/demo_app/expected_output.csv"
echo ""
echo "To run all end-to-end tests (real PyArmor + PyInstaller required):"
echo "  pytest -m e2e -v"
echo ""
