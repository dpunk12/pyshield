# src/debugger_detect.py
#
# This module detects whether a debugger is attached to the running process.
# Debuggers are tools that allow a user to pause execution, inspect memory,
# and trace through code step by step.  For a protected application, allowing
# a debugger to attach makes it easier for an attacker to reverse-engineer
# the code or bypass license checks.
#
# Detection is platform-specific:
#   - Windows: The Win32 API function IsDebuggerPresent() returns 1 when a
#     debugger is attached.
#   - Linux: The kernel writes a non-zero TracerPid value into
#     /proc/self/status when a tracer (such as a debugger using ptrace) is
#     attached.
#   - macOS: The sysctl() call with the P_TRACED flag reports whether the
#     process is being traced.
#
# If the platform is not recognised, the function returns False (no detection
# is possible, which is safer than crashing).

import ctypes    # Used on Windows to call the Win32 IsDebuggerPresent API.
import os        # Used on Linux to read /proc/self/status.
import struct    # Used on macOS to pack the sysctl arguments.
import sys       # Used to identify the current operating system platform.


def is_debugger_present() -> bool:
    """Return True if a debugger appears to be attached to this process.

    Uses platform-specific checks:
    - Windows: calls IsDebuggerPresent via ctypes.
    - Linux: reads TracerPid from /proc/self/status.
    - macOS: calls sysctl with the KERN_PROC / P_TRACED constants.

    Returns
    -------
    bool
        True if a debugger is detected, False otherwise.  Returns False on
        unknown platforms where detection is not implemented.
    """

    # Choose the detection method based on the current platform.
    if sys.platform.startswith("win"):
        # Windows detection path.
        return _is_debugger_present_windows()

    if sys.platform.startswith("linux"):
        # Linux detection path.
        return _is_debugger_present_linux()

    if sys.platform == "darwin":
        # macOS detection path.
        return _is_debugger_present_macos()

    # Unknown platform: return False rather than raising an error so that the
    # rest of the application continues to work even on unusual systems.
    return False


def assert_no_debugger() -> None:
    """Raise RuntimeError if a debugger is detected.

    Call this at the start of any security-sensitive function to prevent an
    attacker from stepping through the code with a debugger.

    Raises
    ------
    RuntimeError
        If is_debugger_present() returns True.
    """

    # Check for a debugger and raise a descriptive error if one is found.
    if is_debugger_present():
        raise RuntimeError(
            "A debugger is attached to this process. "
            "The application cannot continue."
        )


def _is_debugger_present_windows() -> bool:
    """Windows-specific debugger detection using the Win32 API.

    The Windows kernel tracks whether each process was started under a
    debugger.  IsDebuggerPresent is a standard, well-documented API call
    that returns 1 when a debugger is present and 0 otherwise.

    Returns
    -------
    bool
        True if IsDebuggerPresent returned a non-zero value.
    """

    try:
        # Load kernel32.dll, which is the Windows core library.
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        # Call IsDebuggerPresent.  It returns an integer: 1 means yes, 0 no.
        result = kernel32.IsDebuggerPresent()

        # Convert to bool: any non-zero integer means a debugger is present.
        return bool(result)

    except Exception:
        # If the call fails for any reason (unexpected platform, missing DLL),
        # return False to avoid crashing the application.
        return False


def _is_debugger_present_linux() -> bool:
    """Linux-specific debugger detection using /proc/self/status.

    The Linux kernel writes information about each process into a virtual
    file at /proc/self/status.  One of the fields is "TracerPid".  Its value
    is the process ID of the tracer (e.g. the debugger).  A value of 0 means
    no tracer is attached.

    Returns
    -------
    bool
        True if TracerPid is non-zero.
    """

    try:
        # Open /proc/self/status in text mode.  This file is always present on
        # Linux and does not require any special permissions.
        with open("/proc/self/status", "r", encoding="utf-8") as status_file:
            # Read all lines from the status file.
            for line in status_file:
                # Find the line that starts with "TracerPid:".
                if line.startswith("TracerPid:"):
                    # The format is "TracerPid:\t<number>\n".
                    # Split on whitespace and take the second token.
                    parts = line.split()

                    # parts[0] is "TracerPid:", parts[1] is the PID number.
                    if len(parts) >= 2:
                        tracer_pid = int(parts[1])
                        # A non-zero PID means a debugger or tracer is attached.
                        return tracer_pid != 0

        # If we read the whole file and did not find TracerPid, return False.
        return False

    except Exception:
        # If /proc/self/status cannot be read (e.g. unusual kernel), return False.
        return False


def _is_debugger_present_macos() -> bool:
    """macOS-specific debugger detection using sysctl.

    On macOS, the kernel exposes process information through the sysctl
    interface.  The kinfo_proc structure for the current process contains a
    flag called P_TRACED that is set when the process is being debugged.

    This implementation uses ctypes to call the C sysctl function directly.

    Returns
    -------
    bool
        True if the P_TRACED flag is set.
    """

    try:
        # Load libc, the C standard library on macOS.
        libc = ctypes.CDLL("libc.dylib", use_errno=True)

        # Constants from the macOS kernel headers.
        # CTL_KERN identifies the kernel subsystem.
        CTL_KERN = 1
        # KERN_PROC asks for process information.
        KERN_PROC = 14
        # KERN_PROC_PID asks for the information of one specific process.
        KERN_PROC_PID = 1
        # P_TRACED is the flag bit that indicates the process is being traced.
        P_TRACED = 0x00000800

        # Build the sysctl "name" array: [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid].
        # We use the current process's PID (os.getpid()).
        mib = (ctypes.c_int * 4)(CTL_KERN, KERN_PROC, KERN_PROC_PID, os.getpid())

        # kinfo_proc is a large struct returned by sysctl.  Its exact layout is
        # complex; we allocate 648 bytes which is the size on 64-bit macOS.
        kinfo_size = 648
        kinfo_buf = ctypes.create_string_buffer(kinfo_size)

        # size must be a mutable value that sysctl can update.
        size = ctypes.c_size_t(kinfo_size)

        # Call sysctl.  Return value 0 means success.
        ret = libc.sysctl(
            mib,            # The name array describing what to query.
            4,              # Length of the name array.
            kinfo_buf,      # Buffer to receive the result.
            ctypes.byref(size),  # Size of the buffer; updated by the kernel.
            None,           # newp: we are not setting a value, only reading.
            0,              # newlen: 0 because we are not setting a value.
        )

        # A return value other than 0 means the call failed.
        if ret != 0:
            return False

        # The p_flag field is at offset 32 in the kinfo_proc structure on
        # 64-bit macOS (this is the extern_proc.p_flag field).
        # We unpack a 4-byte integer from that offset.
        p_flag = struct.unpack_from("i", kinfo_buf.raw, 32)[0]

        # Test whether the P_TRACED bit is set in p_flag.
        return bool(p_flag & P_TRACED)

    except Exception:
        # If sysctl is not available or the call fails, return False.
        return False
