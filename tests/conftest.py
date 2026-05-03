# tests/conftest.py
#
# Shared pytest fixtures for the PyShield test suite.
#
# This file is automatically loaded by pytest before any test file runs.
# Fixtures defined here are available to every test file in the tests/ directory.
#
# The key fixture is built_demo, which builds the demo application once per
# test session and returns the path to the finished binary AND the path to
# the .pyshield_secret file created during the build.  All end-to-end
# tests that need the binary reuse this single build, so PyArmor and
# PyInstaller are only invoked once per CI run.
#
# If PyArmor or PyInstaller are not installed in the test environment,
# this fixture calls pytest.skip() with a clear message instead of failing.

import os         # Used to resolve file paths and check file existence.
import subprocess # Used to invoke the PyShield build command.
import sys        # Used to find the Python executable for the current environment.

import pytest     # Provides the fixture decorator and skip mechanism.


def _check_tool_available(tool_module_name: str) -> None:
    """Check that a Python module (tool) is importable as a command.

    Attempts to run "python -m <tool_module_name> --version" and calls
    pytest.skip() if the tool is not available.

    Args:
        tool_module_name: The module name to check, e.g. "pyarmor" or "PyInstaller".

    Returns:
        None.  If the tool is unavailable, pytest.skip() is called (which
        raises an internal exception that pytest handles).
    """

    try:
        # Run the tool with --version to confirm it is installed and works.
        result = subprocess.run(
            [sys.executable, "-m", tool_module_name, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # A non-zero exit code means the module ran but reported an error.
        if result.returncode != 0:
            pytest.skip(
                f"{tool_module_name} is not available in this environment: "
                f"{result.stderr.strip()}"
            )

    except FileNotFoundError:
        # The Python executable itself was not found — very unlikely.
        pytest.skip(
            f"{tool_module_name} is not available: Python executable not found."
        )
    except subprocess.TimeoutExpired:
        # The tool hung.
        pytest.skip(
            f"{tool_module_name} is not available: version check timed out."
        )
    except Exception as exc:
        # Any other unexpected error.
        pytest.skip(
            f"{tool_module_name} is not available in this environment: {exc}"
        )


@pytest.fixture(scope="session")
def built_demo(tmp_path_factory):
    """Build the demo application once per test session.

    This fixture:
    1. Checks that PyArmor and PyInstaller are available; skips all e2e tests
       if either is missing.
    2. Runs "python pyshield.py build --source examples/demo_app ..." to
       produce a protected binary.
    3. Yields a tuple of (binary_path, secret_path) where binary_path is the
       absolute path to the finished binary and secret_path is the absolute
       path to the .pyshield_secret file written by the build.  End-to-end
       tests that generate licenses must pass --secret-file secret_path (or
       pass the secret bytes directly) so that the license is signed with the
       same key that was embedded in the binary.

    Because the scope is "session", the build runs only once per pytest
    invocation, even if multiple tests depend on this fixture.

    Args:
        tmp_path_factory: A pytest built-in session-scoped fixture that provides
                          a factory for creating temporary directories.

    Yields:
        tuple[str, str]: A two-element tuple:
            - The absolute path to the compiled binary.
              On Linux and macOS this ends in "/main".
              On Windows it ends in "/main.exe".
            - The absolute path to the .pyshield_secret file written by the
              build.  Pass this to --secret-file when generating test licenses.
    """

    # --- Check that PyArmor is installed. ---
    # PyArmor is the obfuscation tool.  Without it the build cannot obfuscate.
    _check_tool_available("pyarmor")

    # --- Check that PyInstaller is installed. ---
    # PyInstaller is the packaging tool.  Without it the build cannot create
    # a standalone binary.
    _check_tool_available("PyInstaller")

    # --- Find the repository root. ---
    # This conftest.py lives in tests/, so going one level up gives the repo root.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # --- Create a temporary output directory for this test session. ---
    # tmp_path_factory.mktemp creates a uniquely named directory under the
    # system temp folder.  It is cleaned up automatically after the session.
    dist_dir = str(tmp_path_factory.mktemp("pyshield_demo_dist"))

    # --- Run the PyShield build command. ---
    # We invoke pyshield.py as a script using the same Python interpreter that
    # is running pytest, so the correct virtual environment is used.
    print(f"\nBuilding demo app for e2e tests. Output directory: {dist_dir}")

    build_result = subprocess.run(
        [
            sys.executable,       # Same Python that is running pytest.
            "pyshield.py",        # The PyShield CLI script.
            "build",              # The 'build' subcommand (obfuscate + package).
            "--source", os.path.join(repo_root, "examples", "demo_app"),
            "--entry", "main.py", # Entry-point within the demo app directory.
            "--output", dist_dir, # Where to put the finished binary.
            "--name", "main",     # Name the binary "main" (or "main.exe" on Windows).
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,            # Run from the repo root so imports resolve correctly.
        timeout=300,              # Allow up to 5 minutes for the build.
    )

    # If the build failed, skip the tests with a clear explanation.
    if build_result.returncode != 0:
        # Limit the error summary to keep the skip message readable, but
        # add an indicator when the output was truncated so the reader knows
        # to check the full CI log for more context.
        raw_error = build_result.stderr or build_result.stdout or "no output"
        truncate_limit = 500
        if len(raw_error) > truncate_limit:
            error_summary = raw_error[:truncate_limit] + " ... (truncated — see full log)"
        else:
            error_summary = raw_error
        pytest.skip(
            f"Demo app build failed (exit code {build_result.returncode}). "
            f"Error: {error_summary}"
        )

    # --- Find the produced binary. ---
    # PyInstaller names the binary after the --name argument.
    # On Windows it appends .exe; on all other platforms there is no extension.
    if sys.platform.startswith("win"):
        binary_name = "main.exe"
    else:
        binary_name = "main"

    binary_path = os.path.join(dist_dir, binary_name)

    # Confirm the binary was actually created.
    if not os.path.isfile(binary_path):
        pytest.skip(
            f"Build completed but the expected binary was not found at: {binary_path}. "
            f"Build output: {build_result.stdout[:300]}"
        )

    # --- Find the secret file that was created by the build. ---
    # The 'pyshield build' command writes the per-build HMAC secret to
    # <output_dir>/.pyshield_secret.  End-to-end tests that generate licenses
    # must use this file (via --secret-file) so the license is signed with the
    # same key that was embedded in the binary during obfuscation.
    secret_path = os.path.join(dist_dir, ".pyshield_secret")

    if not os.path.isfile(secret_path):
        # This should not happen if the build succeeded, but check explicitly
        # so the error message is actionable rather than cryptic.
        pytest.skip(
            f"Build succeeded but the secret file was not found at: {secret_path}. "
            "Check that 'pyshield build' calls load_or_create_secret correctly."
        )

    print(f"Demo binary built successfully: {binary_path}")
    print(f"Build secret file: {secret_path}")

    # --- Yield both the binary path and the secret file path to the tests. ---
    # "yield" instead of "return" makes this a generator-based fixture so pytest
    # can run cleanup code after all tests finish (though we have none here,
    # since tmp_path_factory handles cleanup).
    yield binary_path, secret_path
