# tests/test_license_manager.py
#
# Unit tests for the src/license_manager.py module.
#
# These tests verify that:
# - generate_license creates a valid JSON license file.
# - verify_license returns True for a freshly generated license.
# - verify_license raises ValueError when the signature has been tampered with.
# - verify_license raises ValueError when the license is machine-locked and
#   the machine ID does not match.
# - verify_license raises ValueError when the license has expired.
# - generate_license records an expiry date when days > 0.
# - generate_license records a machine_id when machine_lock=True.
# - A license signed with secret A is rejected when verified with secret B.
# - load_or_create_secret uses the env var when PYSHIELD_HMAC_KEY is set.
# - The secret file has restrictive permissions (0o600) on POSIX systems.

import datetime     # Used to test expiry date logic.
import json         # Used to read and modify license files in tests.
import os           # Used to manage temp file paths.
import pathlib      # Used to work with secret file paths.
import stat         # Used to inspect file permission bits.
import sys          # Used to skip POSIX-only tests on Windows.
import tempfile     # Used to create temporary directories.

import pytest       # Provides test runner and assertion helpers.

# Import the functions being tested.
from src.license_manager import generate_license, verify_license, get_machine_id
from src.build_secret import (
    load_or_create_secret,    # Tested in the new env-var test.
    generate_secret,          # Used to create test secrets.
    secret_fingerprint,       # Used to verify fingerprint behaviour.
)


@pytest.fixture
def test_secret() -> bytes:
    """Provide a fresh 32-byte HMAC secret for each test.

    Using a fresh secret per test ensures that tests are isolated: a license
    generated in one test cannot accidentally be verified in another.
    The secret is generated with secrets.token_bytes (via generate_secret)
    so it is cryptographically random and reproducibly unique.

    Returns:
        A fresh 32-byte bytes object suitable for use as an HMAC key.
    """
    # generate_secret calls secrets.token_bytes(32) — the standard stdlib
    # function for generating cryptographic key material.
    return generate_secret()


def test_generate_license_creates_file(test_secret):
    """generate_license should create a license file at the specified path."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")

        # Generate a simple license with no machine lock and no expiry.
        # Pass the fixture secret so the test is isolated from other secrets.
        result_path = generate_license(license_path, secret=test_secret)

        # The returned path should match the input path.
        assert result_path == os.path.abspath(license_path), (
            "generate_license should return the absolute path of the license file."
        )

        # The file should actually exist on disk.
        assert os.path.isfile(result_path), (
            "generate_license should create the license file on disk."
        )


def test_generate_license_produces_valid_json(test_secret):
    """generate_license should write a valid JSON object to the file."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, secret=test_secret)

        # Open and parse the license file.
        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # The JSON object must contain the required fields.
        assert "issued" in data, "License file must contain an 'issued' field."
        assert "signature" in data, "License file must contain a 'signature' field."


def test_verify_license_passes_for_fresh_license(test_secret):
    """verify_license should return True for a freshly generated license."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, secret=test_secret)

        # A fresh license should pass verification without raising.
        # We pass the same secret that was used to sign it.
        result = verify_license(license_path, secret=test_secret)
        assert result is True, (
            "verify_license should return True for a valid license."
        )


def test_verify_license_fails_for_tampered_signature(test_secret):
    """verify_license should raise ValueError when the signature is wrong."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, secret=test_secret)

        # Read the license JSON.
        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # Overwrite the signature with garbage.
        data["signature"] = "0" * 64

        # Write the tampered data back.
        with open(license_path, "w", encoding="utf-8") as lf:
            json.dump(data, lf)

        # verify_license should raise ValueError.
        with pytest.raises(ValueError, match="signature"):
            verify_license(license_path, secret=test_secret)


