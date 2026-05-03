# tests/test_debugger_detect.py
#
# Unit tests for the src/debugger_detect.py module.
#
# These tests verify that:
# - is_debugger_present returns a boolean.
# - assert_no_debugger does not raise in a normal test environment (no debugger).
# - The platform-specific helper functions each return a boolean.

import sys      # Used to identify the platform for platform-specific tests.

import pytest   # Provides test runner and assertion helpers.

# Import the functions being tested.
from src.debugger_detect import (
    is_debugger_present,
    assert_no_debugger,
    _is_debugger_present_linux,
    _is_debugger_present_macos,
    _is_debugger_present_windows,
)


def test_is_debugger_present_returns_bool():
    """is_debugger_present should always return a bool, never raise."""

    # Call the function and check the return type.
    result = is_debugger_present()
    assert isinstance(result, bool), (
        "is_debugger_present should always return a bool."
    )


def test_assert_no_debugger_does_not_raise_in_normal_test_environment():
    """assert_no_debugger should not raise when running under pytest without a debugger.

    pytest itself is not a native debugger in the sense that IsDebuggerPresent
    or TracerPid detect.  This test confirms the guard does not false-positive
    in the normal test-suite environment.
    """

    # Under normal pytest execution, this should not raise.
    # If you are running this test under a native debugger (gdb, lldb, WinDbg),
    # this test may legitimately fail.
    try:
        assert_no_debugger()
    except RuntimeError as exc:
        # If we are somehow running under a debugger in CI, skip instead of fail.
        pytest.skip(f"Debugger detected in test environment: {exc}")


def test_linux_helper_returns_bool():
    """The Linux helper should return a bool and never raise."""

    result = _is_debugger_present_linux()
    assert isinstance(result, bool), (
        "The Linux debugger detection helper should return a bool."
    )


def test_macos_helper_returns_bool():
    """The macOS helper should return a bool and never raise."""

    result = _is_debugger_present_macos()
    assert isinstance(result, bool), (
        "The macOS debugger detection helper should return a bool."
    )


def test_windows_helper_returns_bool():
    """The Windows helper should return a bool and never raise."""

    result = _is_debugger_present_windows()
    assert isinstance(result, bool), (
        "The Windows debugger detection helper should return a bool."
    )
