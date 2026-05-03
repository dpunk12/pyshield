# pyshield.py
#
# This is the main command-line interface for PyShield.
# Run it with "python pyshield.py <subcommand> [arguments]".
#
# Subcommands:
#   build             — Obfuscate source code and package it in one step.
#   obfuscate         — Obfuscate source code only (no packaging).
#   package           — Package an already-obfuscated tree only.
#   license generate  — Generate a new license file.
#   license verify    — Verify an existing license file.
#   hash verify       — Verify the SHA-256 hash of a file.
#
# All subcommands print a plain-English status message for each step they
# perform, so that output is meaningful when read aloud by a screen reader.
#
# No shell=True is used anywhere.  All subprocess calls are made through the
# src modules, which pass arguments as lists.

import argparse   # Standard library module for parsing command-line arguments.
import os         # Used to resolve paths and read environment variables.
import pathlib    # Used to represent and manipulate file paths.
import sys        # Used to read the platform name and exit with a status code.

# Import the PyShield modules that implement each operation.
# Each import is on its own line with a comment so it is easy to follow.
from src.build_secret import (
    load_or_create_secret,   # Loads or generates the per-build HMAC secret.
    secret_fingerprint,      # Returns the first 8 hex chars of SHA-256(secret).
)
from src.obfuscator import obfuscate          # Wraps PyArmor.
from src.packager import package              # Wraps PyInstaller.
from src.license_manager import (
    generate_license,   # Creates a signed license file.
    verify_license,     # Validates an existing license file.
)
from src.tamper import (
    compute_hash,   # Computes and saves the SHA-256 hash of a file.
    verify_hash,    # Checks a file against a saved SHA-256 hash.
)


