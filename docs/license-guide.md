# docs/license-guide.md

This document explains how PyShield's license system works. It is written in plain prose for screen-reader accessibility.

## What a PyShield License Is

A PyShield license is a JSON text file. It contains four fields:

- issued: The date the license was created, in ISO 8601 format (YYYY-MM-DD).
- machine_id: A SHA-256 hash of the hardware identifiers of the machine the license is bound to, or null if the license is not machine-locked.
- expires: The date the license expires in ISO 8601 format, or null if the license does not expire.
- signature: An HMAC-SHA256 signature that proves the other three fields have not been changed since the license was generated.

## Generating a License

To generate a license file, run:

```
python pyshield.py license generate --output product.lic
```

This creates a license that is not machine-locked and does not expire.

To machine-lock the license, add the --machine-lock flag:

```
python pyshield.py license generate --machine-lock --output product.lic
```

To set an expiry date, use the --days flag:

```
python pyshield.py license generate --days 365 --output product.lic
```

You can combine both options:

```
python pyshield.py license generate --machine-lock --days 90 --output product.lic
```

## What the Machine ID Is

The machine ID is a SHA-256 hash of three hardware values: the MAC address of the first network interface, the number of logical CPU cores, and the total size of the first disk. The hash means the raw hardware values are never stored in the license file. The same hardware produces the same hash on every boot.

## Verifying a License

To verify a license from the command line, run:

```
python pyshield.py license verify --license product.lic
```

To verify a license from within a Python application, call verify_license:

```python
from src.license_manager import verify_license

try:
    verify_license("product.lic")
    print("License is valid. Starting application.")
except (FileNotFoundError, ValueError) as error:
    print(f"License check failed: {error}")
    raise SystemExit(1)
```

## Security Notes

The HMAC secret key used to sign licenses is stored in src/license_manager.py. In the open-source version it is a fixed string. In a production deployment you should replace this with a key that is unique per customer or per product. The key must be embedded in the protected application (which is itself obfuscated) to make extraction difficult.

The HMAC protects the license file from modification but does not encrypt it. The dates and machine ID are visible in plain text. If you need to hide those values, you can encrypt the license file before distribution using the cryptography library. PyShield does not currently implement license encryption; this is a potential future enhancement.