def test_verify_license_fails_for_wrong_machine_id(test_secret):
    """verify_license should raise ValueError when the machine ID does not match."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")

        # Generate a license with a machine ID, but set it to a fake value
        # so it will never match the current machine.
        generate_license(license_path, secret=test_secret)

        # Read the license, inject a fake machine_id, and re-sign it.
        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # Set a machine_id that does not match the current machine.
        data["machine_id"] = "a" * 64   # A fake 64-char hex string.

        # Recompute the signature with the fake machine_id so the signature
        # check passes but the machine check fails.
        # Import _sign_payload here so the import stays close to where it is used.
        from src.license_manager import _sign_payload
        payload_for_signing = {k: v for k, v in data.items() if k != "signature"}
        # Pass the same test_secret so the signature is valid for this secret,
        # but the machine ID is still wrong.
        data["signature"] = _sign_payload(payload_for_signing, test_secret)

        # Write the modified license back to disk.
        with open(license_path, "w", encoding="utf-8") as lf:
            json.dump(data, lf)

        # verify_license should raise ValueError about the machine ID.
        with pytest.raises(ValueError, match="machine"):
            verify_license(license_path, secret=test_secret)


def test_verify_license_fails_for_expired_license(test_secret):
    """verify_license should raise ValueError when the license has expired."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")

        # Generate a license and then manually set the expiry date to yesterday.
        generate_license(license_path, days=365, secret=test_secret)

        # Read the license and set the expiry date to one day in the past.
        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # Compute yesterday's date in ISO 8601 format.
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        data["expires"] = yesterday

        # Recompute the signature so the signature check still passes.
        from src.license_manager import _sign_payload
        payload_for_signing = {k: v for k, v in data.items() if k != "signature"}
        data["signature"] = _sign_payload(payload_for_signing, test_secret)

        # Write the modified license back.
        with open(license_path, "w", encoding="utf-8") as lf:
            json.dump(data, lf)

        # verify_license should raise ValueError about expiry.
        with pytest.raises(ValueError, match="expired"):
            verify_license(license_path, secret=test_secret)


def test_generate_license_with_expiry_sets_expires_field(test_secret):
    """generate_license with days > 0 should set the 'expires' field."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, days=30, secret=test_secret)

        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # The expires field should be a date 30 days from today.
        assert data.get("expires") is not None, (
            "License with days=30 should have a non-null 'expires' field."
        )

        # Parse the expiry date and confirm it is 30 days from today.
        expiry = datetime.date.fromisoformat(data["expires"])
        expected_expiry = datetime.date.today() + datetime.timedelta(days=30)
        assert expiry == expected_expiry, (
            f"Expected expiry {expected_expiry} but got {expiry}."
        )


def test_generate_license_machine_lock_sets_machine_id(test_secret):
    """generate_license with machine_lock=True should set the 'machine_id' field."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, machine_lock=True, secret=test_secret)

        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # The machine_id field should match the current machine's ID.
        stored_machine_id = data.get("machine_id")
        assert stored_machine_id is not None, (
            "License with machine_lock=True should have a non-null 'machine_id'."
        )
        assert stored_machine_id == get_machine_id(), (
            "Stored machine_id should match the current machine's ID."
        )


def test_verify_license_raises_file_not_found(test_secret):
    """verify_license should raise FileNotFoundError for a non-existent file."""

    with pytest.raises(FileNotFoundError):
        verify_license("/tmp/this_file_does_not_exist_pyshield.lic", secret=test_secret)


# ---------------------------------------------------------------------------
# New tests added as part of per-build secret hardening.
# ---------------------------------------------------------------------------

