# CI Notes: End-to-End Test Policy

This document explains the CI workflow decisions in .github/workflows/build.yml, specifically the policy around which platforms are required to pass the end-to-end tests and why.

## Overview of the two test categories

The PyShield test suite is divided into two categories.

The first category is unit tests. These tests do not call PyArmor or PyInstaller. They test the Python logic directly: license generation and verification, hash computation, tamper detection, CLI argument parsing, and debugger detection. Unit tests run in milliseconds and require no external tools beyond the packages in requirements.txt and requirements-dev.txt. All unit tests must pass on all platforms.

The second category is end-to-end tests. These tests are marked with @pytest.mark.e2e and are selected with: pytest -m e2e -v. They call the full PyShield build pipeline, which invokes PyArmor and PyInstaller, builds a real binary, and then runs that binary to check its behaviour. End-to-end tests take approximately one to three minutes on a fresh CI runner.

## Why unit tests run first

The CI workflow runs unit tests first with: pytest -m "not e2e". This ensures that any failure in basic Python logic is caught quickly, without waiting for the longer build step. If unit tests fail, the CI run fails fast with a clear signal.

## Platform policy for end-to-end tests

Linux (ubuntu-latest) is the required platform. The end-to-end test step on Linux is set to continue-on-error: false. If the end-to-end tests fail on Linux, the CI run fails and pull requests cannot merge without fixing them. Linux is the primary deployment target for most server-side use cases, and the Linux runners on GitHub Actions have stable, predictable environments that support PyArmor and PyInstaller reliably.

Windows (windows-latest) and macOS (macos-latest) are best-effort platforms. The end-to-end test step on these platforms is set to continue-on-error: true. This means CI runs do not block on failures from these platforms. Failures are still visible in the GitHub Actions log and should be investigated, but they do not block merges.

The reason for the Windows and macOS best-effort status is that PyInstaller and PyArmor have historically had platform-specific packaging issues that take time to stabilise: antivirus interference on Windows, notarisation requirements on macOS, and differences in how each platform handles self-extracting archives. As these issues are resolved and the builds are confirmed stable, the continue-on-error setting on each platform can be changed to false.

## How to read CI failures

When a unit test fails, the error message will include the test name and a short traceback. The test name describes what was being checked. For example, test_verify_license_fails_for_expired_license is self-explanatory.

When an end-to-end test fails, there are two common reasons.

The first common reason is that PyArmor or PyInstaller is not installed or is at an incompatible version. The test will print a skip message like "PyArmor not available in this environment." If you see this, check that requirements.txt was installed correctly.

The second common reason is a genuine failure in the protection pipeline. For example, if PyArmor changes its output format in a new version, the test that checks for the absence of proprietary strings may start failing. If you see an assertion failure in test_obfuscation_hides_proprietary_strings, investigate the PyArmor version installed on the runner.

## How to change the platform policy

To require end-to-end tests to pass on Windows, change the line in build.yml from:

    continue-on-error: ${{ matrix.os != 'ubuntu-latest' }}

to:

    continue-on-error: ${{ matrix.os == 'macos-latest' }}

This would require both Linux and Windows to pass, leaving only macOS as best-effort.

To require all three platforms, change the line to:

    continue-on-error: false

Do this only after confirming that the end-to-end tests pass reliably on all three platforms in several consecutive CI runs.

## Running end-to-end tests locally

To run the end-to-end tests on your local machine, ensure PyArmor and PyInstaller are installed, then run:

    pytest -m e2e -v

The tests will print step-by-step progress. Each test that requires the demo binary reuses the same build, so the build only happens once per pytest session.

To skip the end-to-end tests and run only the fast unit tests:

    pytest -m "not e2e" -v
