# docs/architecture.md

This document describes the internal architecture of PyShield in plain prose. There are no diagrams. Every component is described as text.

## Overview

PyShield is a command-line tool written in Python. It is composed of a CLI layer and five functional modules, each in a separate file under the src directory.

The CLI layer lives in pyshield.py at the root of the repository. It uses Python's standard argparse module to parse command-line arguments and then dispatches to the appropriate module function. The CLI layer contains no business logic itself; it only translates user input into function calls.

The five functional modules are:

1. src/obfuscator.py — Wraps PyArmor to scramble Python source code.
2. src/packager.py — Wraps PyInstaller to bundle code into an executable.
3. src/license_manager.py — Generates and verifies license files.
4. src/tamper.py — Computes and verifies SHA-256 file hashes.
5. src/debugger_detect.py — Detects debugger attachment at runtime.

## Data Flow for the 'build' Command

When the user runs "python pyshield.py build", the following happens in order.

First, the CLI layer parses the arguments and calls cmd_build in pyshield.py.

Second, cmd_build calls obfuscate() from src/obfuscator.py. obfuscate() runs PyArmor as a child process, passing the source directory and the output directory. PyArmor writes obfuscated Python files to the output directory. obfuscate() returns the output directory path.

Third, cmd_build calls package() from src/packager.py. package() runs PyInstaller as a child process, passing the obfuscated directory and the entry-point script. PyInstaller writes a single-file executable to the dist directory. After PyInstaller finishes, package() calls compute_hash() from src/tamper.py to record a SHA-256 fingerprint of the executable.

## License Flow

When the user runs "python pyshield.py license generate", the CLI calls generate_license() from src/license_manager.py.

generate_license() builds a JSON document containing the issue date, an optional expiry date, and an optional machine ID. It then computes an HMAC-SHA256 signature over the document and adds the signature to the JSON. The finished document is written to a file.

When the user (or the protected application) calls verify_license(), the function reads the JSON file, recomputes the signature, and compares it with the stored one. If the signature matches, it checks the machine ID (if present) and the expiry date (if present). If all checks pass, verify_license returns True.

## Tamper Detection Flow

The tamper.py module uses SHA-256 hashes. SHA-256 is a one-way function that produces a 64-character hexadecimal string from any input. Any change to even one byte of the input produces a completely different output.

compute_hash() reads the target file in 64-kilobyte chunks, feeds each chunk to a SHA-256 hasher, and writes the final hex digest to a sidecar file named file_path + ".sha256".

verify_hash() reads the stored digest from the sidecar file, recomputes the digest from the current file contents, and raises RuntimeError if they differ.

## Subprocess Security

All calls to external tools (PyArmor, PyInstaller) use subprocess.run with a list of arguments. No call uses shell=True. This prevents shell injection attacks where a malicious file path could include shell metacharacters that would be interpreted by the shell.

## Platform Support

The code is written to run on Windows, Linux, and macOS. Platform-specific behaviour is limited to:

- src/debugger_detect.py, which uses different APIs on each platform.
- src/packager.py, which appends ".exe" to the executable name on Windows.

The GitHub Actions workflow runs the build on all three platforms.
