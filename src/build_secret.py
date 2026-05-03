# src/build_secret.py
#
# This module manages the per-build HMAC secret that PyShield uses to sign
# and verify license files.
#
# Background: PyShield previously shipped with a single, fixed HMAC key baked
# into the source code.  That key was publicly visible, meaning anyone who
# read the source could forge an unlimited number of valid licenses.
#
# The fix is to generate a fresh 32-byte secret on every "pyshield build"
# invocation and embed that secret into the obfuscated binary.  Because each
# build gets its own secret, an attacker who reverse-engineers one customer's
# binary can only forge licenses for that specific build — not for any other
# customer.  This limits the "blast radius" of a single compromise.
#
# Where the secret lives:
#   - On disk:    <output_dir>/.pyshield_secret  (raw bytes, mode 0o600 on POSIX)
#   - In CI:      PYSHIELD_HMAC_KEY environment variable (64 hex chars)
#   - In binary:  _pyshield_runtime_constants.py (obfuscated by PyArmor)
#
# IMPORTANT: Never log the actual secret.  Every log statement in this file
# and in the CLI uses secret_fingerprint() — the first 8 hex chars of
# SHA-256(secret).  The fingerprint cannot be reversed to recover the secret,
# so it is safe to include in build logs.

import hashlib    # Used to compute the SHA-256 fingerprint of the secret.
import os         # Used to read the PYSHIELD_HMAC_KEY environment variable.
import pathlib    # Used to represent and manipulate file paths.
import secrets    # Used to generate cryptographically secure random bytes.


def generate_secret() -> bytes:
    """Generate a new 32-byte HMAC secret.

    Uses the operating system's cryptographically secure random number
    generator via the stdlib secrets module.  On Linux and macOS this reads
    from /dev/urandom; on Windows it reads from CryptGenRandom.  Both sources
    are suitable for cryptographic key material.

    This function should be called once per build to create a secret that is
    unique to that build.  Using a fresh secret per build ensures that an
    attacker who extracts the secret from one customer's binary cannot use it
    to forge licenses for any other customer.

    Returns:
        A bytes object of length 32 containing cryptographically random data.
    """

    # secrets.token_bytes is the stdlib function recommended for generating
    # key material.  Passing 32 gives us 32 bytes = 256 bits of entropy,
    # which is the same key length as AES-256 and is widely considered
    # sufficient for HMAC-SHA256.
    return secrets.token_bytes(32)


