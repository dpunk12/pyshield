# Demo Application: Acme Corp Customer Churn Processor

## What this is

This folder contains a realistic mock "data processor" application that serves two purposes.

First, it demonstrates what a real piece of proprietary software looks like before protection. The file secret_algorithm.py contains a weighted scoring model with specific numeric constants. Those constants represent business intelligence that the owner does not want competitors to read. The file license_check.py enforces that only licensed users can run the application.

Second, this demo app is the subject of PyShield's end-to-end tests. The tests build this application, protect it, run it, and verify that the protection works. The tests are the evidence you show to your VP or client instead of asking them to take your word for it.

## How to build the protected binary

From the repository root directory, run one of the following.

On Linux or macOS:

    chmod +x examples/demo_app/build_demo.sh
    ./examples/demo_app/build_demo.sh

On Windows:

    examples\demo_app\build_demo.bat

Both scripts call the PyShield command-line tool, which obfuscates the source with PyArmor and packages it with PyInstaller. The finished binary appears at dist/demo/main on Linux and macOS, or dist/demo/main.exe on Windows.

## What the build script requires

Python 3.11 or later must be in your PATH. The following packages must be installed:

    pip install -r requirements.txt
    pip install -r requirements-dev.txt

## How to run the demo manually

After building, run:

    ./dist/demo/main process examples/demo_app/sample_input.csv /tmp/out.csv

The program reads the 20-row sample customer file, scores each customer for churn risk, and writes the results to /tmp/out.csv. To confirm the output is correct:

    diff /tmp/out.csv examples/demo_app/expected_output.csv

No output from diff means the files are identical. That confirms the protection has not broken the application logic.

## How to run with license validation

Generate a license file locked to your machine with a one-year expiry:

    python pyshield.py license generate --output demo.lic --machine-lock --days 365

Then pass it to the binary:

    ./dist/demo/main process examples/demo_app/sample_input.csv /tmp/out.csv --license demo.lic

If the license is valid, processing continues normally. If the license is expired, bound to the wrong machine, or has been tampered with, the binary exits immediately with a plain-language error message.

## How to run the automated end-to-end tests

These tests build the demo, run it with various license scenarios, and check every result automatically:

    pytest -m e2e -v

The tests require PyArmor and PyInstaller to be installed. If either is missing, pytest prints a clear skip message explaining why.

## What is in this folder

The file main.py is the command-line entry point. It accepts a "process" subcommand with an input CSV path, an output CSV path, and an optional license file path.

The file secret_algorithm.py contains the proprietary churn-risk scoring function. It implements a logistic regression formula with six weighted inputs: age, income, tenure in months, number of products held, and number of support tickets. After PyArmor obfuscation, the numeric constants in this file will not appear as readable text in the binary.

The file data_loader.py handles reading and writing CSV files. It validates that required columns are present and raises clear error messages if the file is malformed.

The file license_check.py validates PyShield license files. It is self-contained so it can be bundled inside the PyInstaller binary without importing from PyShield's src directory.

The file sample_input.csv contains 20 rows of plausible fake customer data for testing.

The file expected_output.csv contains the exact output that the program should produce when run against sample_input.csv. The values are computed from the formula in secret_algorithm.py. The end-to-end test checks that the binary's output matches this file byte for byte.

The files build_demo.sh and build_demo.bat are one-command build scripts for Linux or macOS and Windows respectively.

## What the output looks like

The output CSV contains all columns from the input plus a new column named churn_risk. The churn_risk column holds a decimal probability between 0.000000 and 1.000000. Values close to 1.0 indicate a customer who is very likely to cancel. Values close to 0.0 indicate a loyal customer.

For example, customer C004 (age 28, income 38000, 8 support tickets) receives a churn risk of 0.994271, meaning the model considers them extremely likely to churn. Customer C010 (age 55, income 125000, 84 months tenure) receives a churn risk of 0.000000, meaning the model considers them essentially certain to stay.

## Screen-reader notes

Every progress message printed by the application begins with "Step X of Y:" followed by a plain-language description of what is happening. Error messages are printed to standard error and begin with "Error:" so they are easy to identify. The license validation step prints its own "Step 1 of 4" prefix when a license is provided.
