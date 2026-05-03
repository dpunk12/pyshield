# tests/test_end_to_end.py
#
# Real end-to-end tests for PyShield.
#
# Unlike the unit tests in test_cli.py, test_obfuscator.py, etc., these tests
# do NOT mock subprocess.run.  They actually invoke the full PyShield pipeline:
# PyArmor obfuscates the demo app, PyInstaller packages it into a binary, and
# we run that binary to prove protection works.
#
# All tests in this file are marked with @pytest.mark.e2e so they can be
# selected with: pytest -m e2e -v
# or skipped in environments without PyArmor/PyInstaller: pytest -m "not e2e"
#
# The shared "built_demo" fixture in conftest.py builds the binary once per
# session.  If PyArmor or PyInstaller are not installed, the fixture calls
# pytest.skip() and all these tests are skipped with a clear message.
#
# IMPORTANT: built_demo now yields a tuple (binary_path, secret_path).
# All tests must unpack it as: binary_path, secret_path = built_demo
#
# Test summary:
#   1. test_obfuscation_hides_proprietary_strings
#      Reads the binary as bytes and asserts that readable proprietary strings
#      are not present.  This is the primary proof that source is protected.
#
#   2. test_protected_binary_runs_correctly
#      Runs the binary with a valid license and checks that the output CSV
#      matches examples/demo_app/expected_output.csv byte for byte.
#
#   3. test_tamper_detection_rejects_modified_binary
#      Modifies the binary by flipping one byte, then runs the PyShield hash
#      verification command and asserts it reports a tamper error.
#
#   4. test_expired_license_is_rejected
#      Generates a license with yesterday's date as the expiry, runs the
#      binary with that license, and asserts the exit code is non-zero and
#      the output mentions "expired".
#
#   5. test_wrong_machine_license_is_rejected
#      Generates a license locked to a fake machine ID, runs the binary,
#      and asserts the exit code is non-zero and the output mentions "machine".
#
#   6. test_license_signed_with_different_secret_rejected
#      Builds a binary, then generates a license using a DIFFERENT secret,
#      and asserts that the binary refuses to run with that license.

import datetime   # Used to compute yesterday's date for the expired license test.
import json       # Used to read and modify license JSON files in tests.
import os         # Used to read file sizes, copy files, and check existence.
import pathlib    # Used to read the secret file when passing it to _make_license.
import shutil     # Used to copy the binary before tampering with it.
import subprocess # Used to run the binary and the pyshield CLI.
import sys        # Used to find the Python executable and detect the platform.

import pytest     # Provides the mark.e2e decorator and assertion helpers.

# Import the internal signing helper so the expired and wrong-machine license
# tests can produce a validly signed but semantically invalid license without
# needing an extra CLI round-trip.
# NOTE: _sign_payload now requires a 'secret' parameter.
from src.license_manager import _sign_payload, get_machine_id
from src.build_secret import generate_secret   # Used to create a different secret.


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _repo_root() -> str:
    """Return the absolute path to the repository root directory.

    This function computes the path by going one level up from the tests/
    directory where this file lives.

    Returns:
        The absolute path to the repository root.
    """

    # os.path.abspath(__file__) gives the absolute path to this test file.
    # dirname gives the tests/ directory.
    # dirname again gives the repo root.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_license(path: str, secret: bytes, machine_id=None, days=None) -> None:
    """Create a validly signed PyShield license file with custom fields.

    This helper is used by the license tests to produce license files with
    specific properties (expired, wrong machine) that the PyShield CLI cannot
    generate directly (because it would refuse to generate an already-expired
    license).

    The license is signed with the provided secret, so it will pass the HMAC
    check when verified with that same secret.

    Args:
        path: The file path where the license JSON will be written.
        secret: The HMAC secret bytes to sign the license with.  This must
                match the secret embedded in the binary under test.
        machine_id: If provided, this string is stored as the machine_id field.
                    Set to a fake hex string to create a wrong-machine license.
        days: If provided, the expiry date is set this many days from today.
              Pass a negative number (e.g., -1) for an already-expired license.

    Returns:
        None.
    """

    # Build the payload dictionary.
    issued_date = datetime.date.today().isoformat()
    payload = {
        "issued": issued_date,
        "machine_id": machine_id,   # None if not machine-locked.
        "expires": None,            # Filled in below if days is provided.
    }

    # Set the expiry date if requested.
    if days is not None:
        expiry_date = datetime.date.today() + datetime.timedelta(days=days)
        payload["expires"] = expiry_date.isoformat()

    # Sign the payload using the provided HMAC secret.
    # The secret must match the one embedded in the binary so the binary's
    # license_check.validate_license() call will accept this license.
    payload["signature"] = _sign_payload(
        {k: v for k, v in payload.items() if k != "signature"},
        secret,
    )

    # Write the signed license to disk.
    with open(path, "w", encoding="utf-8") as license_file:
        json.dump(payload, license_file, indent=2)


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_obfuscation_hides_proprietary_strings(built_demo):
    """Verify that proprietary strings are not recoverable from the binary.

    This test reads the entire binary as a byte sequence and asserts that
    known proprietary strings do not appear anywhere in it.  After PyArmor
    obfuscation, the source code is encrypted, so plain-text strings from
    the original Python files should not be visible.

    This is the primary test that proves to a VP or client that source code
    is actually hidden — not just "compiled", but encrypted.

    Args:
        built_demo: Session-scoped fixture that provides a tuple of
                    (binary_path, secret_path).
    """

    # Unpack the fixture tuple.  binary_path is the compiled binary; we do not
    # need secret_path in this test because we are not generating a license.
    binary_path, _secret_path = built_demo

    # Read the entire binary as raw bytes.
    # Large binaries are typically 5-15 MB, which fits in memory easily.
    with open(binary_path, "rb") as binary_file:
        binary_data = binary_file.read()

    # Define the strings that must NOT appear in the binary.
    # These come from secret_algorithm.py and represent proprietary IP.
    # The module docstring contains "PROPRIETARY" and "Acme Corp".
    # The numeric constants 0.0234, 0.7891, 2.4567 are the magic weights.
    forbidden_strings = [
        b"PROPRIETARY",    # From the module docstring.
        b"Acme Corp",      # From the copyright notice.
        b"0.0234",         # AGE_WEIGHT constant.
        b"0.7891",         # TICKET_WEIGHT constant.
        b"2.4567",         # BIAS_TERM constant.
        b"AGE_WEIGHT",     # The constant name itself.
        b"TICKET_WEIGHT",  # The constant name itself.
    ]

    # Check each forbidden string.
    for forbidden in forbidden_strings:
        assert forbidden not in binary_data, (
            f"Proprietary string {forbidden!r} was found in the binary at "
            f"{binary_path}. "
            "This means PyArmor obfuscation did not protect this string. "
            "Check that the obfuscation step ran successfully."
        )


