# PyShield

PyShield is an enterprise-grade Python source-code protection tool. It obfuscates your Python source code, packages it into a standalone executable, generates and verifies machine-locked or expiry-dated licenses, detects tampering with SHA-256 hashes, and detects debugger attachment at runtime. It runs on Windows, Linux, and macOS.

This README is written for screen readers. There are no ASCII diagrams or alignment-based formatting. Every section is written as plain prose.

## Table of Contents

1. What PyShield Does
2. Requirements
3. Installation
4. Quickstart
5. Three-Step Walkthrough
6. CLI Reference
7. Module Reference
8. Running Tests
9. Accessibility Notes
10. License

---

## 1. What PyShield Does

PyShield protects Python source code in four ways.

First, it uses PyArmor to obfuscate the source. Obfuscation transforms readable Python into a form that is difficult to reverse-engineer, while still allowing the code to run normally.

Second, it uses PyInstaller to bundle the obfuscated code into a single-file standalone executable. The result is one file that can be distributed without a Python installation on the end user's machine.

Third, it generates license files that can be tied to a specific machine (using a hash of the CPU, MAC address, and disk serial number), to an expiry date, or to both. The protected application reads and verifies this license at startup.

Fourth, it records a SHA-256 hash of the packaged executable and checks that hash at runtime, so that any modification to the distributed file is detected immediately.

In addition, the runtime guard detects whether a debugger is attached to the process. On Windows it calls the IsDebuggerPresent API. On Linux it reads the TracerPid field from the process status file. On macOS it calls the sysctl API. If a debugger is found, the program exits.

---

## 2. Requirements

Python 3.8 or newer is required.

Runtime dependencies:

- pyarmor version 8.0 or newer. Provides the obfuscation engine.
- pyinstaller version 5.0 or newer. Packages Python applications into executables.
- cryptography. Used for license signing and verification.
- psutil. Used to read system hardware identifiers for machine locking.

Development dependencies (only needed to run the test suite):

- pytest
- pytest-cov

---

## 3. Installation

Clone the repository and install the dependencies.

```
git clone https://github.com/dpunk12/pyshield.git
cd pyshield
pip install -r requirements.txt
```

To also install development tools:

```
pip install -r requirements-dev.txt
```

---

## 4. Quickstart

Protect a project in one command:

```
python pyshield.py build --source my_project/ --entry main.py --output dist/
```

This obfuscates everything under my_project, bundles it with PyInstaller, records the SHA-256 hash, and places the result in dist/.

Generate a license tied to this machine that expires in 30 days:

```
python pyshield.py license generate --days 30 --output my_project.lic
```

Verify a license:

```
python pyshield.py license verify --license my_project.lic
```

---

## 5. Three-Step Walkthrough

This walkthrough takes a small example project from raw Python source to a protected, licensed executable.

Step 1: Obfuscate the source.

Run the obfuscate subcommand, pointing it at the source directory and choosing an output directory. PyShield calls PyArmor with the gen subcommand, passes the recursive flag so every file in the tree is processed, and places the transformed files in the output directory you specify.

```
python pyshield.py obfuscate --source my_project/ --output obfuscated/
```

After this step, the obfuscated/ directory contains the scrambled Python files.

Step 2: Package into an executable.

Run the package subcommand, pointing it at the obfuscated directory and naming the entry-point file.

```
python pyshield.py package --source obfuscated/ --entry main.py --output dist/ --name my_app
```

PyShield calls PyInstaller with the onefile, noconfirm, and clean flags. The result is a single executable in dist/my_app (or dist/my_app.exe on Windows). PyShield also writes a SHA-256 hash of that file to dist/my_app.sha256.

Step 3: Generate and embed a license.

Generate a machine-locked license that expires in 90 days:

```
python pyshield.py license generate --machine-lock --days 90 --output dist/product.lic
```

Distribute dist/my_app and dist/product.lic together. On startup, your application should call pyshield.src.license_manager.verify_license to check the license file.

---

## 6. CLI Reference

All subcommands are accessed through pyshield.py.

### pyshield build

Runs obfuscation and packaging in one step.

Arguments:
- --source: Path to the directory containing your Python source files. Required.
- --entry: Filename of the entry-point script inside the source directory. Required.
- --output: Directory where the final executable will be placed. Required.
- --name: Name for the output executable. Defaults to "app".

### pyshield obfuscate

Runs only the obfuscation step.

Arguments:
- --source: Path to the directory containing your Python source files. Required.
- --output: Directory where the obfuscated files will be placed. Required.

### pyshield package

Runs only the packaging step.

Arguments:
- --source: Path to the directory containing obfuscated files. Required.
- --entry: Filename of the entry-point script. Required.
- --output: Directory where the executable will be placed. Required.
- --name: Name for the output executable. Defaults to "app".

### pyshield license generate

Generates a new license file.

Arguments:
- --output: Path for the generated license file. Required.
- --machine-lock: If present, binds the license to the current machine's hardware identifiers.
- --days: Number of days until the license expires. If omitted, the license does not expire.

### pyshield license verify

Verifies a license file.

Arguments:
- --license: Path to the license file to verify. Required.

### pyshield hash verify

Verifies the SHA-256 hash of a file.

Arguments:
- --file: Path to the file to verify. Required.
- --hash-file: Path to the .sha256 file containing the expected hash. Required.

---

## 7. Module Reference

All modules live in the src/ directory.

### src/obfuscator.py

Contains the obfuscate function. Accepts a source directory path and an output directory path. Calls PyArmor as a subprocess and returns the path to the obfuscated tree.

### src/packager.py

Contains the package function. Accepts an obfuscated directory path, an entry-point filename, an output directory path, and a platform name. Calls PyInstaller as a subprocess and returns the path to the generated executable.

### src/license_manager.py

Contains generate_license and verify_license functions. generate_license creates a signed JSON license file. verify_license reads and validates a license file, checking the machine ID and expiry date if applicable.

### src/tamper.py

Contains compute_hash and verify_hash functions. compute_hash calculates the SHA-256 hash of a file and writes it to a sidecar file. verify_hash reads the sidecar file and confirms the target file still matches.

### src/debugger_detect.py

Contains is_debugger_present and assert_no_debugger functions. is_debugger_present returns True if a debugger is attached, using platform-specific checks. assert_no_debugger calls is_debugger_present and raises RuntimeError if a debugger is found.

---

## 8. Running Tests

```
pytest tests/ -v
```

To generate a coverage report:

```
pytest tests/ --cov=src --cov-report=term-missing
```

---

## 9. Accessibility Notes

See ACCESSIBILITY.md for a full description of how this project is maintained with screen-reader accessibility in mind.

---

## 10. License

MIT License. Copyright dpunk12. See the LICENSE file for the full text.

