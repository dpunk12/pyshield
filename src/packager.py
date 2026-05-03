# src/packager.py
#
# This module wraps PyInstaller to package a Python application into a single
# standalone executable file.
#
# The only public function is package().  Call it with the path to the
# obfuscated source directory, the name of the entry-point script within that
# directory, the output directory, and an optional name for the executable.
#
# No shell=True is used anywhere in this file.  All subprocess calls pass
# arguments as a list.
#
# After packaging, this module calls tamper.compute_hash to record a SHA-256
# fingerprint of the produced executable, so that any future modification can
# be detected.

import os           # Used to resolve paths and locate the produced executable.
import subprocess   # Used to run PyInstaller as a child process.
import sys          # Used to find the Python executable for the current env.

# Import our tamper-detection helper.  The leading dot means "from the same
# package (src)", which works regardless of how the package is installed or
# invoked.
from .tamper import compute_hash


def package(
    obfuscated_dir: str,
    entry_file: str,
    output_dir: str,
    platform_name: str = "",
    name: str = "app",
) -> str:
    """Package an obfuscated Python tree into a single standalone executable.

    Parameters
    ----------
    obfuscated_dir : str
        Path to the directory containing the obfuscated Python files.
    entry_file : str
        The filename of the entry-point script inside obfuscated_dir.
        For example "main.py".
    output_dir : str
        Directory where the finished executable will be placed.
    platform_name : str, optional
        An informational string describing the target platform, for example
        "linux", "windows", or "macos".  Not currently passed to PyInstaller
        because cross-compilation requires special toolchains; it is included
        here for future use and for CI labelling.
    name : str, optional
        The base name for the output executable.  Defaults to "app".

    Returns
    -------
    str
        The absolute path to the produced executable file.

    Raises
    ------
    FileNotFoundError
        If obfuscated_dir does not exist, or if entry_file does not exist
        inside obfuscated_dir.
    subprocess.CalledProcessError
        If PyInstaller exits with a non-zero status code.
    RuntimeError
        If the expected executable cannot be found after PyInstaller runs.
    """

    # Resolve all paths to absolute form.
    obfuscated_dir = os.path.abspath(obfuscated_dir)
    output_dir = os.path.abspath(output_dir)

    # Check that the obfuscated directory exists.
    if not os.path.isdir(obfuscated_dir):
        raise FileNotFoundError(
            f"Obfuscated source directory does not exist: {obfuscated_dir}"
        )

    # Build the full path to the entry-point script.
    entry_path = os.path.join(obfuscated_dir, entry_file)

    # Verify the entry-point script exists inside the obfuscated directory.
    if not os.path.isfile(entry_path):
        raise FileNotFoundError(
            f"Entry-point script not found: {entry_path}"
        )

    # Create the output directory if it does not already exist.
    os.makedirs(output_dir, exist_ok=True)

    # Build the argument list for PyInstaller.
    # sys.executable ensures we use the PyInstaller from the same virtual env.
    #
    # Explanation of each flag:
    #   --onefile    — Bundle everything into one single executable file.
    #   --noconfirm  — Overwrite the previous build without asking for
    #                  confirmation.
    #   --clean      — Delete PyInstaller's build cache before starting, so
    #                  the output is always fresh.
    #   --distpath   — Where to place the finished executable.
    #   --workpath   — Where to put temporary build files (we put them inside
    #                  output_dir/build so they are easy to find and clean up).
    #   --specpath   — Where to write the .spec file that PyInstaller generates.
    #   --name       — The base name of the output executable.
    #   entry_path   — The Python script that is the program's entry point.
    command = [
        sys.executable,        # The Python interpreter for this environment.
        "-m", "PyInstaller",   # Invoke PyInstaller as a Python module.
        "--onefile",           # Produce a single file, not a folder.
        "--noconfirm",         # Do not prompt; overwrite existing output.
        "--clean",             # Delete cached build artifacts first.
        "--distpath", output_dir,   # Where to place the finished executable.
        "--workpath", os.path.join(output_dir, "build"),  # Temp build files.
        "--specpath", os.path.join(output_dir, "spec"),   # Spec file location.
        "--name", name,        # Name of the output executable.
        entry_path,            # The entry-point script to package.
    ]

    # Run PyInstaller and raise CalledProcessError if it fails.
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    # Log PyInstaller's stdout if it produced any output.
    if result.stdout.strip():
        print(f"PyInstaller output: {result.stdout.strip()}")

    # Determine what the executable will be named on this platform.
    # On Windows, PyInstaller appends .exe.  On everything else, no extension.
    if sys.platform.startswith("win"):
        executable_name = name + ".exe"
    else:
        executable_name = name

    # Build the expected full path to the produced executable.
    executable_path = os.path.join(output_dir, executable_name)

    # Verify PyInstaller actually created the file before we try to hash it.
    if not os.path.isfile(executable_path):
        raise RuntimeError(
            f"PyInstaller finished but the expected executable was not found: "
            f"{executable_path}"
        )

    # Compute and record the SHA-256 hash of the executable.
    # The hash is written to a sidecar file next to the executable.
    # This allows integrity checking at any point in the future.
    hash_file_path = compute_hash(executable_path)
    print(
        f"SHA-256 hash written to: {hash_file_path}"
    )

    # Return the path to the executable so the caller can use it directly.
    return executable_path