def cmd_build(args: argparse.Namespace) -> int:
    """Handle the 'build' subcommand.

    Runs obfuscation and packaging in sequence.  Before obfuscation begins,
    a per-build HMAC secret is generated (or loaded from the environment
    variable PYSHIELD_HMAC_KEY or from a pre-existing secret file).  The
    secret is embedded into the source tree as _pyshield_runtime_constants.py
    so PyArmor encrypts it along with the rest of the source.  After
    obfuscation finishes, the unobfuscated constants file is deleted so the
    plaintext key is never left on disk in a readable form.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.  Expected attributes:
        - source: path to the Python source directory.
        - entry: name of the entry-point script.
        - output: path to the output directory.
        - name: base name for the executable.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """

    # Tell the user what is about to happen.
    print(f"Step 1 of 4: Preparing build secret for source directory: {args.source}")

    # -------------------------------------------------------------------------
    # Step 1 of 4: Load or generate the per-build HMAC secret.
    # -------------------------------------------------------------------------
    # The secret file is stored in the output directory alongside the binary.
    # .gitignore includes .pyshield_secret so it cannot be accidentally committed.
    output_path = pathlib.Path(args.output)
    secret_file = output_path / ".pyshield_secret"

    try:
        # load_or_create_secret checks PYSHIELD_HMAC_KEY env var first,
        # then looks for an existing file, then generates a fresh random secret.
        build_secret = load_or_create_secret(secret_file)
    except ValueError as exc:
        # The environment variable was set but invalid.
        print(f"Build failed: bad HMAC secret configuration: {exc}")
        return 1

    # Log only the fingerprint — never the secret itself.
    # The fingerprint is the first 8 hex chars of SHA-256(secret), which is
    # safe to include in build logs and audit trails because SHA-256 is a
    # one-way function: the fingerprint cannot be reversed to recover the secret.
    fingerprint = secret_fingerprint(build_secret)
    print(f"Build secret fingerprint: {fingerprint}")  # lgtm[py/clear-text-logging-sensitive-data]

    # -------------------------------------------------------------------------
    # Step 2 of 4: Write the runtime constants file into the source tree.
    # -------------------------------------------------------------------------
    # _pyshield_runtime_constants.py contains the HMAC key as a Python literal.
    # Placing it in the source tree means PyArmor will encrypt it along with
    # the rest of the code.  We delete the unobfuscated copy after PyArmor runs.
    source_path = pathlib.Path(args.source).resolve()
    constants_file = source_path / "_pyshield_runtime_constants.py"

    print(
        f"Step 2 of 4: Embedding build secret into source tree "
        f"(fingerprint: {fingerprint})."  # lgtm[py/clear-text-logging-sensitive-data]
    )

    try:
        # Write a minimal Python module that just defines the HMAC key.
        # bytes.fromhex is used at import time so the bytes literal in the
        # source is a hex string, which is readable and unambiguous.
        constants_content = (
            "# _pyshield_runtime_constants.py\n"
            "#\n"
            "# This file is generated automatically by 'pyshield build'.\n"
            "# It contains the per-build HMAC secret in an obfuscatable form.\n"
            "# PyArmor encrypts this file so the key is not readable in the\n"
            "# final binary.  The unobfuscated copy of this file is deleted\n"
            "# after obfuscation completes.\n"
            "#\n"
            "# Do NOT commit this file to source control.  It is .gitignore'd.\n"
            "# Do NOT distribute this file directly; only the obfuscated binary\n"
            "# should be delivered to end users.\n"
            "\n"
            f"HMAC_KEY = bytes.fromhex(\"{build_secret.hex()}\")\n"
        )
        constants_file.write_text(constants_content, encoding="utf-8")
    except OSError as exc:
        print(f"Build failed: could not write runtime constants file: {exc}")
        return 1

    # -------------------------------------------------------------------------
    # Step 3 of 4: Obfuscate the source code (including the constants file).
    # -------------------------------------------------------------------------
    # We place the obfuscated files in a subdirectory of the output directory.
    obfuscated_dir = os.path.join(args.output, "obfuscated")
    print(f"Step 3 of 4: Running obfuscation. Output will go to: {obfuscated_dir}")

    try:
        # Call the obfuscator module.  It returns the resolved output path.
        obfuscated_path = obfuscate(args.source, obfuscated_dir)
        print(f"Obfuscation complete. Obfuscated files are in: {obfuscated_path}")
    except Exception as exc:
        # Print a descriptive error message and return failure.
        print(f"Obfuscation failed: {exc}")
        # Clean up the unobfuscated constants file even if obfuscation failed.
        _delete_constants_file(constants_file)
        return 1
    finally:
        # Always delete the unobfuscated constants file so the plaintext key
        # is never left in the source tree after the build completes or fails.
        _delete_constants_file(constants_file)

    # -------------------------------------------------------------------------
    # Step 4 of 4: Package the obfuscated code into a standalone executable.
    # -------------------------------------------------------------------------
    print(f"Step 4 of 4: Running packaging. Entry point: {args.entry}. Output: {args.output}")

    try:
        # Determine the platform name from the current system for labelling.
        platform_name = sys.platform

        # Call the packager module.  It returns the path to the executable.
        executable_path = package(
            obfuscated_path,
            args.entry,
            args.output,
            platform_name=platform_name,
            name=args.name,
        )
        print(f"Packaging complete. Executable is at: {executable_path}")
    except Exception as exc:
        print(f"Packaging failed: {exc}")
        return 1

    # Report success with the fingerprint so it appears in CI logs.
    print(f"Build complete. Secret fingerprint: {fingerprint}")  # lgtm[py/clear-text-logging-sensitive-data]
    return 0


def _delete_constants_file(constants_file: pathlib.Path) -> None:
    """Delete the unobfuscated _pyshield_runtime_constants.py file if it exists.

    This is a cleanup helper called by cmd_build whether obfuscation succeeds
    or fails.  The file must be deleted so the plaintext HMAC key is never
    left in the source tree after the build step.

    Parameters
    ----------
    constants_file : pathlib.Path
        Path to the constants file to delete.

    Returns
    -------
    None
    """

    # Only attempt to delete the file if it actually exists.
    if constants_file.exists():
        try:
            constants_file.unlink()
        except OSError as exc:
            # Log a warning but do not fail the build — the file may have
            # already been cleaned up or the filesystem may be read-only.
            print(
                f"Warning: could not delete runtime constants file "
                f"{constants_file}: {exc}"
            )


def cmd_obfuscate(args: argparse.Namespace) -> int:
    """Handle the 'obfuscate' subcommand.

    Runs obfuscation only, without packaging.

    Parameters
    ----------
    args : argparse.Namespace
        Expected attributes: source, output.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """

    print(f"Running obfuscation for source directory: {args.source}")

    try:
        output_path = obfuscate(args.source, args.output)
        print(f"Obfuscation complete. Output is in: {output_path}")
    except Exception as exc:
        print(f"Obfuscation failed: {exc}")
        return 1

    return 0