def load_or_create_secret(
    secret_path: pathlib.Path,
    env_var: str = "PYSHIELD_HMAC_KEY",
) -> bytes:
    """Load the HMAC secret from an environment variable or file, creating it
    if neither source exists.

    Resolution order (each step is tried in sequence; the first match wins):

    Step 1: If the environment variable named by env_var is set and contains
            a valid 64-character hex string, decode it and return the bytes.
            This allows CI systems and customer build pipelines to inject a
            stable per-customer key without touching the filesystem.

    Step 2: If secret_path exists on disk, read it and return its raw bytes.
            This covers the case where a previous build already created the
            secret file, so we reuse the same key across rebuilds.

    Step 3: Generate a fresh 32-byte secret, write it to secret_path with
            restrictive permissions (0o600 on POSIX, meaning only the file
            owner can read or write it), and return the bytes.

    Args:
        secret_path: The filesystem path where the secret file should be
                     read from or written to.  This should be inside the
                     build output directory and listed in .gitignore so it
                     is never accidentally committed to the repository.
        env_var: The name of the environment variable to check first.
                 Defaults to "PYSHIELD_HMAC_KEY".

    Returns:
        A bytes object of length 32 containing the HMAC secret.

    Raises:
        ValueError: If the environment variable is set but is not a valid
                    64-character hex string.  The message explains how to
                    generate a valid value so the caller can fix the config.
    """

    # -------------------------------------------------------------------------
    # Step 1 of 3: Check the environment variable.
    # -------------------------------------------------------------------------
    # Reading from an environment variable lets CI pipelines inject a stable
    # key without writing files.  The variable must be exactly 64 lowercase
    # hex characters, which encodes the 32 bytes of the secret.
    env_value = os.environ.get(env_var)
    if env_value is not None:
        # The environment variable is set.  Validate its length first.
        if len(env_value) == 64:
            try:
                # Attempt to decode the 64 hex characters to 32 bytes.
                # bytes.fromhex raises ValueError if any character is not
                # a valid hex digit (0-9, a-f, A-F).
                return bytes.fromhex(env_value)
            except ValueError:
                # The value was 64 characters long but contained non-hex
                # characters.  Fall through to raise the descriptive error.
                pass

        # If we reach here, the variable was set but not valid.
        # Raise a descriptive error so the user can fix their configuration.
        # We include the actual length so the user can spot simple mistakes
        # like accidentally base64-encoding the key instead of hex-encoding it.
        raise ValueError(
            f"Environment variable {env_var} is set but is not a valid "
            f"64-character hex string. "
            f"Got {len(env_value)} character(s). "
            "A valid value is 64 lowercase hex digits (0-9 and a-f). "
            "To generate a valid value, run: "
            "python -c \"import secrets; print(secrets.token_bytes(32).hex())\""
        )

    # -------------------------------------------------------------------------
    # Step 2 of 3: Check whether the secret file already exists on disk.
    # -------------------------------------------------------------------------
    # If the output directory already has a .pyshield_secret file from a
    # previous build, we reuse it so that old licenses remain valid.
    if secret_path.exists():
        # Read the raw bytes from the secret file and return them.
        # The file was written as raw bytes (not hex or base64), so we read
        # it as raw bytes too.
        return secret_path.read_bytes()

    # -------------------------------------------------------------------------
    # Step 3 of 3: Generate a fresh secret and write it to disk.
    # -------------------------------------------------------------------------
    # This is the first build in this output directory.  Create a new 32-byte
    # secret and persist it so that the license-generation step can find it.
    new_secret = generate_secret()

    # Ensure the parent directory of the secret file exists.
    # parents=True creates any missing intermediate directories.
    # exist_ok=True is a no-op if the directory already exists.
    secret_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the secret to the file as raw bytes.
    # We do not encode as hex or base64 here because raw bytes is the most
    # compact and unambiguous representation for binary key material.
    # This intentionally stores the secret on disk with restricted permissions —
    # that is the designed behaviour so "pyshield license generate" can find it.
    secret_path.write_bytes(new_secret)  # lgtm[py/clear-text-storage-sensitive-data]

    # On POSIX systems (Linux, macOS), set file permissions to owner-only
    # read/write (no group or world access).
    # This prevents other users on the same shared machine from reading the key.
    # On Windows, os.chmod has no meaningful effect (Windows uses ACLs, not
    # POSIX permission bits), so we only call it on POSIX.
    if os.name == "posix":
        os.chmod(secret_path, 0o600)

    return new_secret


def secret_fingerprint(secret: bytes) -> str:
    """Compute a short, safe fingerprint of the HMAC secret for logging.

    Returns the first 8 characters of the hexadecimal SHA-256 digest of the
    secret.  This fingerprint is safe to include in build logs because SHA-256
    is a cryptographic one-way function: the fingerprint cannot be reversed
    to recover the original 32-byte secret.

    Always use this function when you need to log or display something about
    the active secret.  Never log or print the secret bytes themselves.
    Never log the full 64-character hex digest either — the 8-character prefix
    is enough to identify a build in a log without revealing useful key material.

    Args:
        secret: The HMAC secret bytes to fingerprint.  Expected to be 32 bytes,
                but the function accepts any non-empty bytes object.

    Returns:
        An 8-character lowercase hexadecimal string.
        For example: "a3f9c1e2".
    """

    # Compute the SHA-256 hash of the secret bytes.
    # hexdigest() returns the hash as a 64-character lowercase hex string.
    full_hex = hashlib.sha256(secret).hexdigest()

    # Return only the first 8 characters.
    # 8 hex digits represent 4 bytes = 32 bits of output, giving over
    # 4 billion possible values.  That is enough to identify a build in a
    # log without giving an attacker any meaningful information about the key.
    return full_hex[:8]