def test_license_signed_with_one_secret_rejected_by_another():
    """A license signed with secret A must be rejected when verified with secret B.

    This test is the core security proof: it shows that the HMAC signature is
    actually keyed to the specific secret, not to some global or guessable value.
    If this test fails, it means the signing and/or verification logic has a bug
    that could allow cross-build license forgery.
    """

    # Generate two independent secrets so we can test cross-secret rejection.
    secret_a = generate_secret()
    secret_b = generate_secret()

    # Make sure the two secrets are different (astronomically unlikely to collide,
    # but we check explicitly to avoid a false pass in a very unlucky test run).
    assert secret_a != secret_b, (
        "generate_secret() returned the same bytes twice. "
        "This should be astronomically unlikely and indicates a bug in the RNG."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")

        # Sign the license with secret A.
        generate_license(license_path, secret=secret_a)

        # Verification with the same key (secret A) must pass.
        assert verify_license(license_path, secret=secret_a) is True, (
            "License signed with secret A should verify successfully with secret A."
        )

        # Verification with a different key (secret B) must fail.
        with pytest.raises(ValueError, match="signature"):
            verify_license(license_path, secret=secret_b)


def test_load_or_create_secret_uses_env_var_when_set(tmp_path, monkeypatch):
    """load_or_create_secret should decode and return the env var value when set.

    This test monkeypatches PYSHIELD_HMAC_KEY to a known value and confirms
    that load_or_create_secret returns the decoded bytes of that value, rather
    than generating a new random secret or reading from the file.  This proves
    that the CI injection path works correctly.

    Args:
        tmp_path: pytest built-in fixture providing a temporary directory.
        monkeypatch: pytest built-in fixture for patching environment variables.
    """

    # Create a known 32-byte secret and encode it as a 64-character hex string.
    known_secret = bytes(range(32))   # Predictable bytes: 0x00, 0x01, ..., 0x1f.
    known_hex = known_secret.hex()    # 64 lowercase hex characters.

    # Patch the environment so PYSHIELD_HMAC_KEY is set to our known hex string.
    # monkeypatch.setenv automatically undoes the change after the test finishes.
    monkeypatch.setenv("PYSHIELD_HMAC_KEY", known_hex)

    # Point the secret_path at a non-existent file inside tmp_path.
    # Since the env var is set, load_or_create_secret should not read this file.
    secret_path = tmp_path / "unused_secret_file"

    # Call load_or_create_secret.  It should return the decoded env var.
    result = load_or_create_secret(secret_path)

    # The returned bytes must exactly match our known secret.
    assert result == known_secret, (
        "load_or_create_secret should return the decoded env var bytes "
        "when PYSHIELD_HMAC_KEY is set.  "
        f"Expected {known_secret.hex()!r}, got {result.hex()!r}."
    )

    # The file should NOT have been created because the env var took precedence.
    assert not secret_path.exists(), (
        "load_or_create_secret must not write a secret file when the env var is set."
    )


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX file permissions (0o600) are not enforced on Windows.",
)
def test_secret_file_has_restrictive_permissions(tmp_path):
    """The secret file must be created with mode 0o600 on POSIX systems.

    Mode 0o600 means "owner read + owner write only".  Group and world have no
    access.  This prevents other users on a shared machine from reading the key.

    This test is skipped on Windows because the os.chmod call there only sets
    the read-only flag and does not implement POSIX permission semantics.

    Args:
        tmp_path: pytest built-in fixture providing a temporary directory.
    """

    # Use a path that does not yet exist so load_or_create_secret will create it.
    secret_path = tmp_path / ".pyshield_secret"

    # Ensure PYSHIELD_HMAC_KEY is not set so we go through the file-creation path.
    # We use os.environ.pop to remove it if present, and restore it afterwards.
    env_backup = os.environ.pop("PYSHIELD_HMAC_KEY", None)
    try:
        # Call load_or_create_secret with no env var and no existing file.
        # This should create the file with mode 0o600.
        load_or_create_secret(secret_path)
    finally:
        # Restore the environment variable if it was set before this test.
        if env_backup is not None:
            os.environ["PYSHIELD_HMAC_KEY"] = env_backup

    # Confirm the file was created.
    assert secret_path.exists(), (
        "load_or_create_secret should have created the secret file."
    )

    # Read the file's permission bits using os.stat.
    file_stat = secret_path.stat()

    # st_mode contains all permission bits plus the file-type bits.
    # Masking with 0o777 isolates just the permission bits (owner/group/world).
    actual_mode = file_stat.st_mode & 0o777

    assert actual_mode == 0o600, (
        f"Secret file must have mode 0o600 (owner read+write only) on POSIX, "
        f"but found mode 0o{actual_mode:03o}.  "
        "Check that load_or_create_secret calls os.chmod with 0o600."
    )


def test_secret_fingerprint_returns_8_chars():
    """secret_fingerprint should return exactly 8 lowercase hex characters."""

    secret = generate_secret()
    fingerprint = secret_fingerprint(secret)

    # Must be exactly 8 characters long.
    assert len(fingerprint) == 8, (
        f"Fingerprint must be 8 characters, got {len(fingerprint)}: {fingerprint!r}"
    )

    # Must be a valid hex string (all characters in 0-9 and a-f).
    assert all(c in "0123456789abcdef" for c in fingerprint), (
        f"Fingerprint must be lowercase hex, got: {fingerprint!r}"
    )


def test_generate_license_raises_without_secret():
    """generate_license should raise ValueError when secret is None."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        with pytest.raises(ValueError, match="secret"):
            # Omit the secret parameter entirely (defaults to None).
            generate_license(license_path)


def test_verify_license_raises_without_secret(test_secret):
    """verify_license should raise ValueError when secret is None."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, secret=test_secret)
        with pytest.raises(ValueError, match="secret"):
            # Call verify_license without passing a secret.
            verify_license(license_path)
