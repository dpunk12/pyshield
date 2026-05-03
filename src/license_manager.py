# src/license_manager.py
#
# This module generates and verifies software license files.
#
# A license is a JSON document that records:
#   - The date it was created.
#   - The expiry date (optional).
#   - The machine ID it is locked to (optional).
#   - An HMAC-SHA256 signature that proves the file has not been tampered with.
#
# The machine ID is a SHA-256 hash of hardware identifiers collected by psutil:
# the MAC address, CPU count, and disk serial information.  Hashing means we
# never store raw hardware identifiers in the license file.
#
# The HMAC secret key is the string "pyshield-license-key".  In a production
# deployment you would replace this with a per-customer key generated during
# the sales process and embedded in the protected application.  For the open
# source version, a fixed well-known key is used so the verification logic can
# be demonstrated without key management infrastructure.

import datetime   # Used to compute expiry dates and check them at verification.
import hashlib    # Provides SHA-256 and HMAC for hashing and signing.
import hmac       # Provides the HMAC signing function.
import json       # Licenses are stored as JSON text files.
import os         # Used to resolve file paths.
import uuid       # Used to read the hardware MAC address.

import psutil     # Used to read CPU and disk information for the machine ID.

# The HMAC secret key used to sign and verify license files.
# In a production system, replace this with a securely generated per-customer
# key.  Keep this value private in your deployment.
_LICENSE_HMAC_KEY = b"pyshield-license-key"


def get_machine_id() -> str:
    """Compute a stable machine identifier from hardware characteristics.

    Reads the MAC address of the first network interface, the number of CPU
    cores, and the total size of the first physical disk.  Concatenates these
    values and returns their SHA-256 hex digest.

    The result is stable across reboots on the same hardware.  It changes if
    the user replaces a network card, adds or removes CPU cores (rare), or
    replaces the primary disk.

    Returns
    -------
    str
        A 64-character hexadecimal SHA-256 digest that uniquely identifies
        this machine.
    """

    # Get the MAC address as a 48-bit integer, then convert to a string.
    # uuid.getnode() reads the MAC address from the operating system.
    mac_address = str(uuid.getnode())

    # Get the number of logical CPU cores as a string.
    # psutil.cpu_count() returns an integer like 8 or 16.
    cpu_count = str(psutil.cpu_count(logical=True))

    # Get the total size of the first disk partition in bytes as a string.
    # psutil.disk_partitions() returns a list of mounted partitions.
    # We use the first partition as a stable reference point.
    try:
        # Get the list of disk partitions.
        partitions = psutil.disk_partitions()

        # Take the mountpoint of the first partition.
        first_mountpoint = partitions[0].mountpoint if partitions else "unknown"

        # Get disk usage statistics for that mountpoint.
        disk_usage = psutil.disk_usage(first_mountpoint)

        # Use the total disk size as part of the identity string.
        disk_total = str(disk_usage.total)

    except Exception:
        # If disk information cannot be read, use "unknown" as the placeholder.
        disk_total = "unknown"

    # Concatenate the hardware values with pipe separators.
    hardware_string = f"{mac_address}|{cpu_count}|{disk_total}"

    # Hash the hardware string with SHA-256 and return the hex digest.
    machine_id = hashlib.sha256(hardware_string.encode("utf-8")).hexdigest()

    return machine_id


def _sign_payload(payload: dict) -> str:
    """Compute an HMAC-SHA256 signature for a license payload dictionary.

    The payload is serialised to a compact JSON string with sorted keys so
    that the signature is deterministic regardless of key insertion order.

    Parameters
    ----------
    payload : dict
        The license data dictionary (without the "signature" key).

    Returns
    -------
    str
        The hexadecimal HMAC-SHA256 digest.
    """

    # Serialise the payload to a compact JSON string with sorted keys.
    # sort_keys=True ensures the same dictionary always produces the same string.
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

    # Compute the HMAC using SHA-256 and the module-level secret key.
    signature = hmac.new(_LICENSE_HMAC_KEY, payload_bytes, hashlib.sha256)

    # Return the hex digest as a string.
    return signature.hexdigest()


