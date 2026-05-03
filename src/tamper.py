# src/tamper.py
#
# This module provides SHA-256 hash-based tamper detection for files.
#
# When you produce a protected executable, call compute_hash() to record its
# fingerprint.  Later, call verify_hash() to confirm the file has not been
# modified.  If the hash does not match, verify_hash raises RuntimeError.
#
# SHA-256 is a cryptographic hash function.  Any change to even one byte of
# the file will produce a completely different hash.  This makes it reliable
# for detecting modifications, replacements, or corruption.

import hashlib   # Provides the SHA-256 hash algorithm from the standard library.
import os        # Used to check that files exist before opening them.


def compute_hash(file_path: str) -> str:
    """Compute the SHA-256 hash of a file and write it to a sidecar file.

    The sidecar file is placed in the same directory as the input file and
    has the same name with ".sha256" appended.  For example, if file_path is
    "/dist/app", the sidecar is "/dist/app.sha256".

    Parameters
    ----------
    file_path : str
        Path to the file to hash.

    Returns
    -------
    str
        The absolute path to the sidecar .sha256 file that was written.

    Raises
    ------
    FileNotFoundError
        If file_path does not exist.
    """

    # Resolve to an absolute path for consistent behaviour.
    file_path = os.path.abspath(file_path)

    # Make sure the target file actually exists before we try to read it.
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File to hash does not exist: {file_path}")

    # Create a new SHA-256 hasher object from the standard library.
    hasher = hashlib.sha256()

    # Open the file in binary mode.  We read in 64-kilobyte chunks so that
    # very large files do not have to be loaded into memory all at once.
    with open(file_path, "rb") as file_handle:
        # Keep reading chunks until we reach the end of the file.
        while True:
            # Read one chunk.  chunk will be empty bytes b"" at end-of-file.
            chunk = file_handle.read(65536)

            # An empty chunk means we have reached the end of the file.
            if not chunk:
                break

            # Feed the chunk into the hasher to update the running digest.
            hasher.update(chunk)

    # Get the final hex-encoded hash string, e.g.
    # "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    hex_digest = hasher.hexdigest()

    # Build the path for the sidecar file by appending ".sha256" to the
    # original file path.
    hash_file_path = file_path + ".sha256"

    # Write the hex digest to the sidecar file.  We write only the digest
    # string with no trailing newline to keep the file simple to parse.
    with open(hash_file_path, "w", encoding="utf-8") as hash_file:
        hash_file.write(hex_digest)

    # Return the sidecar path so callers know where the hash was written.
    return hash_file_path


def verify_hash(file_path: str, hash_file_path: str = "") -> bool:
    """Verify that a file's SHA-256 hash matches the value stored in a sidecar.

    Parameters
    ----------
    file_path : str
        Path to the file to verify.
    hash_file_path : str, optional
        Path to the .sha256 sidecar file.  If not supplied, the function looks
        for file_path + ".sha256" (the default location used by compute_hash).

    Returns
    -------
    bool
        True if the hash matches.

    Raises
    ------
    FileNotFoundError
        If file_path or hash_file_path does not exist.
    RuntimeError
        If the computed hash does not match the stored hash, indicating the
        file has been modified since the hash was recorded.
    """

    # Resolve file_path to an absolute path.
    file_path = os.path.abspath(file_path)

    # If no explicit sidecar path was provided, use the default location.
    if not hash_file_path:
        hash_file_path = file_path + ".sha256"

    # Resolve the sidecar path to an absolute path.
    hash_file_path = os.path.abspath(hash_file_path)

    # Confirm the target file exists.
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File to verify does not exist: {file_path}")

    # Confirm the sidecar file exists.
    if not os.path.isfile(hash_file_path):
        raise FileNotFoundError(
            f"Hash sidecar file does not exist: {hash_file_path}"
        )

    # Read the expected hash from the sidecar file.
    # strip() removes any accidental trailing whitespace or newlines.
    with open(hash_file_path, "r", encoding="utf-8") as hash_file:
        expected_hash = hash_file.read().strip()

    # Recompute the current hash of the file using the same algorithm.
    # We call compute_hash to reuse the chunked-reading logic, but we do not
    # want to overwrite the sidecar file here, so we compute the digest
    # directly instead of calling compute_hash.
    hasher = hashlib.sha256()
    with open(file_path, "rb") as file_handle:
        while True:
            chunk = file_handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)

    # Get the freshly computed hex digest.
    actual_hash = hasher.hexdigest()

    # Compare the stored hash with the freshly computed hash.
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"Tamper detected. The file {file_path} has been modified. "
            f"Expected hash {expected_hash} but computed {actual_hash}."
        )

    # The hashes match, so the file is intact.
    return True
