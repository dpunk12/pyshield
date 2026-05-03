# Secrets and HMAC Keys in PyShield

This document explains how PyShield manages the HMAC secret used to sign and verify license files. It is written for developers who integrate PyShield into a build pipeline and for operations teams who need to rotate secrets or configure CI.

## Where the build secret lives

When you run "pyshield build", a 32-byte cryptographically random secret is generated and written to a file called .pyshield_secret in your build output directory. The conventional location is dist/.pyshield_secret.

On Linux and macOS, this file is created with mode 0o600, meaning only the file owner can read or write it. On Windows the file is created without special access controls, so you should store it in a directory that is access-controlled at the OS level.

The secret is also embedded into the protected binary at build time. PyShield writes a small Python module called _pyshield_runtime_constants.py into the source tree just before PyArmor runs, then deletes it after obfuscation completes. The obfuscated binary contains the key in encrypted form; the plaintext source file is never distributed.

## Why the secret must not be committed

If .pyshield_secret is committed to a repository, anyone who reads the repository can extract the key and use it to generate unlimited valid licenses for any binary built with that key. The .gitignore file already lists this path, so Git will not track it unless you explicitly force-add it.

Do not commit .pyshield_secret. Do not include it in a container image. Do not log its contents. If you need to check that the right key was used, print or log the fingerprint: the first 8 hex characters of SHA-256 of the secret. The fingerprint cannot be reversed to recover the key.

## How to inject a stable secret via CI

In a continuous integration environment, you often want a stable key so that licenses issued by one build remain valid after a rebuild. To supply a stable key without touching the filesystem, set the PYSHIELD_HMAC_KEY environment variable to a 64-character lowercase hex string before running the build.

To generate a suitable value, run this once:

```
python -c "import secrets; print(secrets.token_bytes(32).hex())"
```

Copy the output, store it as a GitHub Actions repository secret named PYSHIELD_HMAC_KEY, and add the following to your workflow's env block:

```
env:
  PYSHIELD_HMAC_KEY: ${{ secrets.PYSHIELD_HMAC_KEY || '0000000000000000000000000000000000000000000000000000000000000000' }}
```

The fallback value (64 zeros) is the publicly-documented test key used in the PyShield CI workflow when the repository secret is not available (for example, on fork pull requests). It is NOT safe for production use; it is documented here so that everyone who reads the workflow understands it.

When PYSHIELD_HMAC_KEY is set, "pyshield build" uses that key instead of generating a new one. "pyshield license generate" and "pyshield license verify" also read from PYSHIELD_HMAC_KEY before looking for a secret file.

## How to rotate a secret

Rotating a secret means generating a new key, rebuilding all protected binaries with that key, and reissuing all licenses signed with the new key. Licenses signed with the old key will not work with a binary built with the new key.

Follow these steps:

Step 1: Generate a new 64-character hex key as shown above.

Step 2: Update your PYSHIELD_HMAC_KEY repository secret or environment variable.

Step 3: Delete the old dist/.pyshield_secret file so that the next build generates a fresh one from the environment variable.

Step 4: Run "pyshield build" to produce new protected binaries.

Step 5: Run "pyshield license generate" to issue new licenses for all customers or deployments.

Step 6: Distribute the new binaries and new license files together. Old licenses will not activate new binaries.

There is no way to rotate the secret embedded in an already-distributed binary without re-distributing the binary. Plan your rotation schedule accordingly.

## Threat model: what an attacker who obtains the secret can do

If an attacker obtains the HMAC secret for a specific build, they can generate arbitrarily many valid licenses for that specific binary. They cannot use that key to forge licenses for any other build, because each build has its own independently generated key.

This is the primary benefit of per-build secrets: it limits the blast radius. A compromise of one customer's binary does not compromise any other customer.

What an attacker who obtains the secret cannot do:

They cannot decrypt the obfuscated source code using the HMAC key alone. The HMAC key is only used for license signing. The PyArmor obfuscation key is separate and managed by PyArmor.

They cannot modify a license for a different machine to pass the machine-ID check. The machine ID is a hardware fingerprint, and the HMAC signature prevents undetected modification.

They cannot make an expired license appear unexpired. The expiry date is included in the signed payload, so changing it would invalidate the signature.

As documented in LIMITATIONS.md, a determined attacker who captures decrypted bytecode from memory could potentially extract the embedded key. Per-build secrets reduce the blast radius of such a compromise but cannot eliminate the underlying risk of local execution on user-controlled hardware.