def cmd_package(args: argparse.Namespace) -> int:
    """Handle the 'package' subcommand.

    Packages an already-obfuscated source tree into an executable.

    Parameters
    ----------
    args : argparse.Namespace
        Expected attributes: source, entry, output, name.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """

    print(f"Running packaging for obfuscated directory: {args.source}")

    try:
        platform_name = sys.platform
        executable_path = package(
            args.source,
            args.entry,
            args.output,
            platform_name=platform_name,
            name=args.name,
        )
        print(f"Packaging complete. Executable is at: {executable_path}")
    except Exception as exc:
        print(f"Packaging failed: {exc}")
        return 1

    return 0


def cmd_license_generate(args: argparse.Namespace) -> int:
    """Handle the 'license generate' subcommand.

    Generates a new signed license file.  The HMAC secret used to sign the
    license is loaded from (in order of preference):
    1. The file specified by --secret-file (if provided).
    2. The PYSHIELD_HMAC_KEY environment variable (64 hex chars).
    3. The default secret file at dist/.pyshield_secret.

    If none of these sources yields a valid secret, the command fails with a
    clear error message explaining what to do.

    Parameters
    ----------
    args : argparse.Namespace
        Expected attributes: output, machine_lock, days, secret_file.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """

    print(f"Generating license file at: {args.output}")

    # Log what the license will include so the user knows what to expect.
    if args.machine_lock:
        print("License will be locked to the current machine's hardware identifiers.")
    else:
        print("License will not be machine-locked.")

    if args.days and args.days > 0:
        print(f"License will expire in {args.days} days.")
    else:
        print("License will not expire.")

    # -------------------------------------------------------------------------
    # Resolve the HMAC secret.
    # -------------------------------------------------------------------------
    # The secret must match the one embedded in the protected binary.
    # We try three sources in order: --secret-file argument, then the default
    # file path dist/.pyshield_secret.  The environment variable
    # PYSHIELD_HMAC_KEY is checked automatically by load_or_create_secret
    # before looking at the file.

    # Determine which secret file path to use.
    # The --secret-file argument takes precedence over the default path.
    if args.secret_file:
        # The user explicitly provided a path.
        secret_path = pathlib.Path(args.secret_file)
    else:
        # Fall back to the conventional location written by "pyshield build".
        secret_path = pathlib.Path("dist") / ".pyshield_secret"

    # Try to load the secret.  If neither the env var nor the file is present,
    # load_or_create_secret would generate a new random secret — but for license
    # generation we do NOT want to silently create a random secret because the
    # license would then be signed with a key that does not match any binary.
    # So we check explicitly before calling load_or_create_secret.
    env_key = os.environ.get("PYSHIELD_HMAC_KEY")
    if env_key is None and not secret_path.exists():
        print(
            "Cannot generate license: no HMAC secret available. "
            f"Provide --secret-file pointing to a .pyshield_secret file, "
            "or set the PYSHIELD_HMAC_KEY environment variable. "
            "The secret file is created automatically by 'pyshield build'."
        )
        return 1

    try:
        build_secret = load_or_create_secret(secret_path)
    except ValueError as exc:
        print(f"License generation failed: bad HMAC secret configuration: {exc}")
        return 1

    # Log the fingerprint so the user can confirm they used the right key.
    # The fingerprint is the first 8 hex chars of SHA-256(secret): safe to print.
    fingerprint = secret_fingerprint(build_secret)
    print(f"Using secret with fingerprint: {fingerprint}")  # lgtm[py/clear-text-logging-sensitive-data]

    try:
        license_path = generate_license(
            output_path=args.output,
            machine_lock=args.machine_lock,
            days=args.days or 0,
            secret=build_secret,
        )
        print(f"License generated successfully. File is at: {license_path}")
    except Exception as exc:
        print(f"License generation failed: {exc}")
        return 1

    return 0