def generate_license(
    output_path: str,
    machine_lock: bool = False,
    days: int = 0,
) -> str:
    """Generate a signed license file and write it to disk.

    Parameters
    ----------
    output_path : str
        Path where the license file will be written.
    machine_lock : bool, optional
        If True, record the current machine's hardware ID in the license so
        that it will only validate on this machine.  Defaults to False.
    days : int, optional
        Number of days from today until the license expires.  If 0 or
        negative, the license does not expire.  Defaults to 0.

    Returns
    -------
    str
        The absolute path to the written license file.
    """

    # Resolve the output path to an absolute path.
    output_path = os.path.abspath(output_path)

    # Record today's date in ISO 8601 format (YYYY-MM-DD).
    issued_date = datetime.date.today().isoformat()

    # Build the license payload dictionary.
    # This dict will be serialised to JSON and signed.
    payload = {
        "issued": issued_date,
        "machine_id": None,   # Will be filled in below if machine_lock is True.
        "expires": None,      # Will be filled in below if days > 0.
    }

    # If machine locking is requested, compute and store the machine ID.
    if machine_lock:
        payload["machine_id"] = get_machine_id()

    # If an expiry duration was requested, compute the expiry date.
    if days and days > 0:
        # Add the requested number of days to today's date.
        expiry_date = datetime.date.today() + datetime.timedelta(days=days)

        # Store the expiry date as an ISO 8601 string.
        payload["expires"] = expiry_date.isoformat()

    # Sign the payload and add the signature to the document.
    payload["signature"] = _sign_payload(
        # Sign only the data fields, not the signature field itself.
        {k: v for k, v in payload.items() if k != "signature"}
    )

    # Ensure the parent directory of the output file exists.
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Write the license document as indented JSON so it is human-readable
    # (and screen-reader readable) if someone opens the file in a text editor.
    with open(output_path, "w", encoding="utf-8") as license_file:
        json.dump(payload, license_file, indent=2)

    return output_path


def verify_license(license_path: str) -> bool:
    """Verify a license file and return True if it is valid.

    Checks:
    1. The file exists and is valid JSON.
    2. The HMAC signature matches the payload.
    3. If a machine_id is present, it matches the current machine.
    4. If an expiry date is present, today's date is before the expiry.

    Parameters
    ----------
    license_path : str
        Path to the license file to verify.

    Returns
    -------
    bool
        True if the license passes all checks.

    Raises
    ------
    FileNotFoundError
        If the license file does not exist.
    ValueError
        If the signature check fails, the machine ID does not match, or the
        license has expired.
    """

    # Resolve the path to an absolute path.
    license_path = os.path.abspath(license_path)

    # Confirm the license file exists.
    if not os.path.isfile(license_path):
        raise FileNotFoundError(
            f"License file does not exist: {license_path}"
        )

    # Read and parse the JSON content of the license file.
    with open(license_path, "r", encoding="utf-8") as license_file:
        try:
            license_data = json.load(license_file)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"License file is not valid JSON: {license_path}"
            ) from exc

    # Extract the stored signature from the license document.
    stored_signature = license_data.get("signature")

    # Build the payload dict without the signature key, then re-sign it.
    payload_without_sig = {
        k: v for k, v in license_data.items() if k != "signature"
    }
    expected_signature = _sign_payload(payload_without_sig)

    # Compare the stored signature with the freshly computed one.
    # hmac.compare_digest is used instead of "==" to prevent timing attacks.
    if not hmac.compare_digest(str(stored_signature), expected_signature):
        raise ValueError(
            "License signature is invalid. The license file may have been tampered with."
        )

    # If the license records a machine ID, verify it matches this machine.
    stored_machine_id = license_data.get("machine_id")
    if stored_machine_id is not None:
        current_machine_id = get_machine_id()
        if stored_machine_id != current_machine_id:
            raise ValueError(
                "License is locked to a different machine and cannot be used here."
            )

    # If the license records an expiry date, verify it has not passed.
    expires_str = license_data.get("expires")
    if expires_str is not None:
        # Parse the ISO 8601 expiry date string into a date object.
        try:
            expiry_date = datetime.date.fromisoformat(expires_str)
        except ValueError as exc:
            raise ValueError(
                f"License contains an invalid expiry date format: {expires_str}"
            ) from exc

        # Compare the expiry date with today.
        if datetime.date.today() > expiry_date:
            raise ValueError(
                f"License expired on {expires_str}."
            )

    # All checks passed.
    return True