@pytest.mark.e2e
def test_protected_binary_runs_correctly(built_demo, tmp_path):
    """Verify that the protected binary produces correct output.

    Runs the binary with a valid machine-locked license and checks that
    the output CSV is byte-for-byte identical to expected_output.csv.
    This proves that protection does not break the application logic.

    Args:
        built_demo: Session-scoped fixture providing (binary_path, secret_path).
        tmp_path: pytest built-in fixture providing a per-test temp directory.
    """

    # Unpack the fixture tuple.
    binary_path, secret_path = built_demo
    repo_root = _repo_root()

    # Generate a valid license locked to this machine with a 10-year expiry.
    # This simulates a real deployment license that should pass all checks.
    # Pass --secret-file so the license is signed with the same key that was
    # embedded in the binary during the build.
    license_path = str(tmp_path / "valid.lic")
    license_result = subprocess.run(
        [
            sys.executable,
            "pyshield.py",
            "license", "generate",
            "--output", license_path,
            "--machine-lock",
            "--days", "3650",     # Ten years — effectively never expires in testing.
            "--secret-file", secret_path,
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
        timeout=30,
    )

    # The license generation must succeed before we can run the binary.
    assert license_result.returncode == 0, (
        f"License generation failed: {license_result.stderr}"
    )

    # Paths to input and expected output files.
    input_csv = os.path.join(repo_root, "examples", "demo_app", "sample_input.csv")
    expected_csv = os.path.join(repo_root, "examples", "demo_app", "expected_output.csv")
    output_csv = str(tmp_path / "actual_output.csv")

    # Run the protected binary with the valid license.
    run_result = subprocess.run(
        [binary_path, "process", input_csv, output_csv, "--license", license_path],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # The binary must exit successfully.
    assert run_result.returncode == 0, (
        f"Protected binary exited with non-zero code {run_result.returncode}. "
        f"stdout: {run_result.stdout}. stderr: {run_result.stderr}"
    )

    # Read both the actual and expected output files as text.
    with open(output_csv, "r", encoding="utf-8") as actual_file:
        actual_content = actual_file.read()

    with open(expected_csv, "r", encoding="utf-8") as expected_file:
        expected_content = expected_file.read()

    # Assert byte-for-byte equality.  This is stronger than checking a few rows —
    # it proves the entire output matches every decimal place exactly.
    # Compute the position of the first difference for a useful failure message.
    first_diff_pos = next(
        (i for i, (a, b) in enumerate(zip(actual_content, expected_content)) if a != b),
        len(expected_content),
    )
    assert actual_content == expected_content, (
        "Protected binary output does not match expected_output.csv. "
        "This means the protection changed the algorithm's behaviour, which "
        "is a critical failure. "
        f"First difference at character {first_diff_pos}."
    )


@pytest.mark.e2e
def test_tamper_detection_rejects_modified_binary(built_demo, tmp_path):
    """Verify that modifying the binary is detected by hash verification.

    This test:
    1. Copies the binary to a temp directory along with its .sha256 sidecar.
    2. Flips one byte in the middle of the binary copy.
    3. Runs "python pyshield.py hash verify" on the tampered copy.
    4. Asserts that the hash verification reports a tamper error.

    The .sha256 sidecar is written by the packager immediately after the build.
    Any change to the binary will cause the hash to mismatch.

    Args:
        built_demo: Session-scoped fixture providing (binary_path, secret_path).
        tmp_path: pytest built-in fixture providing a per-test temp directory.
    """

    # Unpack the fixture tuple.  We do not need secret_path in this test.
    original_binary_path, _secret_path = built_demo
    repo_root = _repo_root()

    # The hash sidecar file is created by src/packager.py next to the binary.
    original_hash_path = original_binary_path + ".sha256"

    # Confirm the sidecar file was created.
    assert os.path.isfile(original_hash_path), (
        f"SHA-256 sidecar file not found: {original_hash_path}. "
        "The packager should have created this file during the build."
    )

    # Copy the binary and sidecar to a temp directory so we can modify them
    # without affecting the session-scoped fixture used by other tests.
    tampered_binary_path = str(tmp_path / os.path.basename(original_binary_path))
    tampered_hash_path = tampered_binary_path + ".sha256"

    shutil.copy2(original_binary_path, tampered_binary_path)
    shutil.copy2(original_hash_path, tampered_hash_path)

    # --- Flip one byte at the midpoint of the binary. ---
    # We use r+b (read-write binary) mode to modify the file in place.
    binary_size = os.path.getsize(tampered_binary_path)
    midpoint_offset = binary_size // 2

    with open(tampered_binary_path, "r+b") as binary_file:
        # Seek to the midpoint.
        binary_file.seek(midpoint_offset)

        # Read one byte.
        original_byte = binary_file.read(1)

        # Seek back to the same position.
        binary_file.seek(midpoint_offset)

        # Write the byte with all bits flipped (XOR with 0xFF).
        flipped_byte = bytes([original_byte[0] ^ 0xFF])
        binary_file.write(flipped_byte)

    # --- Run PyShield hash verify on the tampered binary. ---
    # pyshield.py hash verify reads the sidecar and compares it to the file.
    # Since we flipped a byte, the hash will no longer match.
    verify_result = subprocess.run(
        [
            sys.executable,
            "pyshield.py",
            "hash", "verify",
            "--file", tampered_binary_path,
            "--hash-file", tampered_hash_path,
        ],
        capture_output=True,
        text=True,
        cwd=repo_root,
        timeout=30,
    )

    # The hash verification must exit with a non-zero code.
    assert verify_result.returncode != 0, (
        "Hash verification should have failed for the tampered binary, "
        "but it reported success.  This means tamper detection is broken."
    )

    # The combined stdout + stderr must mention "tamper" or "integrity".
    combined_output = verify_result.stdout + verify_result.stderr
    assert (
        "tamper" in combined_output.lower()
        or "integrity" in combined_output.lower()
    ), (
        f"Expected 'tamper' or 'integrity' in the verification output, "
        f"but got: {combined_output!r}"
    )


@pytest.mark.e2e
def test_expired_license_is_rejected(built_demo, tmp_path):
    """Verify that an expired license is rejected by the binary.

    Generates a license with yesterday as the expiry date, runs the binary
    with that license, and asserts that the exit code is non-zero and the
    output contains the word "expired".

    Args:
        built_demo: Session-scoped fixture providing (binary_path, secret_path).
        tmp_path: pytest built-in fixture providing a per-test temp directory.
    """

    # Unpack the fixture tuple.
    binary_path, secret_path = built_demo
    repo_root = _repo_root()

    # Read the build secret from the secret file so we can sign the license
    # with the same key that was embedded in the binary.
    build_secret = pathlib.Path(secret_path).read_bytes()

    # Create a license that expired yesterday using the _make_license helper.
    # days=-1 means the expiry date is set to yesterday.
    expired_license_path = str(tmp_path / "expired.lic")
    _make_license(expired_license_path, secret=build_secret, days=-1)

    # Provide a real input CSV so the binary gets far enough to check the license.
    input_csv = os.path.join(repo_root, "examples", "demo_app", "sample_input.csv")
    output_csv = str(tmp_path / "should_not_be_created.csv")

    # Run the binary with the expired license.
    run_result = subprocess.run(
        [binary_path, "process", input_csv, output_csv, "--license", expired_license_path],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # The binary must exit with a non-zero code.
    assert run_result.returncode != 0, (
        "Binary accepted an expired license and ran successfully. "
        "License expiry enforcement is broken."
    )

    # The error output must mention "expired".
    combined_output = run_result.stdout + run_result.stderr
    assert "expired" in combined_output.lower(), (
        f"Expected the word 'expired' in the error output, but got: {combined_output!r}"
    )


@pytest.mark.e2e
def test_wrong_machine_license_is_rejected(built_demo, tmp_path):
    """Verify that a license for a different machine is rejected.

    Creates a license locked to a fake machine ID ("a" repeated 64 times),
    runs the binary with that license, and asserts that the exit code is
    non-zero and the output mentions "machine".  It also checks that the
    output includes the actual machine ID, which a support team would use
    to generate the correct license.

    Args:
        built_demo: Session-scoped fixture providing (binary_path, secret_path).
        tmp_path: pytest built-in fixture providing a per-test temp directory.
    """

    # Unpack the fixture tuple.
    binary_path, secret_path = built_demo
    repo_root = _repo_root()

    # Read the build secret from the secret file.
    build_secret = pathlib.Path(secret_path).read_bytes()

    # Create a license locked to a fake machine ID.
    # "a" * 64 is a valid-looking 64-character hex string, but it will not
    # match any real machine.
    fake_machine_id = "a" * 64
    wrong_machine_license_path = str(tmp_path / "wrong_machine.lic")
    _make_license(wrong_machine_license_path, secret=build_secret, machine_id=fake_machine_id)

    # Provide a real input CSV.
    input_csv = os.path.join(repo_root, "examples", "demo_app", "sample_input.csv")
    output_csv = str(tmp_path / "should_not_be_created.csv")

    # Run the binary with the wrong-machine license.
    run_result = subprocess.run(
        [binary_path, "process", input_csv, output_csv, "--license", wrong_machine_license_path],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # The binary must exit with a non-zero code.
    assert run_result.returncode != 0, (
        "Binary accepted a license for a different machine. "
        "Machine-lock enforcement is broken."
    )

    # The error output must mention "machine".
    combined_output = run_result.stdout + run_result.stderr
    assert "machine" in combined_output.lower(), (
        f"Expected the word 'machine' in the error output, but got: {combined_output!r}"
    )

    # The error output should include the actual machine ID so a support team
    # knows what ID to use when generating the correct license.
    actual_machine_id = get_machine_id()
    assert actual_machine_id in combined_output, (
        f"Expected the actual machine ID ({actual_machine_id}) to appear in the "
        f"error output so users know what to send to support, "
        f"but it was not found. Output: {combined_output!r}"
    )


@pytest.mark.e2e
def test_license_signed_with_different_secret_rejected(built_demo, tmp_path):
    """Verify that a license signed with a different secret is rejected.

    This test proves that the per-build secret hardening actually works:
    if someone generates a license using a secret that does not match the
    one embedded in the binary, the binary must refuse to run.

    Steps:
    1. Get the binary built by the built_demo fixture (uses secret A).
    2. Generate a DIFFERENT random secret (secret B).
    3. Create a license signed with secret B.
    4. Run the binary with that license.
    5. Assert the binary rejects the license (exit code non-zero).

    Args:
        built_demo: Session-scoped fixture providing (binary_path, secret_path).
        tmp_path: pytest built-in fixture providing a per-test temp directory.
    """

    # Unpack the fixture tuple.
    binary_path, _secret_path = built_demo
    repo_root = _repo_root()

    # Generate a completely different secret — not the one embedded in the binary.
    # With 32 bytes of entropy, the probability of accidental collision is negligible.
    different_secret = generate_secret()

    # Create a license signed with the different secret.
    # This license will have a valid HMAC signature, but for the wrong key.
    wrong_secret_license_path = str(tmp_path / "wrong_secret.lic")
    _make_license(wrong_secret_license_path, secret=different_secret)

    # Provide a real input CSV so the binary gets far enough to check the license.
    input_csv = os.path.join(repo_root, "examples", "demo_app", "sample_input.csv")
    output_csv = str(tmp_path / "should_not_be_created.csv")

    # Run the binary with the wrong-secret license.
    run_result = subprocess.run(
        [binary_path, "process", input_csv, output_csv, "--license", wrong_secret_license_path],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # The binary must reject the license and exit with a non-zero code.
    assert run_result.returncode != 0, (
        "Binary accepted a license signed with a different secret. "
        "This is a critical failure: it means the per-build secret is not "
        "being verified.  An attacker could forge licenses using any secret."
    )

    # The error output should mention "signature" or "invalid".
    combined_output = run_result.stdout + run_result.stderr
    assert (
        "signature" in combined_output.lower()
        or "invalid" in combined_output.lower()
        or "tamper" in combined_output.lower()
    ), (
        f"Expected 'signature', 'invalid', or 'tamper' in the error output, "
        f"but got: {combined_output!r}"
    )