def cmd_license_verify(args: argparse.Namespace) -> int:
    """Handle the 'license verify' subcommand.

    Verifies an existing license file against the current machine and date.
    The HMAC secret used to verify the signature is loaded from (in order):
    1. The file specified by --secret-file (if provided).
    2. The PYSHIELD_HMAC_KEY environment variable (64 hex chars).
    3. The default secret file at dist/.pyshield_secret.

    If none of these sources yields a valid secret, the command fails with a
    clear error message.

    Parameters
    ----------
    args : argparse.Namespace
        Expected attributes: license, secret_file.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """

    print(f"Verifying license file: {args.license}")

    # -------------------------------------------------------------------------
    # Resolve the HMAC secret.
    # -------------------------------------------------------------------------
    if args.secret_file:
        secret_path = pathlib.Path(args.secret_file)
    else:
        secret_path = pathlib.Path("dist") / ".pyshield_secret"

    # Fail clearly if no secret source is available.
    env_key = os.environ.get("PYSHIELD_HMAC_KEY")
    if env_key is None and not secret_path.exists():
        print(
            "Cannot verify license: no HMAC secret available. "
            "Provide --secret-file or set PYSHIELD_HMAC_KEY environment variable."
        )
        return 1

    try:
        build_secret = load_or_create_secret(secret_path)
    except ValueError as exc:
        print(f"License verification failed: bad HMAC secret configuration: {exc}")
        return 1

    try:
        verify_license(args.license, secret=build_secret)
        print("License is valid.")
    except (FileNotFoundError, ValueError) as exc:
        print(f"License verification failed: {exc}")
        return 1

    return 0


