# src/obfuscator.py
#
# This module wraps PyArmor to obfuscate Python source code.
# PyArmor transforms readable Python into scrambled bytecode that is hard to
# reverse-engineer but still executes correctly through PyArmor's runtime.
#
# The only public function is obfuscate().  Call it with the path to the
# directory that contains your original Python source and the path where you
# want the obfuscated output to land.  It returns the output directory path
# so the caller can pass it straight into the packager.
#
# No shell=True is used anywhere in this file.  All subprocess calls pass
# arguments as a list so the operating system cannot interpret shell
# metacharacters in user-supplied paths.

import os           # Used to resolve and create directory paths.
import subprocess   # Used to run PyArmor as a child process.
import sys          # Used to find the Python executable that owns this process.


def obfuscate(source_dir: str, output_dir: str) -> str:
    """Obfuscate a Python source tree with PyArmor.

    Parameters
    ----------
    source_dir : str
        Absolute or relative path to the directory that contains the original
        Python source files.  Every .py file in the tree will be processed.
    output_dir : str
        Absolute or relative path to the directory where obfuscated files
        should be written.  The directory will be created if it does not exist.

    Returns
    -------
    str
        The resolved absolute path of output_dir, so the caller can chain
        this directly into the packager without re-computing the path.

    Raises
    ------
    FileNotFoundError
        If source_dir does not exist.
    subprocess.CalledProcessError
        If PyArmor exits with a non-zero status code.
    """

    # Resolve source_dir to an absolute path so PyArmor receives a full path
    # regardless of the current working directory.
    source_dir = os.path.abspath(source_dir)

    # Confirm that the source directory actually exists before calling PyArmor.
    # Giving an early, clear error is better than letting PyArmor fail with a
    # cryptic message.
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(
            f"Source directory does not exist: {source_dir}"
        )

    # Resolve output_dir to an absolute path for the same reason.
    output_dir = os.path.abspath(output_dir)

    # Create the output directory and any missing parent directories.
    # exist_ok=True means this is a no-op if the directory already exists.
    os.makedirs(output_dir, exist_ok=True)

    # Build the argument list for PyArmor.
    # sys.executable is the Python interpreter that is running this script.
    # Running "python -m pyarmor" instead of a bare "pyarmor" command ensures
    # we use the PyArmor that is installed in the same virtual environment.
    #
    # Explanation of each flag:
    #   gen        — PyArmor 8 subcommand that generates obfuscated output.
    #   --recursive — Process every .py file in subdirectories, not just the
    #                 top level.
    #   --output   — Where to write the obfuscated files.
    #   source_dir — The directory to obfuscate.
    command = [
        sys.executable,   # e.g. /usr/bin/python3 or C:\Python310\python.exe
        "-m", "pyarmor",  # Invoke PyArmor as a Python module.
        "gen",            # Use the "gen" (generate) subcommand.
        "--recursive",    # Obfuscate all files in subdirectories too.
        "--output", output_dir,  # Write output here.
        source_dir,       # The source tree to obfuscate.
    ]

    # Run PyArmor.  check=True means Python will raise CalledProcessError if
    # PyArmor exits with a non-zero return code, which indicates an error.
    # We capture stdout and stderr so they can be included in any exception
    # message, making diagnosis easier without visual scanning of terminal output.
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,   # Decode stdout/stderr as text rather than bytes.
    )

    # Log PyArmor's stdout for the caller's information.
    # This is printed as a plain sentence so it reads well through a screen reader.
    if result.stdout.strip():
        print(f"PyArmor output: {result.stdout.strip()}")

    # Return the resolved output directory path for chaining.
    return output_dir
