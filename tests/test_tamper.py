# tests/test_tamper.py
#
# Unit tests for the src/tamper.py module.
#
# These tests verify that:
# - compute_hash writes the correct SHA-256 hash to a sidecar file.
# - verify_hash passes when the file is unmodified.
# - verify_hash raises RuntimeError when the file has been modified.
# - verify_hash raises FileNotFoundError when the target file is missing.
# - verify_hash raises FileNotFoundError when the sidecar file is missing.

import hashlib      # Used to compute expected hashes independently in tests.
import os           # Used to modify files and paths during tests.
import tempfile     # Used to create temporary files and directories.

import pytest       # Provides test runner and assertion helpers.

# Import the functions being tested.
from src.tamper import compute_hash, verify_hash


def test_compute_hash_writes_correct_digest():
    """compute_hash should write the correct SHA-256 hex digest to a sidecar file."""

    # Create a temporary directory to hold test files.
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write a small test file with known content.
        test_file = os.path.join(tmpdir, "example.bin")
        test_content = b"hello pyshield"
        with open(test_file, "wb") as f:
            f.write(test_content)

        # Compute the expected hash independently using hashlib directly.
        expected_hash = hashlib.sha256(test_content).hexdigest()

        # Call compute_hash and get the path to the sidecar file.
        sidecar_path = compute_hash(test_file)

        # Verify the sidecar file was created next to the test file.
        assert os.path.isfile(sidecar_path), (
            "compute_hash should create a sidecar .sha256 file."
        )

        # Verify the sidecar file has the correct name.
        assert sidecar_path == test_file + ".sha256", (
            "The sidecar file should be named by appending .sha256 to the input path."
        )

        # Read the hash written to the sidecar file.
        with open(sidecar_path, "r", encoding="utf-8") as sf:
            written_hash = sf.read().strip()

        # Confirm the written hash matches the expected hash.
        assert written_hash == expected_hash, (
            f"Expected hash {expected_hash} but sidecar contains {written_hash}."
        )


def test_verify_hash_passes_for_unmodified_file():
    """verify_hash should return True when the file has not been modified."""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file.
        test_file = os.path.join(tmpdir, "clean.bin")
        with open(test_file, "wb") as f:
            f.write(b"original content")

        # Record the hash.
        compute_hash(test_file)

        # Verify the unmodified file.
        result = verify_hash(test_file)

        # The function should return True without raising.
        assert result is True, (
            "verify_hash should return True for an unmodified file."
        )


def test_verify_hash_raises_for_modified_file():
    """verify_hash should raise RuntimeError when the file has been modified."""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file and record its hash.
        test_file = os.path.join(tmpdir, "modified.bin")
        with open(test_file, "wb") as f:
            f.write(b"original content")
        compute_hash(test_file)

        # Modify the file after recording the hash.
        with open(test_file, "wb") as f:
            f.write(b"tampered content")

        # verify_hash should detect the change and raise RuntimeError.
        with pytest.raises(RuntimeError, match="Tamper detected"):
            verify_hash(test_file)


def test_verify_hash_raises_when_target_file_missing():
    """verify_hash should raise FileNotFoundError if the target file is missing."""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a hash sidecar file manually without a corresponding target.
        missing_file = os.path.join(tmpdir, "ghost.bin")
        sidecar_path = missing_file + ".sha256"
        with open(sidecar_path, "w", encoding="utf-8") as sf:
            sf.write("a" * 64)   # Write a fake hash string.

        # Calling verify_hash on a non-existent file should raise FileNotFoundError.
        with pytest.raises(FileNotFoundError):
            verify_hash(missing_file, sidecar_path)


def test_verify_hash_raises_when_sidecar_missing():
    """verify_hash should raise FileNotFoundError if the sidecar file is missing."""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the target file but not the sidecar.
        test_file = os.path.join(tmpdir, "nosidecar.bin")
        with open(test_file, "wb") as f:
            f.write(b"some content")

        # There is no sidecar file, so verify_hash should raise FileNotFoundError.
        with pytest.raises(FileNotFoundError):
            verify_hash(test_file)


def test_compute_hash_raises_for_missing_file():
    """compute_hash should raise FileNotFoundError if the input file does not exist."""

    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent = os.path.join(tmpdir, "does_not_exist.bin")

        # Expect a FileNotFoundError because the file does not exist.
        with pytest.raises(FileNotFoundError):
            compute_hash(nonexistent)