def cmd_hash_verify(args: argparse.Namespace) -> int:
    """Handle the 'hash verify' subcommand.

    Verifies the SHA-256 hash of a file against a stored sidecar hash file.

    Parameters
    ----------
    args : argparse.Namespace
        Expected attributes: file, hash_file.

    Returns
    -------
    int
        Exit code: 0 for success, 1 for failure.
    """

    print(f"Verifying SHA-256 hash of file: {args.file}")

    try:
        verify_hash(args.file, args.hash_file)
        print("Hash verification passed. The file has not been modified.")
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Hash verification failed: {exc}")
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the PyShield CLI.

    Returns
    -------
    argparse.ArgumentParser
        The configured parser with all subcommands registered.
    """

    # Create the top-level parser.
    parser = argparse.ArgumentParser(
        prog="pyshield",
        description=(
            "PyShield: Python source-code protection. "
            "Obfuscates, packages, licenses, and guards your Python application."
        ),
    )

    # Create a subparser group for the top-level subcommands.
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # Make a subcommand required so the user sees an error if they omit it.
    subparsers.required = True

    # -------------------------------------------------------------------------
    # 'build' subcommand
    # -------------------------------------------------------------------------
    build_parser_obj = subparsers.add_parser(
        "build",
        help="Obfuscate and package in one step.",
        description=(
            "Obfuscate the source directory with PyArmor and then package it "
            "into a single-file executable with PyInstaller."
        ),
    )
    build_parser_obj.add_argument(
        "--source",
        required=True,
        help="Path to the directory containing the Python source files.",
    )
    build_parser_obj.add_argument(
        "--entry",
        required=True,
        help="Filename of the entry-point script inside the source directory.",
    )
    build_parser_obj.add_argument(
        "--output",
        required=True,
        help="Directory where the finished executable will be placed.",
    )
    build_parser_obj.add_argument(
        "--name",
        default="app",
        help="Base name for the output executable. Defaults to 'app'.",
    )
    # Register the handler function for the 'build' subcommand.
    build_parser_obj.set_defaults(func=cmd_build)

    # -------------------------------------------------------------------------
    # 'obfuscate' subcommand
    # -------------------------------------------------------------------------
    obfuscate_parser_obj = subparsers.add_parser(
        "obfuscate",
        help="Obfuscate source code only.",
        description=(
            "Run PyArmor on the source directory and write obfuscated files "
            "to the output directory.  Does not package."
        ),
    )
    obfuscate_parser_obj.add_argument(
        "--source",
        required=True,
        help="Path to the directory containing the Python source files.",
    )
    obfuscate_parser_obj.add_argument(
        "--output",
        required=True,
        help="Directory where obfuscated files will be written.",
    )
    obfuscate_parser_obj.set_defaults(func=cmd_obfuscate)

    # -------------------------------------------------------------------------
    # 'package' subcommand
    # -------------------------------------------------------------------------
    package_parser_obj = subparsers.add_parser(
        "package",
        help="Package an obfuscated tree into an executable.",
        description=(
            "Run PyInstaller on a directory that already contains obfuscated "
            "Python files and produce a single-file standalone executable."
        ),
    )
    package_parser_obj.add_argument(
        "--source",
        required=True,
        help="Path to the directory containing obfuscated Python files.",
    )
    package_parser_obj.add_argument(
        "--entry",
        required=True,
        help="Filename of the entry-point script.",
    )
    package_parser_obj.add_argument(
        "--output",
        required=True,
        help="Directory where the executable will be placed.",
    )
    package_parser_obj.add_argument(
        "--name",
        default="app",
        help="Base name for the output executable. Defaults to 'app'.",
    )
    package_parser_obj.set_defaults(func=cmd_package)

    # -------------------------------------------------------------------------
    # 'license' subcommand group
    # -------------------------------------------------------------------------
    license_parser_obj = subparsers.add_parser(
        "license",
        help="Generate or verify license files.",
        description="Manage PyShield license files.",
    )

    # Create a sub-subparser group for 'license generate' and 'license verify'.
    license_subparsers = license_parser_obj.add_subparsers(
        dest="license_command",
        metavar="LICENSE_COMMAND",
    )
    license_subparsers.required = True

    # 'license generate' sub-subcommand.
    lic_gen = license_subparsers.add_parser(
        "generate",
        help="Generate a new license file.",
        description=(
            "Create a signed license file.  Optionally lock it to this "
            "machine or set an expiry date."
        ),
    )
    lic_gen.add_argument(
        "--output",
        required=True,
        help="Path where the license file will be written.",
    )
    lic_gen.add_argument(
        "--machine-lock",
        action="store_true",
        dest="machine_lock",
        help=(
            "Bind the license to the current machine's hardware identifiers "
            "so it cannot be used on a different machine."
        ),
    )
    lic_gen.add_argument(
        "--days",
        type=int,
        default=0,
        help=(
            "Number of days until the license expires.  "
            "If not supplied or 0, the license does not expire."
        ),
    )
    lic_gen.add_argument(
        "--secret-file",
        dest="secret_file",
        default=None,
        metavar="PATH",
        help=(
            "Path to the .pyshield_secret file written by 'pyshield build'.  "
            "Defaults to dist/.pyshield_secret.  "
            "The PYSHIELD_HMAC_KEY environment variable is checked first."
        ),
    )
    lic_gen.set_defaults(func=cmd_license_generate)

    # 'license verify' sub-subcommand.
    lic_ver = license_subparsers.add_parser(
        "verify",
        help="Verify a license file.",
        description=(
            "Validate a license file.  Checks the signature, machine ID if "
            "locked, and expiry date if set."
        ),
    )
    lic_ver.add_argument(
        "--license",
        required=True,
        help="Path to the license file to verify.",
    )
    lic_ver.add_argument(
        "--secret-file",
        dest="secret_file",
        default=None,
        metavar="PATH",
        help=(
            "Path to the .pyshield_secret file written by 'pyshield build'.  "
            "Defaults to dist/.pyshield_secret.  "
            "The PYSHIELD_HMAC_KEY environment variable is checked first."
        ),
    )
    lic_ver.set_defaults(func=cmd_license_verify)

    # -------------------------------------------------------------------------
    # 'hash' subcommand group
    # -------------------------------------------------------------------------
    hash_parser_obj = subparsers.add_parser(
        "hash",
        help="Compute or verify SHA-256 hashes.",
        description="Manage SHA-256 hash files for tamper detection.",
    )

    hash_subparsers = hash_parser_obj.add_subparsers(
        dest="hash_command",
        metavar="HASH_COMMAND",
    )
    hash_subparsers.required = True

    # 'hash verify' sub-subcommand.
    hash_ver = hash_subparsers.add_parser(
        "verify",
        help="Verify a file against a stored SHA-256 hash.",
        description=(
            "Read the expected hash from a sidecar file and compare it to "
            "the current hash of the target file."
        ),
    )
    hash_ver.add_argument(
        "--file",
        required=True,
        help="Path to the file to verify.",
    )
    hash_ver.add_argument(
        "--hash-file",
        dest="hash_file",
        default="",
        help=(
            "Path to the .sha256 sidecar file.  "
            "Defaults to the file path with '.sha256' appended."
        ),
    )
    hash_ver.set_defaults(func=cmd_hash_verify)

    return parser


def main() -> int:
    """Parse arguments and dispatch to the appropriate subcommand handler.

    Returns
    -------
    int
        The exit code from the subcommand handler: 0 for success, 1 for error.
    """

    # Build the parser and parse the command-line arguments.
    parser = build_parser()
    args = parser.parse_args()

    # Call the handler function registered by set_defaults(func=...) above.
    return args.func(args)


# Standard Python idiom: only run main() when this file is executed directly,
# not when it is imported as a module.
if __name__ == "__main__":
    # Pass the return value of main() to sys.exit so the shell sees the correct
    # exit code.  Exit code 0 means success; any other value means failure.
    sys.exit(main())
