# tests/test_obfuscator.py
#
# Unit tests for the src/obfuscator.py module.
#
# Because PyArmor is an external tool that may not be installed in the test
# environment, these tests only verify the pre-call validation logic (that
# FileNotFoundError is raised for a missing source directory).  The actual
# subprocess call to PyArmor is tested in integration tests run only when
# PyArmor is confirmed to be installed.

import os           # Used to build test paths.
import tempfile     # Used to create temporary directories.

import pytest       # Provides test runner and assertion helpers.

from src.obfuscator import obfuscate


def test_obfuscate_raises_for_missing_source_directory():
    """obfuscate should raise FileNotFoundError when source_dir does not exist."""

    with tempfile.TemporaryDirectory() as tmpdir:
        # The source directory does not exist.
        missing_source = os.path.join(tmpdir, "does_not_exist")
        output_dir = os.path.join(tmpdir, "output")

        with pytest.raises(FileNotFoundError, match="Source directory does not exist"):
            obfuscate(missing_source, output_dir)


def test_obfuscate_creates_output_directory_if_missing():
    """obfuscate should create the output directory even if it does not exist yet.

    This test patches subprocess.run to avoid actually calling PyArmor, which
    may not be installed in the test environment.
    """

    import unittest.mock as mock   # Standard library mock utility.

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a real source directory.
        source_dir = os.path.join(tmpdir, "source")
        os.makedirs(source_dir)

        # Choose an output directory that does not yet exist.
        output_dir = os.path.join(tmpdir, "output", "nested")

        # Mock subprocess.run to prevent an actual PyArmor call.
        # CompletedProcess is the object returned by subprocess.run on success.
        import subprocess
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        with mock.patch("subprocess.run", return_value=mock_result):
            # Call obfuscate with the mocked subprocess.
            returned_path = obfuscate(source_dir, output_dir)

        # The output directory should now exist.
        assert os.path.isdir(output_dir), (
            "obfuscate should create the output directory."
        )

        # The returned path should be the absolute path to the output directory.
        assert returned_path == os.path.abspath(output_dir), (
            "obfuscate should return the absolute path to the output directory."
        )
