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

import datetime     # Used to test expiry date logic.
import json         # Used to read and modify license files in tests.
import os           # Used to manage temp file paths.
import tempfile     # Used to create temporary directories.

import pytest       # Provides test runner and assertion helpers.

# Import the functions being tested.
from src.license_manager import generate_license, verify_license, get_machine_id


def test_generate_license_creates_file():
    """generate_license should create a license file at the specified path."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")

        # Generate a simple license with no machine lock and no expiry.
        result_path = generate_license(license_path)

        # The returned path should match the input path.
        assert result_path == os.path.abspath(license_path), (
            "generate_license should return the absolute path of the license file."
        )

        # The file should actually exist on disk.
        assert os.path.isfile(result_path), (
            "generate_license should create the license file on disk."
        )


def test_generate_license_produces_valid_json():
    """generate_license should write a valid JSON object to the file."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path)

        # Open and parse the license file.
        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # The JSON object must contain the required fields.
        assert "issued" in data, "License file must contain an 'issued' field."
        assert "signature" in data, "License file must contain a 'signature' field."


def test_verify_license_passes_for_fresh_license():
    """verify_license should return True for a freshly generated license."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path)

        # A fresh license should pass verification without raising.
        result = verify_license(license_path)
        assert result is True, (
            "verify_license should return True for a valid license."
        )


def test_verify_license_fails_for_tampered_signature():
    """verify_license should raise ValueError when the signature is wrong."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path)

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
            verify_license(license_path)


def test_verify_license_fails_for_wrong_machine_id():
    """verify_license should raise ValueError when the machine ID does not match."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")

        # Generate a license with a machine ID, but set it to a fake value
        # so it will never match the current machine.
        generate_license(license_path)

        # Read the license, inject a fake machine_id, and re-sign it.
        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # Set a machine_id that does not match the current machine.
        data["machine_id"] = "a" * 64   # A fake 64-char hex string.

        # Recompute the signature with the fake machine_id so the signature
        # check passes but the machine check fails.
        from src.license_manager import _sign_payload
        payload_for_signing = {k: v for k, v in data.items() if k != "signature"}
        data["signature"] = _sign_payload(payload_for_signing)

        # Write the modified license back to disk.
        with open(license_path, "w", encoding="utf-8") as lf:
            json.dump(data, lf)

        # verify_license should raise ValueError about the machine ID.
        with pytest.raises(ValueError, match="machine"):
            verify_license(license_path)


def test_verify_license_fails_for_expired_license():
    """verify_license should raise ValueError when the license has expired."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")

        # Generate a license and then manually set the expiry date to yesterday.
        generate_license(license_path, days=365)

        # Read the license and set the expiry date to one day in the past.
        with open(license_path, "r", encoding="utf-8") as lf:
            data = json.load(lf)

        # Compute yesterday's date in ISO 8601 format.
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        data["expires"] = yesterday

        # Recompute the signature so the signature check still passes.
        from src.license_manager import _sign_payload
        payload_for_signing = {k: v for k, v in data.items() if k != "signature"}
        data["signature"] = _sign_payload(payload_for_signing)

        # Write the modified license back.
        with open(license_path, "w", encoding="utf-8") as lf:
            json.dump(data, lf)

        # verify_license should raise ValueError about expiry.
        with pytest.raises(ValueError, match="expired"):
            verify_license(license_path)


def test_generate_license_with_expiry_sets_expires_field():
    """generate_license with days > 0 should set the 'expires' field."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, days=30)

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


def test_generate_license_machine_lock_sets_machine_id():
    """generate_license with machine_lock=True should set the 'machine_id' field."""

    with tempfile.TemporaryDirectory() as tmpdir:
        license_path = os.path.join(tmpdir, "test.lic")
        generate_license(license_path, machine_lock=True)

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


def test_verify_license_raises_file_not_found():
    """verify_license should raise FileNotFoundError for a non-existent file."""

    with pytest.raises(FileNotFoundError):
        verify_license("/tmp/this_file_does_not_exist_pyshield.lic")
